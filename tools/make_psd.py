# -*- coding: utf-8 -*-
"""Assemble the layered PSD from the exporter's own intermediates.

PSDTO3D writes, for an N-view job (N = 线数):
    C:\\ok3dtemp\\vwdNNN.gjs   68,133,002 B  -> 332 字节头 + R/G/B 三个平面（每平面 W*H）
    C:\\ok3dtemp\\vwdtNNN.gjs  22,7xx,xxx B  -> 8 位 BMP（第 4 通道）

The 10.1 build's own `writepsd` writes only the layer records (3 KB skeleton) and skips
the pixel payload, so this tool writes the same structure directly:

    python tools/make_psd.py --dir C:\\ok3dtemp --out out.psd
    python tools/make_psd.py --dir C:\\ok3dtemp --out out.psd --merged-from 1
"""
import argparse
import os
import struct
import sys
import time


def read_vwd_planes(path, w, h):
    """vwdNNN.gjs: 332-byte header then **interleaved** RGB (R,G,B,R,G,B,...).

    实测判据：相邻字节平均差 d(i,i+1)=41、d(i,i+3)=4.9 —— 说明同通道像素间隔 3 字节，
    即交错存储。这里把它拆成三个平面。
    """
    n = w * h
    with open(path, 'rb') as fh:
        fh.seek(332)
        raw = fh.read(n * 3)
    if len(raw) != n * 3:
        raise RuntimeError('%s: 像素数据不足' % os.path.basename(path))
    r = bytearray(n)
    g = bytearray(n)
    b = bytearray(n)
    r[0:n] = raw[0::3]
    g[0:n] = raw[1::3]
    b[0:n] = raw[2::3]
    return bytes(r), bytes(g), bytes(b)


def read_bmp_plane(path, w, h):
    """vwdtNNN.gjs: 8bpp BMP, rows bottom-up, stride padded to 4 bytes."""
    with open(path, 'rb') as fh:
        head = fh.read(54)
        if head[:2] != b'BM':
            raise RuntimeError('%s: 不是 BMP' % os.path.basename(path))
        off = struct.unpack('<I', head[10:14])[0]
        bw, bh = struct.unpack('<ii', head[18:26])
        bpp = struct.unpack('<H', head[28:30])[0]
        if bpp not in (8, 24):
            raise RuntimeError('%s: 不支持的位深 %d' % (os.path.basename(path), bpp))
        stride = ((bw * bpp // 8) + 3) & ~3
        fh.seek(off)
        raw = fh.read(stride * abs(bh))
    out = bytearray(w * h)
    for y in range(h):
        src_y = (h - 1 - y) if bh > 0 else y
        row = raw[src_y * stride: src_y * stride + w]
        out[y * w:(y + 1) * w] = row
    return bytes(out)


def build_psd(views, out_path, w, h, merged_from=1, progress=True):
    n_layers = len(views)
    chan_len = 2 + w * h          # 2 字节压缩方式 + 原始数据

    # ---- 图层记录 + 通道数据 ----
    records = bytearray()
    channel_data = bytearray()
    for i, (rgb, alpha) in enumerate(views, start=1):
        r, g, b = rgb
        rect = struct.pack('>iiii', 0, 0, h, w)
        chans = [(-1, alpha), (0, r), (1, g), (2, b)]
        rec = bytearray(rect)
        rec += struct.pack('>H', len(chans))
        for cid, _ in chans:
            rec += struct.pack('>hI', cid, chan_len)
        rec += b'8BIM' + b'norm'
        rec += struct.pack('>4B', 255, 0, 0, 0)
        name = ('ghm%02d' % i).encode('ascii')
        extra = struct.pack('>I', 0)          # 蒙版长度
        extra += struct.pack('>I', 0)          # 混合范围长度
        pstr = bytes([len(name)]) + name
        while len(pstr) % 4:
            pstr += b'\x00'
        extra += pstr
        rec += struct.pack('>I', len(extra)) + extra
        records += rec
        for _, plane in chans:
            channel_data += struct.pack('>H', 0)   # 压缩方式 0 = raw
            channel_data += plane
        if progress:
            sys.stderr.write('\r  层 %d/%d 已组装' % (i, n_layers))
            sys.stderr.flush()
    if progress:
        sys.stderr.write('\n')

    layer_info = struct.pack('>h', n_layers) + bytes(records) + bytes(channel_data)
    layer_and_mask = struct.pack('>I', len(layer_info)) + layer_info + struct.pack('>I', 0)

    # ---- 合并图（取第 merged_from 个视图的 RGB）----
    r, g, b = views[merged_from - 1][0] if views else (b'', b'', b'')
    merged = struct.pack('>H', 0) + r + g + b

    with open(out_path, 'wb') as fh:
        fh.write(b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6)
        fh.write(struct.pack('>HIIHH', 3, h, w, 8, 3))
        fh.write(struct.pack('>I', 0))                      # 颜色模式数据
        fh.write(struct.pack('>I', 0))                      # 图像资源
        fh.write(struct.pack('>I', len(layer_and_mask)))
        fh.write(layer_and_mask)
        fh.write(merged)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=r'C:\ok3dtemp')
    ap.add_argument('--out', required=True)
    ap.add_argument('--width', type=int, default=4370)
    ap.add_argument('--height', type=int, default=5197)
    ap.add_argument('--views', type=int, default=11)
    ap.add_argument('--merged-from', type=int, default=1)
    a = ap.parse_args()

    views = []
    for i in range(1, a.views + 1):
        vwd = os.path.join(a.dir, 'vwd%03d.gjs' % i)
        vwt = os.path.join(a.dir, 'vwdt%03d.gjs' % i)
        if not (os.path.isfile(vwd) and os.path.isfile(vwt)):
            print('缺少视图 %d：%s / %s' % (i, vwd, vwt))
            return 2
        views.append((read_vwd_planes(vwd, a.width, a.height),
                      read_bmp_plane(vwt, a.width, a.height)))
        sys.stderr.write('.')
        sys.stderr.flush()

    t0 = time.time()
    build_psd(views, a.out, a.width, a.height, a.merged_from)
    print('\n写出 %s  %d 字节  用时 %.1fs' % (a.out, os.path.getsize(a.out), time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
