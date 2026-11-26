"""Dump a Delphi app menu three levels deep (top -> submenu -> Languages ...)."""
import ctypes
import sys

import win

u = ctypes.windll.user32
u.GetMenu.restype = ctypes.c_void_p


def dump(menu, depth=0, maxdepth=3):
    n = u.GetMenuItemCount(ctypes.c_void_p(menu))
    for i in range(n):
        buf = ctypes.create_unicode_buffer(256)
        u.GetMenuStringW(ctypes.c_void_p(menu), i, buf, 256, 0x400)
        mid = u.GetMenuItemID(ctypes.c_void_p(menu), i)
        print('%s[%d] id=%-6s %r' % ('  ' * depth, i, mid, buf.value))
        if depth < maxdepth:
            sub = u.GetSubMenu(ctypes.c_void_p(menu), i)
            if sub:
                dump(sub, depth + 1, maxdepth)


def main():
    pid = int(sys.argv[1])
    mw = [w for w in win.windows(pid) if w[1].startswith('TForm')]
    if not mw:
        print('no form window')
        return 1
    menu = u.GetMenu(ctypes.c_void_p(mw[0][0]))
    dump(menu)
    return 0


if __name__ == '__main__':
    sys.exit(main())
