"""Pack N rendered views into a layered PSD (the input LenticularOmega expects).

PSDTO3D 的正常流程是：分层 PSD → 生成 N 个视图 → 输出 PSD（N 层）→ LenticularOmega 交错。
它的 "输出PSD" 在无加密狗时无法使用，但**预览**能在无狗环境正常产出 N 个视图位图，
所以这里直接把视图位图打包成 LenticularOmega 需要的分层 PSD，绕开那一步。

用法：
    python tools/views_to_psd.py <视图目录或文件...> -o out.psd [--reverse] [--pattern vw*.bmp]

约定：
    * 图层名 view_01..view_NN，按文件名中的数字升序
    * 第 1 个视图放在**最底层**（LenticularOmega 默认按层序升序交错）
    * 画布尺寸 = 视图尺寸；所有视图必须同尺寸
"""
import argparse
import glob
import os
import re
import struct
import sys

from PIL import Image


def natural_key(path):
    base = os.path.basename(path)
    nums = re.findall(r'\d+', base)
    return (int(nums[-1]) if nums else 0, base.lower())


def collect(paths, pattern):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, pattern or '*.*'))
        else:
            files.append(p)
    files = [f for f in files if os.path.splitext(f)[1].lower() in
             ('.bmp', '.png', '.tif', '.tiff', '.jpg', '.jpeg')]
    files.sort(key=natural_key)
    return files


def load_layer(path, size):
    im = Image.open(path).convert('RGB')
    if im.size != size:
        raise SystemExit('%s 尺寸 %s 与画布 %s 不一致' % (os.path.basename(path), im.size, size))
    return im


def build_psd(layers, out_path):
    """layers: 由底到顶的 PIL RGB 图像列表。写未压缩（raw）PSD。"""
    n = len(layers)
    w, h = layers[0].size

    def pad4(b):
        return b + b'\x00' * ((4 - len(b) % 4) % 4)

    # ---- 图层记录 + 通道数据 ----
    records = b''
    channel_blobs = b''
    for i, im in enumerate(layers):
        name = ('view_%02d' % (i + 1)).encode('ascii')
        name_field = pad4(bytes([len(name)]) + name)
        rgb = im.tobytes()                       # 3 * w * h, 逐行 interleaved
        planes = [rgb[c::3] for c in range(3)]

        ch_info = b''
        for cid in (0, 1, 2):
            ch_info += struct.pack('>HI', cid, 2 + len(planes[cid]))

        extra = struct.pack('>I', 0)             # mask data length
        extra += struct.pack('>I', 0)            # blending ranges length
        extra += name_field

        records += struct.pack('>iiii', 0, 0, h, w)   # top,left,bottom,right
        records += struct.pack('>H', 3)               # channel count
        records += ch_info
        records += b'8BIM' + b'norm'                  # blend mode
        records += bytes([255, 0, 0, 0])               # opacity, clipping, flags, filler
        records += struct.pack('>I', len(extra)) + extra

        for p in planes:
            channel_blobs += struct.pack('>H', 0) + p   # compression 0 = raw

    layer_info = struct.pack('>h', n if n < 32768 else -n) + records + channel_blobs
    layer_and_mask = struct.pack('>I', len(layer_info)) + layer_info + struct.pack('>I', 0)

    # ---- 合并图（用顶层视图作为可见结果）----
    merged = layers[-1].tobytes()
    image_data = struct.pack('>H', 0)
    for c in range(3):
        image_data += merged[c::3]

    # ---- 组装 ----
    header = b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6
    header += struct.pack('>HIIHH', 3, h, w, 8, 3)
    body = struct.pack('>I', 0)                    # color mode data
    body += struct.pack('>I', 0)                   # image resources
    body += struct.pack('>I', len(layer_and_mask)) + layer_and_mask
    body += image_data

    with open(out_path, 'wb') as f:
        f.write(header + body)
    return n, w, h, os.path.getsize(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+', help='视图目录或文件')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--pattern', default=None, help='目录内匹配模式，如 vw*.bmp')
    ap.add_argument('--reverse', action='store_true', help='反转层序（第 1 个视图放顶层）')
    a = ap.parse_args()

    files = collect(a.inputs, a.pattern)
    if len(files) < 2:
        raise SystemExit('视图数量不足：%d' % len(files))
    probe = Image.open(files[0])
    size = probe.size
    layers = [load_layer(f, size) for f in files]
    if a.reverse:
        layers.reverse()

    print('视图 %d 张，画布 %dx%d' % (len(layers), size[0], size[1]))
    for i, f in enumerate(files if not a.reverse else list(reversed(files))):
        print('   layer %02d <- %s' % (i + 1, os.path.basename(f)))
    n, w, h, sz = build_psd(layers, a.output)
    print('\n已写出 %s  (%d 层, %dx%d, %.1f MB)' % (a.output, n, w, h, sz / 1048576.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
