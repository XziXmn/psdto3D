# -*- coding: utf-8 -*-
"""把若干 PSD 逐个导入程序，报告成功/失败与失败原因。"""
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win


def try_one(pkg, psd):
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    open(os.path.join(pkg, '_dlgopen.txt'), 'w').write(psd + '\n')
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    time.sleep(1.5)
    win.command(hwnd, 7)
    msg = ''
    for _ in range(40):
        time.sleep(0.5)
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('TMessageForm', '#32770'):
                kids = [k[2][:70] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                msg = kids[0] if kids else '(dialog)'
                break
        if msg:
            break
    title = [t for h, cls, t, vis in win.windows(pid) if h == hwnd]
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return msg, (title[0] if title else '')


def main():
    pkg = os.path.abspath(sys.argv[1])
    for psd in sys.argv[2:]:
        msg, title = try_one(pkg, psd)
        ok = 'OK  ' if not msg else 'FAIL'
        print('%-28s %s title=%r %s' % (os.path.basename(psd), ok, title, msg[:70]))


if __name__ == '__main__':
    main()
