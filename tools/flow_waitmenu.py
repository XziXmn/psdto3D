"""Chain the imports/preview, wait until a chosen export menu turns enabled, then send it.

    python tools/flow_waitmenu.py --pkg _work/emu1 --menu 18 --out C:\\bio\\out.gif
"""
import argparse
import ctypes
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32
u.GetMenu.restype = ctypes.c_void_p
u.GetSubMenu.restype = ctypes.c_void_p
u.GetSubMenu.argtypes = [ctypes.c_void_p, ctypes.c_uint]


def menu_state(hwnd, mid):
    top = u.GetMenu(ctypes.c_void_p(hwnd))
    n = u.GetMenuItemCount(ctypes.c_void_p(top))
    for i in range(n):
        sub = u.GetSubMenu(ctypes.c_void_p(top), i)
        if not sub:
            continue
        for j in range(u.GetMenuItemCount(ctypes.c_void_p(sub))):
            if u.GetMenuItemID(ctypes.c_void_p(sub), j) == mid:
                return u.GetMenuState(ctypes.c_void_p(sub), j, 0x400)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--menu', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--wait', type=float, default=180)
    ap.add_argument('--tail', type=float, default=120)
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(0.5)
    if os.path.exists(a.out):
        os.remove(a.out)
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    if not hwnd:
        print('no window')
        return 1

    t0 = time.time()
    sent = []
    deadline = t0 + a.wait
    enabled_at = None
    did = set()
    while time.time() < deadline:
        el = time.time() - t0
        if el >= 10 and '7' not in did:
            win.command(hwnd, 7); sent.append(('7', round(el, 1))); did.add('7')
        if el >= 45 and '10' not in did:
            win.command(hwnd, 10); sent.append(('10', round(el, 1))); did.add('10')
        if el >= 70 and '12' not in did:
            win.command(hwnd, 12); sent.append(('12', round(el, 1))); did.add('12')
        if el > 80:
            st = menu_state(hwnd, a.menu)
            if st is not None and (st & 0x3) == 0:
                if enabled_at is None:
                    enabled_at = round(el, 1)
                    win.command(hwnd, a.menu)
                    sent.append((str(a.menu), round(el, 1)))
                break
        for h, cls, title, vis in win.windows(pid):
            if vis and cls in ('TMessageForm', '#32770'):
                for kh, kcls, ktxt in win.children(h, 2):
                    if kcls in ('TButton', 'Button'):
                        win.click(kh)
                        break
        time.sleep(0.25)

    # give the export time to write
    t1 = time.time()
    while time.time() - t1 < a.tail:
        time.sleep(1)
        if os.path.exists(a.out) and os.path.getsize(a.out) > 0:
            pass

    ex = os.path.exists(a.out)
    print('sent=%s enabled_at=%s out=%s size=%s' % (sent, enabled_at, ex,
          os.path.getsize(a.out) if ex else 0))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
