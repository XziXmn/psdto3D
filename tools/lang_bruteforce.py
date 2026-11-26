"""Brute-force: post WM_COMMAND ids that have no visible menu item (e.g. a hidden
Languages submenu) and report which one turns the captions Chinese."""
import ctypes
import subprocess as sp
import sys
import time

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import win

u = ctypes.windll.user32
u.GetMenu.restype = ctypes.c_void_p


def captions(hwnd):
    menu = u.GetMenu(ctypes.c_void_p(hwnd))
    out = []
    for i in range(u.GetMenuItemCount(ctypes.c_void_p(menu))):
        buf = ctypes.create_unicode_buffer(64)
        u.GetMenuStringW(ctypes.c_void_p(menu), i, buf, 64, 0x400)
        out.append(buf.value)
    return out


def is_chinese(s):
    return any('\u4e00' <= ch <= '\u9fff' for ch in s)


def main():
    pkg, exe = sys.argv[1], sys.argv[2]
    lo, hi = int(sys.argv[3]), int(sys.argv[4])
    proc = sp.Popen([pkg + '\\' + exe], cwd=pkg)
    time.sleep(5)
    pid = proc.pid
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    base = captions(hwnd)
    print('baseline:', base)
    hits = []
    for cmd in range(lo, hi + 1):
        win.command(hwnd, cmd)
        time.sleep(0.35)
        caps = captions(hwnd)
        if any(is_chinese(c) for c in caps):
            hits.append((cmd, caps))
            print('HIT cmd=%d -> %s' % (cmd, caps))
    print('hits:', [h[0] for h in hits])
    proc.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())
