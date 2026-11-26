# -*- coding: utf-8 -*-
"""逐个开启 ini 功能，定位哪个会破坏"打开工程"。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

FEATURES = ['native_psd', 'inject_x2', 'gxwj', 'fix_cancel', 'layers_up']
INI = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\psdto3d_green.ini'
PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'
PSD_OPEN = r'C:\bio\a.tw3d2'


def write_ini(on):
    lines = ['[green]']
    for f in FEATURES:
        lines.append('%s=%d' % (f, 1 if f in on else 0))
    for extra in ('psd_limit', 'psd_build', 'cn_ui', 'cn_native'):
        lines.append('%s=0' % extra)
    io.open(INI, 'wb').write(('\r\n'.join(lines) + '\r\n').encode('gbk'))


def try_open():
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    io.open(os.path.join(PKG, '_dlgopen.txt'), 'w').write(PSD_OPEN + '\n')
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
    while time.time() - t0 < 15:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:50] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.4)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return err, (title[0] if title else '')


def main():
    for f in FEATURES:
        write_ini({f})
        err, title = try_open()
        print('%-12s 弹框=%-22s 标题=%s' % (f, (err or '无')[:22], title))
    return 0


if __name__ == '__main__':
    sys.exit(main())
