"""比较两个 vwd*.gjs（印刷尺寸视图，裸 RGB TIFF）的画面差异。

    python tools/cmp_vwd.py A.gjs B.gjs [--bands 12] [--pairs]

--bands 会把图按水平条带切开分别报差异，便于看出"整体错位"还是"局部错"。
--pairs 则把 A/B 目录下所有同名 vwd 两两比。
"""
import argparse
import glob
import os
import struct
import sys

import numpy as np
from PIL import Image


def load(path):
    d = open(path, "rb").read()
    if d[:2] not in (b"II", b"MM"):
        raise SystemExit("%s 不是 TIFF" % path)
    ifd = struct.unpack_from("<I", d, 4)[0]
    n = struct.unpack_from("<H", d, ifd)[0]
    tag = {}
    for i in range(n):
        t, typ, cnt = struct.unpack_from("<HHI", d, ifd + 2 + 12 * i)
        raw = d[ifd + 2 + 12 * i + 8: ifd + 2 + 12 * i + 12]
        v = struct.unpack("<H", raw[:2])[0] if (typ == 3 and cnt == 1) else struct.unpack("<I", raw)[0]
        tag[t] = v
    w, h, spp, off = tag[0x100], tag[0x101], tag[0x115], tag[0x111]
    arr = np.frombuffer(d, dtype=np.uint8, count=w * h * spp, offset=off)
    return arr.reshape(h, w, spp)[:, :, :3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--bands", type=int, default=10)
    a = ap.parse_args()
    if os.path.isdir(a.a) and os.path.isdir(a.b):
        pa = {os.path.basename(p): p for p in glob.glob(os.path.join(a.a, "vwd*.gjs"))}
        pb = {os.path.basename(p): p for p in glob.glob(os.path.join(a.b, "vwd*.gjs"))}
        common = sorted(set(pa) & set(pb))
        print("%-14s %10s %10s" % ("文件", "mean", "max"))
        for name in common:
            A, B = load(pa[name]), load(pb[name])
            if A.shape != B.shape:
                print("%-14s 尺寸不同 %s vs %s" % (name, A.shape, B.shape))
                continue
            d = np.abs(A.astype(np.int16) - B.astype(np.int16))
            print("%-14s %10.3f %10d" % (name, d.mean(), d.max()))
        return 0

    A, B = load(a.a), load(a.b)
    print("A %s %s" % (os.path.basename(a.a), A.shape))
    print("B %s %s" % (os.path.basename(a.b), B.shape))
    if A.shape != B.shape:
        return 1
    d = np.abs(A.astype(np.int16) - B.astype(np.int16))
    print("整体 mean=%.3f max=%d 相同=%s" % (d.mean(), d.max(), bool(d.max() == 0)))
    h = A.shape[0]
    step = h // a.bands
    print("按水平条带：")
    for i in range(a.bands):
        y0 = i * step
        y1 = h if i == a.bands - 1 else (i + 1) * step
        print("   行 %5d-%5d : mean %7.3f" % (y0, y1, d[y0:y1].mean()))
    col = d.mean(axis=(0, 2))
    print("按 11 相位（列 %% 11）：")
    for p in range(11):
        print("   phase %2d : %.3f" % (p, col[p::11].mean()))
    # 水平整体偏移搜索（粗）
    best = None
    for s in range(-6, 7):
        if s >= 0:
            dd = np.abs(A[:, s:].astype(np.int16) - B[:, :B.shape[1] - s].astype(np.int16)).mean()
        else:
            dd = np.abs(A[:, :A.shape[1] + s].astype(np.int16) - B[:, -s:].astype(np.int16)).mean()
        if best is None or dd < best[0]:
            best = (dd, s)
    print("最佳整体水平偏移: %+d px（残差 %.3f）" % (best[1], best[0]))
    # 存一张对比图
    W = 600
    def small(im):
        return im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    ia = small(Image.fromarray(A, "RGB"))
    ib = small(Image.fromarray(B, "RGB"))
    heat = np.clip(d.max(axis=2) * 4, 0, 255).astype(np.uint8)
    ih = small(Image.fromarray(np.stack([heat] * 3, axis=2)))
    sheet = Image.new("RGB", (W * 3 + 20, ia.height + 26), (22, 22, 22))
    for i, im in enumerate((ia, ib, ih)):
        sheet.paste(im, (i * (W + 10), 26))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_review", "cmp_vwd.png")
    sheet.save(out)
    print("对比图:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
