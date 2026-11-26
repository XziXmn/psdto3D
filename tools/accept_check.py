"""验收：把一份产出的 PSD 和实机参照逐层比画面，给出 PASS/FAIL。

判据（不是文件大小，是画面）：
  · 层数、每层尺寸必须一致
  · 每层平均绝对差 <= --mean（默认 4.0）
  · alpha 平均绝对差 <= 1.0
  · 中心层（views//2）平均绝对差 <= 0.5（这一步是"内容对不对"的硬指标）

    python tools/accept_check.py REF.psd OUT.psd [--mean 4.0] [--center 0.5]
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psdlayers import layer_img, parse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("out")
    ap.add_argument("--mean", type=float, default=4.0)
    ap.add_argument("--center", type=float, default=0.5)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    R = parse(a.ref)
    O = parse(a.out)
    fails = []
    if len(R["layers"]) != len(O["layers"]):
        fails.append("层数 %d != %d" % (len(R["layers"]), len(O["layers"])))
    if (R["w"], R["h"]) != (O["w"], O["h"]):
        fails.append("画布 %dx%d != %dx%d" % (R["w"], R["h"], O["w"], O["h"]))

    rows = []
    n = min(len(R["layers"]), len(O["layers"]))
    center = n // 2
    for i in range(n):
        lr, lo = R["layers"][i], O["layers"][i]
        if (lr["w"], lr["h"]) != (lo["w"], lo["h"]):
            fails.append("第 %d 层尺寸 %dx%d != %dx%d" % (
                i, lr["w"], lr["h"], lo["w"], lo["h"]))
            continue
        rr, ra = layer_img(R, i)
        ro, oa = layer_img(O, i)
        d = float(np.abs(rr.astype(np.int16) - ro.astype(np.int16)).mean())
        da = float(np.abs(ra.astype(np.int16) - oa.astype(np.int16)).mean())
        rows.append((i, lr["name"], d, da))
        if lr["name"] != lo["name"]:
            fails.append("第 %d 层名 %r != %r" % (i, lr["name"], lo["name"]))
        if d > a.mean:
            fails.append("第 %d 层画面差 %.3f > %.1f" % (i, d, a.mean))
        if da > a.alpha:
            fails.append("第 %d 层 alpha 差 %.3f > %.1f" % (i, da, a.alpha))
        if i == center and d > a.center:
            fails.append("中心层画面差 %.3f > %.1f（内容不一致）" % (d, a.center))

    print("%-4s %-10s %8s %8s" % ("#", "layer", "mean", "alpha"))
    for i, name, d, da in rows:
        mark = " <-中心" if i == center else ""
        print("%-4d %-10s %8.3f %8.3f%s" % (i, name, d, da, mark))

    import json
    res = {"ref": a.ref, "out": a.out, "passed": not fails,
           "layers": [[i, nm, round(d, 3), round(da, 3)] for i, nm, d, da in rows],
           "fails": fails}
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print()
    if fails:
        print("FAIL（%d 条）" % len(fails))
        for f in fails[:12]:
            print("  ·", f)
        return 1
    print("PASS：与参照逐层一致（阈值 mean<=%.1f center<=%.1f alpha<=%.1f）"
          % (a.mean, a.center, a.alpha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
