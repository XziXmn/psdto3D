# -*- coding: utf-8 -*-
"""验证假设：第 1 行第 3 个字段 = 角度表行数。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'
CONV = os.path.join(PKG, '_gxwj_conv.tw3d2')
NEWPSD = r'C:\bio\x.psd'


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
                kids = [k[2][:40] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.4)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return err, (title[0] if title else '')


def main():
    conv = io.open(CONV, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    print('原第 1 行:', conv[1])
    cases = {
        'n50': '  2.40000000000000E+0001 13 50  1.00000000000000E+0000',
        'n0':  '  2.40000000000000E+0001 13 0  1.00000000000000E+0000',
        'n13': '  2.40000000000000E+0001 13 13  1.00000000000000E+0000',
    }
    for name, l1 in cases.items():
        d = list(conv)
        d[0] = NEWPSD
        d[1] = l1
        p = r'C:\bio\ang_%s.tw3d2' % name
        io.open(p, 'wb').write('\r\n'.join(d).encode('gbk', errors='replace'))
        err, title = test(p)
        print('%-6s %-52s -> %-26s | %s' % (name, l1.strip()[:52], (err or 'OK')[:26], title))
    return 0


if __name__ == '__main__':
    sys.exit(main())
