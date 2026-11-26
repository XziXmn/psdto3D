"""把 PSDTO3D 预览产出的 N 个视图交错成印刷 TIFF。

背景：PSDTO3D 的 "输出tiff" 依赖内部加密配置，无授权时必崩/输出纯色。
但它的 **预览** 不需要授权，能正确产出 N 个视图位图（C:\\ok3dtemp\\vw*.bmp）。
本工具接手最后一步：按柱镜光栅的物理模型做交错，输出可直接送印的 CMYK TIFF。

公式（详见 docs/原理_柱镜光栅立体印刷.md）：

    柱镜数       n_lent = floor(成品宽(in) × LPI)
    输出宽度     W_out  = n_lent × N          （每个柱镜 N 个像素，每视图 1 像素）
    输出高度     H_out  = 视图高度             （柱镜是竖直的，垂直方向不交错）
    列映射       out[x] 中  x = l*N + k  →  第 k 个视图的第 round(l × viewW / n_lent) 列

用法：
    python tools/interlace_tiff.py --views "C:\\ok3dtemp" --width-cm 10 --lpi 24 \
        --n 13 --dpi 600 -o out.tif [--cmyk] [--cmyk-profile icc/CoatedFOGRA39.icc]
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
from PIL import Image


def natural_key(p):
    n = re.findall(r'\d+', os.path.basename(p))
    return int(n[-1]) if n else 0


def load_views(pattern_dir, pattern, expect_n=None):
    files = sorted(glob.glob(os.path.join(pattern_dir, pattern)), key=natural_key)
    files = [f for f in files if re.search(r'vw\d+\.(bmp|png|tif|tiff)$', os.path.basename(f), re.I)]
    if expect_n:
        files = files[:expect_n]
    if not files:
        raise SystemExit('没有找到视图文件：%s' % os.path.join(pattern_dir, pattern))
    imgs = [Image.open(f).convert('RGB') for f in files]
    w, h = imgs[0].size
    for f, im in zip(files, imgs):
        if im.size != (w, h):
            raise SystemExit('%s 尺寸 %s != %s' % (f, im.size, (w, h)))
    return files, imgs


def interlace(imgs, n_lent, n_views, px_per_lent=None):
    """px_per_lent = None -> 每视图 1 像素（视图分辨率）；
    否则为印刷分辨率，每柱镜 px_per_lent 个像素，视图宽度按误差扩散分配（Bresenham）。"""
    arr = [np.asarray(im, np.uint8) for im in imgs]
    h, w, _ = arr[0].shape
    P = px_per_lent or n_views
    w_out = n_lent * P
    dst = np.empty((h, w_out, 3), np.uint8)
    for l in range(n_lent):
        x_src = int(round(l * w / float(n_lent)))
        if x_src >= w:
            x_src = w - 1
        base = l * P
        for q in range(P):
            k = int(q * n_views / P)          # 0..n_views-1，误差扩散的等价形式
            if k >= n_views:
                k = n_views - 1
            dst[:, base + q, :] = arr[k][:, x_src, :]
    return dst


def to_cmyk(rgb, icc_path=None):
    im = Image.fromarray(rgb, 'RGB')
    if icc_path and os.path.exists(icc_path):
        try:
            from PIL import ImageCms
            src = ImageCms.createProfile('sRGB')
            dst = ImageCms.getOpenProfile(icc_path)
            return ImageCms.profileToProfile(im, src, dst, outputMode='CMYK')
        except Exception as e:
            print('ICC 转换失败，改用 PIL 内置转换: %s' % e)
    return im.convert('CMYK')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--views', required=True, help='视图所在目录（内含 vw1..vwN.bmp）')
    ap.add_argument('--pattern', default='vw*.bmp')
    ap.add_argument('--width-cm', type=float, required=True, help='成品宽度（厘米）')
    ap.add_argument('--lpi', type=float, required=True)
    ap.add_argument('--n', type=int, required=True, help='视图数 Angles')
    ap.add_argument('--dpi', type=float, required=True, help='输出 DPI（写入 TIFF 元数据）')
    ap.add_argument('--cmyk', action='store_true', help='输出 CMYK（印刷用）')
    ap.add_argument('--cmyk-profile', default=None)
    ap.add_argument('--compression', default='tiff_lzw')
    ap.add_argument('--px-per-lenticule', type=int, default=None,
                    help='每柱镜像素数 P；省略则用 N（视图分辨率）。印刷用 P=dpi/lpi')
    ap.add_argument('--height-cm', type=float, default=None,
                    help='成品高度（厘米）；给出则垂直缩放到 height_cm/2.54*dpi')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args()

    files, imgs = load_views(a.views, a.pattern, expect_n=a.n)
    if a.height_cm:
        th = int(round(a.height_cm / 2.54 * a.dpi))
        if th != imgs[0].size[1]:
            print('垂直缩放 %d -> %d px (%.2fcm @ %.0fdpi)' % (imgs[0].size[1], th, a.height_cm, a.dpi))
            imgs = [im.resize((im.width, th), Image.LANCZOS) for im in imgs]
    if len(imgs) < a.n:
        raise SystemExit('视图不足：找到 %d，需要 %d' % (len(imgs), a.n))
    vw, vh = imgs[0].size
    width_in = a.width_cm / 2.54
    n_lent = max(1, int(width_in * a.lpi))
    print('视图 %d 张 %dx%d' % (len(imgs), vw, vh))
    print('成品 %.2fcm = %.3fin, LPI=%g -> 柱镜 %d 条' % (a.width_cm, width_in, a.lpi, n_lent))
    P = a.px_per_lenticule or max(1, int(round(a.dpi / a.lpi)))
    print('每柱镜 P = %d 像素 (= %.0f dpi / %g lpi)，视图宽按误差扩散分配'
          % (P, a.dpi, a.lpi))
    print('输出 %d x %d px，物理宽 %.2fcm'
          % (n_lent * P, vh, (n_lent * P) / a.dpi * 2.54))

    rgb = interlace(imgs, n_lent, a.n, px_per_lent=P)
    out = to_cmyk(rgb, a.cmyk_profile) if a.cmyk else Image.fromarray(rgb, 'RGB')
    kw = {}
    if a.compression and a.compression != 'none':
        kw['compression'] = a.compression
    out.save(a.output, dpi=(a.dpi, a.dpi), **kw)
    sz = os.path.getsize(a.output)
    print('已写出 %s  (%.1f MB, %s)' % (a.output, sz / 1048576.0, out.mode))
    return 0


if __name__ == '__main__':
    sys.exit(main())
