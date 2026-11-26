# -*- coding: utf-8 -*-
"""导入 + 预览 两步检查：对每个 PSD 报告 导入是否成功、预览是否报错。"""
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win


def run_one(pkg, psd):
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

    def dialogs():
        out = []
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('TMessageForm', '#32770'):
                kids = [k[2][:60] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                out.append(kids[0] if kids else '(dialog)')
        return out

    win.command(hwnd, 7)
    t0 = time.time()
    imp_err = ''
    while time.time() - t0 < 20:
        d = dialogs()
        if d:
            imp_err = d[0]
            break
        time.sleep(0.5)
    time.sleep(1)
    title = [t for h, cls, t, vis in win.windows(pid) if h == hwnd]
    imported = imp_err == '' and title and 'Psdto3d 101' not in (title[0] or '')

    prev_err = ''
    if imported:
        win.command(hwnd, 12)
        t0 = time.time()
        while time.time() - t0 < 40:
            d = dialogs()
            if d:
                prev_err = d[0]
                break
            time.sleep(0.5)

    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return imp_err, prev_err


def main():
    pkg = os.path.abspath(sys.argv[1])
    for psd in sys.argv[2:]:
        imp, prev = run_one(pkg, psd)
        print('%-14s 导入:%-28s 预览:%s'
              % (os.path.basename(psd), 'OK' if not imp else imp[:26],
                 'OK' if not prev else prev[:40]))


if __name__ == '__main__':
    main()
