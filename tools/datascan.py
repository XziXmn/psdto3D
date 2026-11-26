"""在预览前后快照 exe 的 .data/.bss，找出"因狗状态不同而不同"的全局。

思路：gx 切片两边全同，vw*.bmp 却不同 → 差异只可能来自某个进程内全局。
带狗跑一次、无狗跑一次，各在「预览完成」时快照 .data/.bss，
逐 dword 对比，差异集合就是候选授权状态。

用法：
    python tools/datascan.py --pkg _review/pkgA --tag A --cmds "7@12,10@44,12@74" --wait 78
    python tools/datascan.py --pkg _review/pkgB2 --tag B --cmds "7@12,10@44,12@74" --wait 78
    python tools/datascan.py --diff A B
"""
import argparse
import ctypes
import json
import os
import struct
import sys
import time
from ctypes import wintypes

import pefile

k32 = ctypes.windll.kernel32
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win


def sections_of(exe):
    pe = pefile.PE(exe, fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase
    out = []
    for s in pe.sections:
        nm = s.Name.rstrip(b"\0").decode(errors="ignore")
        if nm.upper() not in ("DATA", "BSS"):
            continue
        va = ib + s.VirtualAddress
        size = max(s.Misc_VirtualSize, s.SizeOfRawData)
        if size > 0x80000:
            size = 0x80000
        out.append((nm, va, size))
    pe.close()
    return out


def snapshot(pid, secs):
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)   # VM_READ | QUERY_INFO
    if not h:
        raise SystemExit("OpenProcess 失败 %s" % ctypes.WinError())
    res = {}
    for nm, va, size in secs:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if k32.ReadProcessMemory(h, ctypes.c_void_p(va), buf, size, ctypes.byref(got)):
            res["%s@%08X" % (nm, va)] = buf.raw[:got.value]
    k32.CloseHandle(h)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg")
    ap.add_argument("--exe", default="psdto3d101.exe")
    ap.add_argument("--tag")
    ap.add_argument("--cmds")
    ap.add_argument("--wait", type=float, default=78)
    ap.add_argument("--out", default="_review/datascan")
    ap.add_argument("--diff", nargs=2, metavar=("TAGA", "TAGB"))
    a = ap.parse_args()

    outdir = a.out
    os.makedirs(outdir, exist_ok=True)

    if a.diff:
        ta, tb = a.diff
        da = json.load(open(os.path.join(outdir, "%s.json" % ta), encoding="utf-8"))
        db = json.load(open(os.path.join(outdir, "%s.json" % tb), encoding="utf-8"))
        print("A=%s  B=%s" % (ta, tb))
        total = 0
        for k in sorted(set(da) & set(db)):
            ba = bytes.fromhex(da[k])
            bb = bytes.fromhex(db[k])
            n = min(len(ba), len(bb))
            diffs = []
            for off in range(0, n - 3, 4):
                va = int(k.split("@")[1], 16) + off
                x = struct.unpack_from("<I", ba, off)[0]
                y = struct.unpack_from("<I", bb, off)[0]
                if x != y:
                    diffs.append((va, x, y))
            if diffs:
                print("\n%s 段（%s）：%d 个 dword 不同" % (k.split("@")[0], k.split("@")[1], len(diffs)))
                for va, x, y in diffs[:60]:
                    print("   %08X  A=%08X(%d)  B=%08X(%d)" % (va, x, x, y, y))
                total += len(diffs)
        print("\n合计 %d 个 dword 不同" % total)
        return 0

    if not (a.pkg and a.tag):
        raise SystemExit("需要 --pkg 和 --tag")

    pkg = os.path.abspath(a.pkg)
    exe = os.path.join(pkg, a.exe)
    secs = sections_of(exe)
    print("监控段：", [(n, hex(v), s) for n, v, s in secs])

    # 起进程
    psd = os.path.abspath("_review/bio_ascii.psd")
    sett = os.path.abspath("_review/bio_ascii.tw3d2")
    with open(os.path.join(pkg, "_dlgopen.txt"), "wb") as f:
        f.write((psd + "\r\n").encode("gbk", "ignore"))
        f.write((sett + "\r\n").encode("gbk", "ignore"))
        f.write((psd + "\r\n").encode("gbk", "ignore"))

    os.environ["NODLGPATCH"] = "1"
    proc = __import__("subprocess").Popen([exe], cwd=pkg)
    time.sleep(1.0)
    pid = None
    for _ in range(40):
        try:
            ws = win.windows_by_pid = win.windows
            cand = [w for w in ws(proc.pid) if w[1] == "TForm1"]
            if cand:
                pid = proc.pid
                hwnd = cand[0][0]
                break
        except Exception:
            pass
        time.sleep(0.4)
    if pid is None:
        proc.kill()
        raise SystemExit("找不到主窗口")
    print("pid=%d hwnd=%d" % (pid, hwnd))

    sched = sorted((float(t), int(c)) for c, t in (x.split("@") for x in a.cmds.split(",")))
    t0 = time.time()
    nxt = 0
    while time.time() - t0 < a.wait:
        el = time.time() - t0
        if nxt < len(sched) and el >= sched[nxt][0]:
            win.command(hwnd, sched[nxt][1])
            print("  发命令 %d @%.1f" % (sched[nxt][1], el))
            nxt += 1
        try:
            for h, cls, title, vis in win.windows(pid):
                if vis and cls in ("#32770", "TMessageForm"):
                    for kh, kcls, ktxt in win.children(h, 3):
                        if kcls in ("TButton", "Button"):
                            win.click(kh)
                            break
        except Exception:
            pass
        time.sleep(0.2)

    snap = snapshot(pid, secs)
    if hasattr(win, "screenshot"):
        pass
    os.system("taskkill /PID %d /F >nul 2>&1" % pid)

    data = {k: v.hex() for k, v in snap.items()}
    p = os.path.join(outdir, "%s.json" % a.tag)
    json.dump(data, open(p, "w"), indent=0)
    print("已保存 %s（%d 段）" % (p, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
