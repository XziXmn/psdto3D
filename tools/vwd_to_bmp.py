# -*- coding: utf-8 -*-
"""把 vwd*.gjs（交错 RGB）转成 24bpp BMP，用于验证 writepsd 是否只认 BMP。

    python tools/vwd_to_bmp.py --dir C:\\ok3dtemp --views 11
"""
import argparse
import glob
import os
import struct
import sys

W, H = 4370, 5197


def convert(src, dst, w, h):
    with open(src, 'rb') as fh:
        fh.seek(332)
        raw = fh.read(w * h * 3)
    if len(raw) != w * h * 3:
        raise RuntimeError('short read')
    stride = (w * 3 + 3) & ~3
    rows = []
    for y in range(h - 1, -1, -1):
        row = raw[y * w * 3:(y + 1) * w * 3]
        rows.append(row + b'\x00' * (stride - w * 3))
    body = b''.join(rows)
    header = b'BM' + struct.pack('<IHHI', 14 + 40 + len(body), 0, 0, 54)
    info = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(body), 2835, 2835, 0, 0)
    with open(dst, 'wb') as fh:
        fh.write(header + info + body)
    return os.path.getsize(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=r'C:\ok3dtemp')
    ap.add_argument('--views', type=int, default=11)
    ap.add_argument('--width', type=int, default=W)
    ap.add_argument('--height', type=int, default=H)
    a = ap.parse_args()
    for i in range(1, a.views + 1):
        src = os.path.join(a.dir, 'vwd%03d.gjs' % i)
        if not os.path.exists(src):
            print('缺 %s' % src)
            return 2
        n = convert(src, src, a.width, a.height)
        print('vwd%03d.gjs -> 24bpp BMP %d 字节' % (i, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
