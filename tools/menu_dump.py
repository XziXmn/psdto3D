"""Enumerate the menu commands of a running psdto3d window (class -> id -> caption)."""
import ctypes
import sys
from ctypes import wintypes

import win

u = ctypes.windll.user32


def menu_tree(hwnd):
    u.GetMenu.restype = ctypes.c_void_p
    menu = u.GetMenu(ctypes.c_void_p(hwnd))
    if not menu:
        return []
    n = u.GetMenuItemCount(ctypes.c_void_p(menu))
    out = []
    for i in range(n):
        buf = ctypes.create_unicode_buffer(128)
        u.GetMenuStringW(ctypes.c_void_p(menu), i, buf, 128, 0x400)
        out.append(('top', i, buf.value, None))
        sub = u.GetSubMenu(ctypes.c_void_p(menu), i)
        if sub:
            k = u.GetMenuItemCount(ctypes.c_void_p(sub))
            for j in range(k):
                b2 = ctypes.create_unicode_buffer(256)
                u.GetMenuStringW(ctypes.c_void_p(sub), j, b2, 256, 0x400)
                mid = u.GetMenuItemID(ctypes.c_void_p(sub), j)
                out.append(('item', (i, j), b2.value, mid))
    return out


def main():
    pid = int(sys.argv[1])
    mw = [w for w in win.windows(pid) if w[1].startswith('TForm')]
    if not mw:
        print('no form')
        return 1
    for row in menu_tree(mw[0][0]):
        print(row)
    return 0


if __name__ == '__main__':
    sys.exit(main())
