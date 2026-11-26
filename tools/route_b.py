"""路线 B 的核心：**不用加密狗**，把预览位图（vw*.bmp）直接交错成印刷 TIFF。

交错规则与 `cmykdrop.c` 里复刻过的厂商 mergtotiff 完全一致：
    柱镜像素 P = 输出宽 / 柱镜数
    x 列 → q = x % P → 视图号 vidx = q * N / P → 取视图 (N-1-vidx)
    采样：sx = trunc((2x+1)*vw/(2*ow))，sy = trunc((y+0.5)*vh/oh)
    颜色：厂商写的是取反值（255-源），本脚本两种都试，报告最好的

    python tools/route_b.py --views C:\\ok3dtemp --ref out.tif \
        --out my.tif --n 11 --p 11 --invert auto
"""
import argparse
import glob
import os
import re
import struct
import sys

import numpy as np
from PIL import Image


def load_views(views_dir, n, src="bmp"):
    if src == "vwd":
        fs = sorted([p for p in glob.glob(os.path.join(views_dir, "vwd*.gjs"))
                     if re.match(r"^vwd\d+\.gjs$", os.path.basename(p), re.I)],
                    key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[-1]))
        if len(fs) < n:
            raise SystemExit("只找到 %d 个 vwd*.gjs，需要 %d" % (len(fs), n))
        meta = []
        for p in fs[:n]:
            d = open(p, "rb").read(2048)
            ifd = struct.unpack_from("<I", d, 4)[0]
            nt = struct.unpack_from("<H", d, ifd)[0]
            tag = {}
            for i in range(nt):
                t, typ, cnt = struct.unpack_from("<HHI", d, ifd + 2 + 12 * i)
                raw = d[ifd + 2 + 12 * i + 8: ifd + 2 + 12 * i + 12]
                v = struct.unpack("<H", raw[:2])[0] if (typ == 3 and cnt == 1) else struct.unpack("<I", raw)[0]
                tag[t] = v
            meta.append((p, tag[0x0100], tag[0x0101], tag[0x0111]))
        return meta, fs[:n]
    fs = sorted(glob.glob(os.path.join(views_dir, "vw*.bmp")),
                key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[-1]))
    if len(fs) < n:
        raise SystemExit("只找到 %d 个 vw*.bmp，需要 %d" % (len(fs), n))
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in fs[:n]]
    return imgs, fs[:n]


def interlace(imgs, ow, oh, p, invert, reverse, src="bmp"):
    n = len(imgs)
    if src == "vwd":
        vw, vh = imgs[0][1], imgs[0][2]
    else:
        vh, vw = imgs[0].shape[:2]
    xs = np.arange(ow)
    q = xs % p
    vidx = (q * n) // p
    want = n - 1 - vidx
    sx = ((2 * xs + 1) * vw) // (2 * ow)
    sx = np.clip(sx, 0, vw - 1)
    ys = np.arange(oh)
    sy = ((2 * ys + 1) * vh) // (2 * oh)
    sy = np.clip(sy, 0, vh - 1)
    order = list(range(n))
    if reverse:
        order = order[::-1]
    out = np.zeros((oh, ow, 3), np.uint8)
    for k in range(n):
        m = (want == k)
        if not m.any():
            continue
        idx = order[k]
        if src == "vwd":
            path, w, h, off = imgs[idx]
            arr = np.fromfile(path, dtype=np.uint8, count=w * h * 3, offset=off).reshape(h, w, 3)
        else:
            arr = imgs[idx]
        block = arr[sy][:, sx[m]]
        if invert:
            block = 255 - block
        out[:, m] = block
        if src == "vwd":
            del arr
    return out


def load_tif_rgb(path):
    d = open(path, "rb").read()
    ifd = struct.unpack_from("<I", d, 4)[0]
    n = struct.unpack_from("<H", d, ifd)[0]
    tag = {}
    for i in range(n):
        t, typ, cnt = struct.unpack_from("<HHI", d, ifd + 2 + 12 * i)
        raw = d[ifd + 2 + 12 * i + 8: ifd + 2 + 12 * i + 12]
        v = struct.unpack("<H", raw[:2])[0] if (typ == 3 and cnt == 1) else struct.unpack("<I", raw)[0]
        tag[t] = v
    w, h, spp, off = tag[0x0100], tag[0x0101], tag[0x0115], tag[0x0111]
    px = np.frombuffer(d, dtype=np.uint8, count=w * h * spp, offset=off)
    return px.reshape(h, w, spp)[:, :, :3], off


def write_tif(path, img, ref_header):
    """把参考 TIFF 的 332 字节头照抄，只改宽高和字节数，再追加像素。"""
    h, w = img.shape[:2]
    hdr = bytearray(ref_header)
    struct.pack_into("<H", hdr, 0x16 + 8, w)          # ImageWidth
    struct.pack_into("<H", hdr, 0x22 + 8, h)          # ImageLength
    struct.pack_into("<I", hdr, 0x72 + 8, h)          # RowsPerStrip
    struct.pack_into("<I", hdr, 0x76 + 8, w * h * 3)  # StripByteCounts
    with open(path, "wb") as f:
        f.write(bytes(hdr))
        f.write(img.tobytes())
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default=r"C:\ok3dtemp")
    ap.add_argument("--ref", required=True, help="同一次运行的厂商 TIFF")
    ap.add_argument("--n", type=int, default=11)
    ap.add_argument("--p", type=int, default=11)
    ap.add_argument("--out", default=None)
    ap.add_argument("--invert", choices=["auto", "yes", "no"], default="auto")
    ap.add_argument("--src", choices=["bmp", "vwd"], default="bmp")
    args = ap.parse_args()

    ref, off = load_tif_rgb(args.ref)
    oh, ow = ref.shape[:2]
    print("厂商 TIFF: %dx%d (像素起点 %d)" % (ow, oh, off))
    imgs, paths = load_views(args.views, args.n, args.src)
    if args.src == "vwd":
        print("视图: %d 张 vwd，%dx%d，第一张=%s" % (len(imgs), imgs[0][1], imgs[0][2], os.path.basename(paths[0])))
    else:
        print("视图: %d 张 bmp，%dx%d，第一张=%s" % (
            len(imgs), imgs[0].shape[1], imgs[0].shape[0], os.path.basename(paths[0])))

    combos = []
    inv_opts = [True, False] if args.invert == "auto" else [args.invert == "yes"]
    for inv in inv_opts:
        for rev in (False, True):
            out = interlace(imgs, ow, oh, args.p, inv, rev, args.src)
            d = float(np.abs(out.astype(np.int16) - ref.astype(np.int16)).mean())
            combos.append((d, inv, rev, out))
    combos.sort(key=lambda x: x[0])
    for d, inv, rev, _ in combos:
        print("  invert=%-5s reverse=%-5s  mean|diff| = %.3f" % (inv, rev, d))

    d, inv, rev, best = combos[0]
    print("\n最好组合：invert=%s reverse=%s，平均差 %.3f/255" % (inv, rev, d))
    # 相位分布：看差异是不是集中在柱镜边界
    col = np.abs(best.astype(np.int16) - ref.astype(np.int16)).mean(axis=(0, 2))
    print("按柱镜相位（x %% %d）的差异：" % args.p)
    for p in range(args.p):
        print("   phase %2d : %.2f" % (p, col[p::args.p].mean()))
    if args.out:
        hdr = open(args.ref, "rb").read(off)
        write_tif(args.out, best, hdr)
        print("\n已写出 %s（%d 字节）" % (args.out, os.path.getsize(args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
