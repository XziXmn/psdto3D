"""从运行中的主窗口读出菜单树：每项的 命令号(WM_COMMAND id) 和 标题。

Delphi 的 TMainMenu 会建真实的 HMENU，项 id 就是点菜单时发的 WM_COMMAND 号，
所以 GetMenuItemID / GetMenuString 能给出权威映射。

    python tools/menu_ids.py <pkg> [--exe psdto3d101.exe]
"""
import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32
k = ctypes.windll.kernel32
u.GetMenu.restype = wintypes.HANDLE
u.GetSubMenu.restype = wintypes.HANDLE
u.GetMenuItemCount.argtypes = [wintypes.HANDLE]
u.GetMenuItemID.argtypes = [wintypes.HANDLE, ctypes.c_int]
u.GetMenuStringA.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPSTR,
                             ctypes.c_int, wintypes.UINT]


def text_of(hmenu, idx):
    buf = ctypes.create_string_buffer(256)
    n = u.GetMenuStringA(hmenu, idx, buf, 256, 0x400)  # MF_BYPOSITION
    return buf.value.decode('gbk', 'replace') if n else ''


def walk(hmenu, depth=0, maxdepth=2):
    if not hmenu or depth > maxdepth:
        return
    cnt = u.GetMenuItemCount(hmenu)
    for i in range(cnt):
        sub = u.GetSubMenu(hmenu, i)
        mid = u.GetMenuItemID(hmenu, i)
        cap = text_of(hmenu, i)
        print('%s%-6s %-22r %s' % ('  ' * depth, mid, cap, '[sub]' if sub else ''))
        if sub:
            walk(sub, depth + 1, maxdepth)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg')
    ap.add_argument('--exe', default='psdto3d101.exe')
    a = ap.parse_args()
    pkg = os.path.abspath(a.pkg)
    import dialogless_launch
    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg, '', '')
    pid = rep['pid']
    hwnd = None
    for _ in range(60):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)
    print('hwnd', hwnd)
    if not hwnd:
        return 1
    m = u.GetMenu(ctypes.c_void_p(hwnd))
    print('menu', m)
    walk(m)
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
