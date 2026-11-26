"""一键导出印刷 TIFF：用 PSDTO3D 的预览产视图，再自己交错。

为什么需要它
------------
PSDTO3D 的 `输出tiff` 依赖内部加密配置（USBKey），无授权时：
  · 原始 DLL → `Floating point division by zero`
  · 修补后   → 能写文件但内容是纯色（视图数据源为空）
而它的 **预览** 不需要授权，能正确产出 N 个视图位图（C:\\ok3dtemp\\vw*.bmp）。

本脚本把两段接起来，等价于"输出tiff"功能：

    打开工程 → 预览 → 等 N 张视图 → 停止 → 按柱镜参数交错 → CMYK TIFF

用法：
    python tools/export_tiff.py --pkg "psdto3d2022绿色版" --project "工程.tw3d2" \
        -o out.tif [--dpi 600] [--width-cm auto] [--height-cm auto]

工程文件里没有成品尺寸时，用 --width-cm/--height-cm 显式给。
"""
import argparse
import glob
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WORKDIR = r'C:\ok3dtemp'


def parse_project(path):
    raw = open(path, 'rb').read()
    lines = [l.strip() for l in raw.split(b'\r\n')]
    hdr = lines[1].decode('gbk', 'replace').split()
    lpi = float(hdr[0])
    angles = int(float(hdr[1]))
    depth = float(hdr[3]) if len(hdr) > 3 else 1.0
    w_cm = h_cm = None
    for l in lines[:12]:
        parts = l.decode('gbk', 'replace').split()
        if len(parts) == 5 and re.fullmatch(r'-?\d+', parts[3] or '') and re.fullmatch(r'-?\d+', parts[4] or ''):
            try:
                w_cm = float(parts[1])
                h_cm = float(parts[2])
            except ValueError:
                continue
            break
    return {'lpi': lpi, 'angles': angles, 'depth': depth,
            'width_cm': w_cm, 'height_cm': h_cm, 'path': os.path.abspath(path)}


def clear_views():
    for f in glob.glob(os.path.join(WORKDIR, 'vw*.bmp')):
        try:
            os.remove(f)
        except OSError:
            pass


def collect_views(n, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        named = {}
        for f in glob.glob(os.path.join(WORKDIR, 'vw*.bmp')):
            m = re.fullmatch(r'vw(\d+)\.bmp', os.path.basename(f))
            if m:
                named[int(m.group(1))] = f
        if len(named) >= n:
            return [named[k] for k in sorted(named)][:n]
        time.sleep(2)
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default='psdto3d2022绿色版')
    ap.add_argument('--project', required=True)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--dpi', type=float, default=600)
    ap.add_argument('--width-cm', type=float, default=None)
    ap.add_argument('--height-cm', type=float, default=None)
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--keep-views', action='store_true')
    a = ap.parse_args()

    import dialogless_launch
    import win
    import interlace_tiff as it
    from PIL import Image

    info = parse_project(a.project)
    n = info['angles']
    w_cm = a.width_cm or info['width_cm']
    h_cm = a.height_cm or info['height_cm']
    print('工程: LPI=%g  视图数=%d  Depth=%g  成品=%sx%s cm'
          % (info['lpi'], n, info['depth'], w_cm, h_cm))
    if not w_cm:
        raise SystemExit('工程里没读到成品尺寸，请用 --width-cm/--height-cm 指定')

    os.makedirs(WORKDIR, exist_ok=True)
    clear_views()

    pkg = os.path.abspath(a.pkg)
    exe = os.path.join(pkg, 'psdto3d101.exe')
    print('启动 %s ...' % os.path.basename(exe))
    rep, _ = dialogless_launch.launch(exe, pkg, info['path'], os.path.abspath(a.output))
    pid = rep['pid']
    try:
        time.sleep(5)
        hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
        print('打开工程 ...')
        win.command(hwnd, 3)
        time.sleep(10)
        print('预览（生成视图）...')
        win.command(hwnd, 12)
        files = collect_views(n, a.timeout)
        if not files:
            raise SystemExit('等待视图超时（%ds）' % a.timeout)
        print('收到 %d 张视图' % len(files))
        win.command(hwnd, 13)
        time.sleep(2)
    finally:
        os.system('taskkill /PID %d /F >nul 2>&1' % pid)

    imgs = [Image.open(f).convert('RGB') for f in files]
    vw, vh = imgs[0].size
    if h_cm:
        th = int(round(h_cm / 2.54 * a.dpi))
        if th != vh:
            imgs = [im.resize((im.width, th), Image.LANCZOS) for im in imgs]
            vh = th

    width_in = w_cm / 2.54
    n_lent = max(1, int(width_in * info['lpi']))
    P = max(1, int(round(a.dpi / info['lpi'])))
    print('柱镜 %d 条 × 每柱镜 %d px -> 输出 %d x %d px' % (n_lent, P, n_lent * P, vh))
    rgb = it.interlace(imgs, n_lent, n, px_per_lent=P)
    out = it.to_cmyk(rgb)
    out.save(a.output, dpi=(a.dpi, a.dpi), compression='tiff_lzw')
    print('已写出 %s  (%.1f MB, %s, %.2f x %.2f cm)'
          % (a.output, os.path.getsize(a.output) / 1048576.0, out.mode,
             out.width / a.dpi * 2.54, out.height / a.dpi * 2.54))
    if not a.keep_views:
        clear_views()
    return 0


if __name__ == '__main__':
    sys.exit(main())
