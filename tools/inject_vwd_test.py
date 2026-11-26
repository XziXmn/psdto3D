"""验证假设：`输出PSD` 是不是直接读 C:\\ok3dtemp\\vwd*.gjs。

做法：带狗跑 7 -> 10 -> 12 -> 13 -> 16（这一步会生成 vwd001..011），
然后**把 vwd001 整张涂成纯色**，再发 17（输出PSD）。
最后检查产出 PSD 的第 1 层是不是纯色：
   是  -> PSD 写出确实读盘上的 vwd，我们就可以自己造视图喂它
   否  -> PSD 走的是内存里的画布，得换思路

    python tools/inject_vwd_test.py --pkg _review/pkgA --psd X.psd --settings Y.tw3d2 --out DIR
"""
import argparse
import ctypes
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['NODLGPATCH'] = '1'

import dialogless_launch
import win

KDE = r'C:\ok3dtemp'


def fill_vwd(path, rgb=(0, 255, 0)):
    """把 vwd 的像素区整片涂成 rgb（保持原 332 字节头）。"""
    with open(path, "r+b") as f:
        d = f.read(2048)
        ifd = struct.unpack_from("<I", d, 4)[0]
        n = struct.unpack_from("<H", d, ifd)[0]
        tag = {}
        for i in range(n):
            t, typ, cnt = struct.unpack_from("<HHI", d, ifd + 2 + 12 * i)
            raw = d[ifd + 2 + 12 * i + 8: ifd + 2 + 12 * i + 12]
            v = struct.unpack("<H", raw[:2])[0] if (typ == 3 and cnt == 1) else struct.unpack("<I", raw)[0]
            tag[t] = v
        w, h, spp, off = tag[0x100], tag[0x101], tag[0x115], tag[0x111]
        px = bytes(rgb) * (w * h)
        f.seek(off)
        f.write(px)
    return w, h, spp, off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--psd", required=True)
    ap.add_argument("--settings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exe", default="psdto3d101.exe")
    ap.add_argument("--fill", default="0,255,0")
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    outd = os.path.abspath(a.out)
    os.makedirs(outd, exist_ok=True)
    out_tif = os.path.join(outd, "out.tif")
    out_psd = os.path.join(outd, "out.psd")
    for p in (out_tif, out_psd):
        if os.path.exists(p):
            os.remove(p)
    if os.path.isdir(KDE):
        for f in os.listdir(KDE):
            try:
                os.remove(os.path.join(KDE, f))
            except OSError:
                pass

    psd = os.path.abspath(a.psd)
    sett = os.path.abspath(a.settings)
    with open(os.path.join(pkg, "_dlgopen.txt"), "wb") as f:
        f.write((psd + "\r\n").encode("gbk", "ignore"))
        f.write((sett + "\r\n").encode("gbk", "ignore"))
        f.write((psd + "\r\n").encode("gbk", "ignore"))
    with open(os.path.join(pkg, "_dlgsave.txt"), "wb") as f:
        f.write((out_tif + "\r\n").encode("gbk", "ignore"))
        f.write((out_psd + "\r\n").encode("gbk", "ignore"))

    for name in ("_dongle.log", "_dlgonly.txt"):
        p = os.path.join(pkg, name)
        if os.path.exists(p):
            os.remove(p)

    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg, psd, out_tif)
    pid = rep["pid"]
    hwnd = None
    for _ in range(60):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1' and w[3]]
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)
    if not hwnd:
        print(json.dumps({"error": "no main window"}, ensure_ascii=False))
        return 1

    BTN = ('ok', '确定', '是', 'yes', 'close', '关闭')
    IGNORE = {'TForm1', 'TApplication', 'TAboutBox', 'TPUtilWindow', 'ComboLBox',
              'IME', 'MSCTFIME UI', 'THintWindow'}
    seen = set()
    log = {"steps": [], "fills": [], "dialogs": []}
    rgb = tuple(int(x) for x in a.fill.split(","))

    t0 = time.time()
    plan = [(12, 7), (44, 10), (74, 12), (180, 13), (196, 16), (250, 17)]
    i = 0
    filled = False
    while time.time() - t0 < 340:
        el = time.time() - t0
        if i < len(plan) and el >= plan[i][0]:
            cmd = plan[i][1]
            win.command(hwnd, cmd)
            log["steps"].append({"t": round(el, 1), "cmd": cmd})
            i += 1
        # 在 16 完成之后、17 之前注入
        if not filled and 215 <= el <= 248:
            p = os.path.join(KDE, "vwd001.gjs")
            if os.path.exists(p):
                info = fill_vwd(p, rgb)
                log["fills"].append({"t": round(el, 1), "file": p, "geom": info,
                                     "rgb": rgb, "size": os.path.getsize(p)})
                filled = True
                time.sleep(2)
        for h, cls, title, vis in win.windows(pid):
            if not vis or cls in IGNORE or h in seen:
                continue
            try:
                kids = win.children(h, 3)
            except Exception:
                kids = []
            btns = [(kh, kcls, ktxt) for kh, kcls, ktxt in kids if kcls in ('TButton', 'Button')]
            log["dialogs"].append({"t": round(el, 1), "cls": cls,
                                   "buttons": [b[2] for b in btns]})
            seen.add(h)
            for kh, kcls, ktxt in btns:
                if (ktxt or "").strip().lower() in BTN:
                    win.click(kh)
                    break
        time.sleep(0.15)

    for tag, p in (("tif", out_tif), ("psd", out_psd)):
        if os.path.exists(p):
            log[tag] = {"size": os.path.getsize(p)}
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    with open(os.path.join(outd, "report.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(json.dumps(log, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
