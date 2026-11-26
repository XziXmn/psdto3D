# -*- coding: utf-8 -*-
"""探测 99 版的打开对话框结构，找出文件名输入框。"""
import ctypes
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32
PKG = r'C:\Home\Workspace\UGit\psdto\_work\99test'


def walk(hwnd, depth=0, out=None):
    if out is None:
        out = []
    buf = ctypes.create_unicode_buffer(256)
    cls = ctypes.create_unicode_buffer(128)
    u.GetClassNameW(ctypes.c_void_p(hwnd), cls, 128)
    u.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 256)
    out.append(('  ' * depth) + '%s [%s] %r' % (hex(hwnd), cls.value, buf.value[:40]))
    child = u.GetWindow(ctypes.c_void_p(hwnd), 5)  # GW_CHILD
    while child:
        walk(child, depth + 1, out)
        child = u.GetWindow(ctypes.c_void_p(child), 2)  # GW_HWNDNEXT
    return out


def main():
    sp.run(['taskkill', '/IM', 'psdto3d.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    proc = sp.Popen([os.path.join(PKG, 'psdto3d.exe')], cwd=PKG)
    pid = proc.pid
    time.sleep(7)
    hwnd = [h for h, c, t, v in win.windows(pid) if c == 'TForm1'][0]
    # 99 版的"打开工程"菜单序号需要试：先打印菜单项
    for cmd in (2, 3, 4):
        win.command(hwnd, cmd)
        time.sleep(2)
        d = [h for h, c, t, v in win.windows(pid) if v and c == '#32770']
        if d:
            print('菜单 %d 弹出对话框' % cmd)
            for line in walk(d[0]):
                print(line)
            break
        else:
            print('菜单 %d -> 标题 %s' % (cmd, [t for h, c, t, v in win.windows(pid) if h == hwnd]))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
