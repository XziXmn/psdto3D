"""验证一个猜想：vwd（印刷尺寸的一整张视图）是不是把 vw*.bmp（1200×1427 预览）
直接放大到 4370×5197 得来的——比例 4370/1200 = 3.6417 与 5197/1427 = 3.6419 几乎相同。

    python tools/vwd_check.py --kde C:\\ok3dtemp [--vwd 001]
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image


def load_vwd(path):
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
    return px.reshape(h, w, spp)[:, :, :3]


def load_bmp(path):
    im = Image.open(path).convert("RGB")
    return np.asarray(im)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kde", default=r"C:\ok3dtemp")
    ap.add_argument("--vwd", default="001")
    a = ap.parse_args()
    vwd_path = os.path.join(a.kde, "vwd%s.gjs" % a.vwd)
    if not os.path.exists(vwd_path):
        raise SystemExit("没有 %s" % vwd_path)
    V = load_vwd(vwd_path)
    H, W = V.shape[:2]
    print("vwd%s = %dx%d" % (a.vwd, W, H))

    res = []
    for i in range(1, 13):
        p = os.path.join(a.kde, "vw%d.bmp" % i)
        if not os.path.exists(p):
            continue
        B = load_bmp(p)
        for kname, k in (("NEAREST", Image.NEAREST), ("BILINEAR", Image.BILINEAR),
                         ("BICUBIC", Image.BICUBIC), ("LANCZOS", Image.LANCZOS)):
            up = np.asarray(Image.fromarray(B).resize((W, H), k))
            d = np.abs(up.astype(np.int16) - V.astype(np.int16)).mean()
            res.append((d, i, kname))
    res.sort()
    for d, i, k in res[:10]:
        print("  vw%-2d %-8s mean|diff| = %.3f" % (i, k, d))
    print()
    if res and res[0][0] < 2.0:
        print("→ 命中：vwd%s ≈ vw%d 放大（%s），差 %.3f" % (a.vwd, res[0][1], res[0][2], res[0][0]))
    else:
        print("→ 不是单纯放大（最好也只有 %.3f），需要按切块合成" % (res[0][0] if res else -1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
