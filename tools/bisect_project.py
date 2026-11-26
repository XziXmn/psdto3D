# -*- coding: utf-8 -*-
"""二分定位：把工程截断到 N 行，看程序从第几行开始报 Invalid numeric input。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'
SRC = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\_gxwj_conv.tw3d2'


def make(n, path):
    data = io.open(SRC, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    io.open(path, 'wb').write('\r\n'.join(data[:n]).encode('gbk', errors='replace'))


def test(path):
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    io.open(os.path.join(PKG, '_dlgopen.txt'), 'wb').write((path + '\r\n').encode('gbk'))
    proc = sp.Popen([os.path.join(PKG, 'psdto3d101.exe')], cwd=PKG)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    time.sleep(1.5)
    win.command(hwnd, 3)
    err = ''
    t0 = time.time()
    while time.time() - t0 < 12:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:50] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.4)
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return err


def main():
    tmp = r'C:\bio\trunc.tw3d2'
    for n in (8, 60, 120, 200, 400, 700, 1000):
        make(n, tmp)
        err = test(tmp)
        print('%5d 行 -> %s' % (n, err if err else 'OK'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
