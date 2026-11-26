"""Dump every menu item (id / state / text) of the running app after a preview start."""
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


def walk(menu, depth, out):
    n = u.GetMenuItemCount(ctypes.c_void_p(menu))
    for i in range(n):
        buf = ctypes.create_unicode_buffer(128)
        u.GetMenuStringW(ctypes.c_void_p(menu), i, buf, 128, 0x400)
        mid = u.GetMenuItemID(ctypes.c_void_p(menu), i)
        st = u.GetMenuState(ctypes.c_void_p(menu), i, 0x400)
        out.append((depth, mid, st, buf.value))
        sub = u.GetSubMenu(ctypes.c_void_p(menu), i)
        if sub:
            walk(sub, depth + 1, out)


def main():
    pkg = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else r'_work/emu1')
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(0.5)
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    t0 = time.time()
    while time.time() - t0 < 130:
        el = time.time() - t0
        if abs(el - 10) < 0.3:
            win.command(hwnd, 7)
        if abs(el - 45) < 0.3:
            win.command(hwnd, 10)
        if abs(el - 70) < 0.3:
            win.command(hwnd, 12)
        time.sleep(0.2)

    out = []
    menu = u.GetMenu(ctypes.c_void_p(hwnd))
    walk(menu, 0, out)
    for depth, mid, st, txt in out:
        flag = 'enabled' if (st & 0x3) == 0 else ('grayed' if st & 0x1 else 'disabled')
        print('%s id=%-5d %-9s %s' % ('  ' * depth, mid, flag, txt))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
