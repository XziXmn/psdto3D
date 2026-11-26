# -*- coding: utf-8 -*-
"""逐个测不同层数 PSD 的导入与预览（新构建，不插狗）。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'


def run(psd, do_preview=True):
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp.run(['cmd', '/c', 'rd', '/s', '/q', r'C:\ok3dtemp'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    io.open(os.path.join(PKG, '_dlgopen.txt'), 'wb').write((psd + '\r\n').encode('gbk'))
    proc = sp.Popen([os.path.join(PKG, 'psdto3d101.exe')], cwd=PKG)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    if not hwnd:
        return ('启动失败', '', False)
    time.sleep(1.5)
    win.command(hwnd, 7)          # 导入 PSD
    imp_err = ''
    t0 = time.time()
    while time.time() - t0 < 25:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:36] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                imp_err = kids[0] if kids else '(dialog)'
                break
        if imp_err:
            break
        time.sleep(0.5)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    if imp_err or not do_preview:
        sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return (imp_err or 'OK', title[0] if title else '', proc.poll() is None)

    win.command(hwnd, 12)         # 预览
    pre_err = ''
    t0 = time.time()
    while time.time() - t0 < 60:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:36] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                pre_err = kids[0] if kids else '(dialog)'
                break
        if pre_err:
            break
        time.sleep(0.6)
    alive = proc.poll() is None
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return ('OK', pre_err or 'OK', alive)


def main():
    psds = sys.argv[1:]
    for psd in psds:
        name = os.path.basename(psd)
        imp, pre, alive = run(psd)
        print('%-10s 导入=%-28s 预览=%-28s 存活=%s' % (name, imp[:28], pre[:28], alive))
    return 0


if __name__ == '__main__':
    sys.exit(main())
