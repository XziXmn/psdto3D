"""把 PSDTO3D 的裸 RGB TIFF 转成 PNG（缩小），并可生成差异热图。

    python tools/tif2png.py a.tif out.png [--width 900]
    python tools/tif2png.py a.tif b.tif --diff diff.png

只读 TIFF，不解压缩（厂商写的是 Compression=1 裸数据）。
"""
import argparse
import struct
import sys

import numpy as np
from PIL import Image


def load(path):
    d = open(path, "rb").read()
    ifd = struct.unpack_from("<I", d, 4)[0]
    n = struct.unpack_from("<H", d, ifd)[0]
    tag = {}
    for i in range(n):
        t, typ, cnt = struct.unpack_from("<HHI", d, ifd + 2 + 12 * i)
        raw = d[ifd + 2 + 12 * i + 8:ifd + 2 + 12 * i + 12]
        v = struct.unpack("<H", raw[:2])[0] if (typ == 3 and cnt == 1) else struct.unpack("<I", raw)[0]
        tag[t] = v
    w, h, spp, off = tag[0x0100], tag[0x0101], tag[0x0115], tag[0x0111]
    px = np.frombuffer(d, dtype=np.uint8, count=w * h * spp, offset=off)
    return px.reshape(h, w, spp)


def to_img(a, width):
    im = Image.fromarray(a[:, :, :3], "RGB")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--diff", action="store_true")
    a = ap.parse_args()
    if a.diff and len(a.files) == 2:
        A, B = load(a.files[0]), load(a.files[1])
        d = np.abs(A[:, :, :3].astype(np.int16) - B[:, :, :3].astype(np.int16)).astype(np.uint8)
        heat = np.clip(d.max(axis=2).astype(np.int16) * 3, 0, 255).astype(np.uint8)
        im = Image.fromarray(heat, "L")
        if a.width and im.width > a.width:
            im = im.resize((a.width, round(im.height * a.width / im.width)), Image.LANCZOS)
        im.save(a.out)
        print("diff %s  mean=%.3f max=%d" % (a.out, d.mean(), d.max()))
        return 0
    for f in a.files:
        im = to_img(load(f), a.width)
        out = a.out or (f.rsplit(".", 1)[0] + "_prev.png")
        im.save(out)
        print("%s -> %s %dx%d" % (f, out, im.width, im.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
