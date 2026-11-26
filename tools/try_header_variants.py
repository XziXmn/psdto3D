# -*- coding: utf-8 -*-
"""测试：99 转换工程的第 1 行 / 第 7 行标志位改成 10.1 的写法，看哪个能让程序读下去。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'
BASE = os.path.join(PKG, '_gxwj_conv.tw3d2')

VARIANTS = {
    'orig':      (None, None),
    'line7_2':   (None, ' 1.00000000000000E+0004  1.00000000000000E+0001  1.20005000000000E+0001 2 2'),
    'line1_1113': ('  2.40000000000000E+0001 11 13  1.00000000000000E+0000', None),
    'both':      ('  2.40000000000000E+0001 11 13  1.00000000000000E+0000',
                  ' 1.00000000000000E+0004  1.00000000000000E+0001  1.20005000000000E+0001 2 2'),
}


def build(name, l1, l7):
    d = io.open(BASE, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    if l1:
        d[1] = l1
    if l7:
        d[7] = l7
    path = r'C:\bio\var_%s.tw3d2' % name
    io.open(path, 'wb').write('\r\n'.join(d).encode('gbk', errors='replace'))
    return path


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
                kids = [k[2][:44] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.4)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return err, (title[0] if title else '')


def main():
    for name, (l1, l7) in VARIANTS.items():
        p = build(name, l1, l7)
        err, title = test(p)
        print('%-12s -> %-24s | %s' % (name, (err or 'OK')[:24], title))
    return 0


if __name__ == '__main__':
    sys.exit(main())
