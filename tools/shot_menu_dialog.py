# -*- coding: utf-8 -*-
"""给指定菜单弹出的文件对话框截图（检查过滤器）。"""
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
    cmd = int(sys.argv[3]) if len(sys.argv) > 3 else 10
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
    win.command(hwnd, cmd)
    time.sleep(2.5)
    dlg = [h for h, cls, t, vis in win.windows(pid) if vis and cls == '#32770']
    if dlg:
        print('dialog size', capture(dlg[0], out))
        for h, cls, t, vis in win.windows(pid):
            if h == dlg[0]:
                for kh, kcls, ktxt in win.children(h, 4):
                    if ktxt and ktxt.strip():
                        print('  %-12s %s' % (kcls, ktxt.strip()[:60]))
    else:
        print('no dialog')
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)


if __name__ == '__main__':
    main()
