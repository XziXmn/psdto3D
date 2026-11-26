# -*- coding: utf-8 -*-
"""打开文件对话框截图（验证过滤器是否含 .gxwj）。"""
import ctypes
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win
from winshot import capture


def main():
    pkg = os.path.abspath(sys.argv[1])
    out = sys.argv[2]
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    time.sleep(2)
    win.command(hwnd, 3)
    time.sleep(2.5)
    dlg = [h for h, cls, t, vis in win.windows(pid) if vis and cls == '#32770']
    if dlg:
        print('dialog size', capture(dlg[0], out))
    else:
        print('no dialog')
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)


if __name__ == '__main__':
    main()
