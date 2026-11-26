"""对 PSDTO3D 产出的 TIFF 做像素级对比（裸 RGB，StripOffsets=332 或 334）。

    python tools/tifpixdiff.py a.tif b.tif [--views N]

输出：整体平均绝对差、按视图相位（列 % N）的差异分布。
相位分布能区分"同一张图整体偏移"和"逐层视差幅度不同"。
"""
import argparse
import struct
import sys

import numpy as np


def load(path):
    d = open(path, "rb").read()
    if d[:2] != b"II":
        raise SystemExit("%s: 不是小端 TIFF" % path)
    ifd = struct.unpack_from("<I", d, 4)[0]
    n = struct.unpack_from("<H", d, ifd)[0]
    tag = {}
    for i in range(n):
        t, typ, cnt = struct.unpack_from("<HHI", d, ifd + 2 + 12 * i)
        raw = d[ifd + 2 + 12 * i + 8:ifd + 2 + 12 * i + 12]
        if typ == 3 and cnt == 1:
            v = struct.unpack("<H", raw[:2])[0]
        elif typ == 4 and cnt == 1:
            v = struct.unpack("<I", raw)[0]
        else:
            v = struct.unpack("<I", raw)[0]      # 偏移
        tag[t] = (typ, cnt, v, raw)
    w = tag[0x0100][2]
    h = tag[0x0101][2]
    spp = tag[0x0115][2]
    off = tag[0x0111][2]
    comp = tag[0x0103][2]
    px = np.frombuffer(d, dtype=np.uint8, count=w * h * spp, offset=off)
    return {'w': w, 'h': h, 'spp': spp, 'comp': comp, 'off': off,
            'px': px.reshape(h, w, spp).astype(np.int16)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--views", type=int, default=0)
    ap.add_argument("--rows", default="")
    args = ap.parse_args()

    A, B = load(args.a), load(args.b)
    print("A %-42s %dx%d spp=%d comp=%d off=%d" % (args.a.split('\\')[-1], A['w'], A['h'],
                                                    A['spp'], A['comp'], A['off']))
    print("B %-42s %dx%d spp=%d comp=%d off=%d" % (args.b.split('\\')[-1], B['w'], B['h'],
                                                    B['spp'], B['comp'], B['off']))
    if (A['w'], A['h'], A['spp']) != (B['w'], B['h'], B['spp']):
        print("尺寸/通道不同，只能报整体差异")
        return 0
    a, b = A['px'], B['px']
    diff = np.abs(a - b)
    print("整体平均绝对差 %.4f   最大 %d   完全相同=%s" % (
        diff.mean(), diff.max(), bool(diff.max() == 0)))
    if args.rows:
        r0, r1 = (int(x) for x in args.rows.split(':'))
        a, b, diff = a[r0:r1], b[r0:r1], diff[r0:r1]
        print("（只统计行 %d..%d）" % (r0, r1))
    col = diff.mean(axis=(0, 2))
    if args.views:
        print("按视图相位（列 %% %d）:" % args.views)
        for p in range(args.views):
            print("   phase %2d : %.4f" % (p, col[p::args.views].mean()))
    else:
        print("列差异 均值 %.4f 最大 %.1f" % (col.mean(), col.max()))
    # 行方向差异（判断是否只在某些层/区域）
    row = diff.mean(axis=(1, 2))
    nz = np.nonzero(row > 0.5)[0]
    print("行差异>0.5 的行数 %d / %d" % (len(nz), len(row)))
    if len(nz):
        print("  首个差异行 %d，最后 %d" % (nz[0], nz[-1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
