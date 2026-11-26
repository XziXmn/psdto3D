"""量"每个切块在整幅视图里的位置"：把 <层>gx<视图>.gjs 和 vwd<视图>.gjs 做
归一化互相关（FFT），找峰值偏移。

目的：确认 bmptotiff 的合成规则是不是"每层每视图贴一次、只有整数偏移"。
如果每层都能找到一个尖峰（NCC 很高），那自己写合成器就是可行的。

    python tools/tile_offset.py --kde C:\\ok3dtemp --view 1 --layers 1,2,3
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image


def load_vwd(path, scale=4):
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
    img = px.reshape(h, w, spp)[:, :, :3]
    im = Image.fromarray(img, "RGB")
    if scale > 1:
        im = im.resize((w // scale, h // scale), Image.BILINEAR)
    return np.asarray(im).astype(np.float32)


def load_bmp(path, scale=4):
    im = Image.open(path).convert("RGB")
    if scale > 1:
        im = im.resize((im.width // scale, im.height // scale), Image.BILINEAR)
    return np.asarray(im).astype(np.float32)


def ncc_offset(big, tmpl):
    """返回 (dy, dx, 峰值) —— tmpl 贴在 big 里的位置（big 坐标，可为负）。"""
    B = big.mean(axis=2)
    T = tmpl.mean(axis=2)
    T = T - T.mean()
    th, tw = T.shape
    if th > B.shape[0] or tw > B.shape[1]:
        return None
    fh, fw = B.shape[0] + th, B.shape[1] + tw
    FB = np.fft.rfft2(B, (fh, fw))
    FT = np.fft.rfft2(T[::-1, ::-1], (fh, fw))
    corr = np.fft.irfft2(FB * FT, (fh, fw))
    # 归一化分母：局部能量
    ones = np.ones_like(T)
    F1 = np.fft.rfft2(B * B, (fh, fw))
    F2 = np.fft.rfft2(ones, (fh, fw))
    local = np.fft.irfft2(F1 * F2, (fh, fw))
    # corr 的索引：峰值在 (dy, dx) 表示 T 的左上角贴在 B 的 (dy, dx)
    corr = corr[:B.shape[0], :B.shape[1]]
    local = local[:B.shape[0], :B.shape[1]]
    denom = np.sqrt(np.maximum(local, 1e-6) * float((T * T).sum()))
    ncc = corr / denom
    idx = np.unravel_index(np.argmax(ncc), ncc.shape)
    return idx[0], idx[1], float(ncc[idx])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kde", default=r"C:\ok3dtemp")
    ap.add_argument("--view", type=int, default=1)
    ap.add_argument("--layers", default="1,2,3,4,5")
    ap.add_argument("--scale", type=int, default=4)
    a = ap.parse_args()
    vwd = os.path.join(a.kde, "vwd%03d.gjs" % a.view)
    if not os.path.exists(vwd):
        raise SystemExit("缺 %s" % vwd)
    B = load_vwd(vwd, a.scale)
    print("vwd%03d -> %dx%d (1/%d)" % (a.view, B.shape[1], B.shape[0], a.scale))
    print("%-6s %-12s %-14s %s" % ("层", "切块(1/%d)" % a.scale, "位置(原图坐标)", "NCC"))
    for lay in [int(x) for x in a.layers.split(",") if x]:
        p = os.path.join(a.kde, "%dgx%d.gjs" % (lay, a.view))
        if not os.path.exists(p):
            print("%-6d 缺文件" % lay)
            continue
        T = load_bmp(p, a.scale)
        r = ncc_offset(B, T)
        if not r:
            print("%-6d 切块比画布大，跳过（%dx%d）" % (lay, T.shape[1], T.shape[0]))
            continue
        dy, dx, peak = r
        print("%-6d %-12s (%5d,%5d) -> %s" % (
            lay, "%dx%d" % (T.shape[1], T.shape[0]), dx, dy,
            "尖峰 %.3f" % peak if peak > 0.5 else "峰弱 %.3f" % peak))
    return 0


if __name__ == "__main__":
    sys.exit(main())
