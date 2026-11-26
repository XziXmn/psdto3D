"""按图层取 PSD 像素、导出 PNG、逐层对比。

PSDTO3D 写出的 PSD 布局（实测）：全部层记录连续排在层段开头，之后才是各层通道像素数据；
每层 4 通道，通道 id -1=透明蒙版、0/1/2=R/G/B，数据前 2 字节是压缩标记 0（裸数据）。

    python tools/psdlayers.py dump A.psd --outdir D --width 700
    python tools/psdlayers.py diff A.psd B.psd --outdir D --width 700

diff 会输出每层的平均绝对差、最大差，并把 A/B/差异 三张图拼在一起。
"""
import argparse
import mmap
import os
import struct
import sys

import numpy as np
from PIL import Image


def parse(path):
    f = open(path, "rb")
    n = os.path.getsize(path)
    d = mmap.mmap(f.fileno(), n, access=mmap.ACCESS_READ)
    if d[:4] != b"8BPS":
        raise SystemExit("not psd")
    ch, h, w, depth, mode = struct.unpack_from(">HIIHH", d, 12)
    p = 26
    cm, = struct.unpack_from(">I", d, p); p += 4 + cm
    ir, = struct.unpack_from(">I", d, p); p += 4 + ir
    lm, = struct.unpack_from(">I", d, p); p += 4
    li, = struct.unpack_from(">I", d, p); p += 4
    li_end = p + li
    cnt, = struct.unpack_from(">h", d, p); p += 2
    layers = []
    for i in range(abs(cnt)):
        top, left, bottom, right = struct.unpack_from(">iiii", d, p); p += 16
        nch, = struct.unpack_from(">H", d, p); p += 2
        chans = []
        for _ in range(nch):
            cid, clen = struct.unpack_from(">hI", d, p); p += 6
            chans.append((cid, clen))
        p += 12
        exlen, = struct.unpack_from(">I", d, p); p += 4
        ex_end = p + exlen
        q = p
        ml, = struct.unpack_from(">I", d, q); q += 4 + ml
        br, = struct.unpack_from(">I", d, q); q += 4 + br
        nl = d[q]
        name = bytes(d[q + 1:q + 1 + nl]).decode("gbk", "replace")
        layers.append({"name": name, "rect": (top, left, bottom, right),
                       "chans": chans, "w": right - left, "h": bottom - top})
        p = ex_end
    data_start = p
    off = data_start
    for L in layers:
        L["offset"] = off
        L["data_bytes"] = sum(c[1] for c in L["chans"])
        off += L["data_bytes"]
    return {"path": path, "w": w, "h": h, "mode": mode, "layers": layers,
            "data_start": data_start, "mm": d, "size": n}


def layer_img(P, i):
    L = P["layers"][i]
    d, w, h = P["mm"], L["w"], L["h"]
    base = L["offset"]
    planes = {}
    o = base
    for cid, clen in L["chans"]:
        comp, = struct.unpack_from(">H", d, o)
        if comp != 0:
            raise SystemExit("layer %s channel %d compressed(%d)" % (L["name"], cid, comp))
        planes[cid] = np.frombuffer(d, dtype=np.uint8, count=w * h, offset=o + 2).reshape(h, w)
        o += clen
    rgb = np.zeros((h, w, 3), np.uint8)
    for k, cid in enumerate((0, 1, 2)):
        if cid in planes:
            rgb[:, :, k] = planes[cid]
    alpha = planes.get(-1, np.full((h, w), 255, np.uint8))
    return rgb, alpha


def save_png(rgb, alpha, path, width, bg=(255, 255, 255)):
    h, w = alpha.shape
    a = (alpha.astype(np.float32) / 255.0)[:, :, None]
    b = np.array(bg, np.float32)[None, None, :]
    comp = (rgb.astype(np.float32) * a + b * (1 - a)).astype(np.uint8)
    im = Image.fromarray(comp, "RGB")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(path)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dump", "diff", "list"])
    ap.add_argument("a")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--outdir", default="_review/layers")
    ap.add_argument("--width", type=int, default=700)
    ap.add_argument("--layers", default="")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    A = parse(args.a)
    print("A %s  %dx%d  layers=%d  data_start=%d" % (
        os.path.basename(args.a), A["w"], A["h"], len(A["layers"]), A["data_start"]))
    if args.mode == "list":
        for i, L in enumerate(A["layers"]):
            print("  [%02d] %-8s %dx%d ch=%s off=%d" % (
                i, L["name"], L["w"], L["h"], [c[0] for c in L["chans"]], L["offset"]))
        return 0

    want = range(len(A["layers"]))
    if args.layers:
        want = [int(x) for x in args.layers.split(",")]

    if args.mode == "dump":
        for i in want:
            rgb, alpha = layer_img(A, i)
            p = os.path.join(args.outdir, "%s_%02d_%s.png" % (
                os.path.splitext(os.path.basename(args.a))[0], i, A["layers"][i]["name"]))
            save_png(rgb, alpha, p, args.width)
            print("  wrote", p)
        return 0

    B = parse(args.b)
    print("B %s  %dx%d  layers=%d" % (os.path.basename(args.b), B["w"], B["h"], len(B["layers"])))
    n = min(len(A["layers"]), len(B["layers"]))
    print("%-4s %-8s %-14s %-14s %8s %6s %6s" % ("#", "name", "A size", "B size", "mean", "p99", "max"))
    for i in range(n):
        la, lb = A["layers"][i], B["layers"][i]
        ra, aa = layer_img(A, i)
        rb, ab = layer_img(B, i)
        if ra.shape != rb.shape:
            print("  [%02d] 尺寸不同 %s vs %s" % (i, ra.shape, rb.shape))
            continue
        diff = np.abs(ra.astype(np.int16) - rb.astype(np.int16))
        adiff = np.abs(aa.astype(np.int16) - ab.astype(np.int16))
        print("[%02d] %-8s %dx%-5d %dx%-5d %8.3f %6d %6d   alpha_mean=%.3f" % (
            i, la["name"], la["w"], la["h"], lb["w"], lb["h"],
            diff.mean(), np.percentile(diff, 99), diff.max(), adiff.mean()))
        if i in want or not args.layers:
            heat = np.clip(diff.max(axis=2).astype(np.int16) * 4, 0, 255).astype(np.uint8)
            ia = Image.fromarray(ra, "RGB")
            ib = Image.fromarray(rb, "RGB")
            ih = Image.fromarray(heat, "L").convert("RGB")
            W = args.width
            ims = []
            for im in (ia, ib, ih):
                ims.append(im.resize((W, round(im.height * W / im.width)), Image.LANCZOS))
            sheet = Image.new("RGB", (W * 3, ims[0].height), (20, 20, 20))
            for k, im in enumerate(ims):
                sheet.paste(im, (k * W, 0))
            p = os.path.join(args.outdir, "cmp_%02d_%s.png" % (i, la["name"]))
            sheet.save(p)
            print("        sheet ->", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
