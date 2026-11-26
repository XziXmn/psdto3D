# -*- coding: utf-8 -*-
"""生成测试用分层 PSD（每层 4 通道：alpha + RGB，普通层，无背景层）。

    python tools/make_test_psd.py out.psd --layers 50 --size 400
"""
import argparse
import struct


def build(path, layers, size, alpha_first=True):
    w = h = size
    n = w * h
    chan_ids = [-1, 0, 1, 2] if alpha_first else [0, 1, 2]

    recs = bytearray()
    data = bytearray()
    for i in range(layers):
        v = (i * 7) % 250
        recs += struct.pack('>iiii', 0, 0, h, w)
        recs += struct.pack('>H', len(chan_ids))
        for cid in chan_ids:
            recs += struct.pack('>hI', cid, n + 2)
        recs += b'8BIM' + b'norm'
        recs += struct.pack('>4B', 255, 0, 0, 0)
        name = ('L%03d' % (i + 1)).encode('ascii')
        extra = struct.pack('>I', 0) + struct.pack('>I', 0)
        pstr = bytes([len(name)]) + name
        while len(pstr) % 4:
            pstr += b'\x00'
        extra += pstr
        recs += struct.pack('>I', len(extra)) + extra
        for k, cid in enumerate(chan_ids):
            plane = 255 if cid == -1 else (v + k * 30) & 0xFF
            data += struct.pack('>H', 0)
            data += bytes([plane]) * n

    li = struct.pack('>h', layers) + bytes(recs) + bytes(data)
    lm = struct.pack('>I', len(li)) + li + struct.pack('>I', 0)

    with open(path, 'wb') as fh:
        fh.write(b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6)
        fh.write(struct.pack('>HIIHH', 4, h, w, 8, 3))
        fh.write(struct.pack('>I', 0))
        fh.write(struct.pack('>I', 0))
        fh.write(struct.pack('>I', len(lm)))
        fh.write(lm)
        fh.write(struct.pack('>H', 0))
        for c in range(3):
            fh.write(bytes([(c * 60 + 40) & 0xFF]) * n)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--layers', type=int, default=50)
    ap.add_argument('--size', type=int, default=400)
    a = ap.parse_args()
    build(a.path, a.layers, a.size)
    print('写出 %s：%d 层 %dx%d 4通道' % (a.path, a.layers, a.size, a.size))


if __name__ == '__main__':
    main()
