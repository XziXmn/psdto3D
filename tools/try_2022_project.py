# -*- coding: utf-8 -*-
"""在 2022 版里通过真实文件对话框打开 50 层工程，看它报什么。"""
import ctypes
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win
from winshot import capture

u = ctypes.windll.user32
PKG = r'C:\Home\Workspace\UGit\psdto\_work\2022ok'
TARGET = r'C:\Home\Workspace\UGit\psdto\_work\2022ok\test50.tw3d2'


def fill_dialog(dlg, path):
    """把文件名填进去并点打开"""
    edits = []
    combos = []
    for h, cls, txt in win.children(dlg, 4):
        if cls == 'Edit':
            edits.append(h)
        if cls == 'ComboBox':
            combos.append(h)
    target = None
    # ComboBox 里的 Edit 是文件名框（Ex请参见：文件对话框的文件名框通常是 ComboBox 内嵌 Edit）
    for cb in combos:
        for h, cls, txt in win.children(cb, 2):
            if cls == 'Edit':
                target = h
    if target is None and edits:
        target = edits[-1]
    if target is None:
        return False
    u.SetWindowTextW(ctypes.c_void_p(target), ctypes.c_wchar_p(path))
    time.sleep(0.4)
    # 点"打开"
    for h, cls, txt in win.children(dlg, 3):
        if cls == 'Button' and txt and ('打开' in txt or 'Open' in txt or '&O' in txt):
            u.SendMessageW(ctypes.c_void_p(h), 0x00F5, 0, 0)   # BM_CLICK
            return True
    u.PostMessageW(ctypes.c_void_p(dlg), 0x0111, 1, 0)           # IDOK
    return True


def main():
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    proc = sp.Popen([os.path.join(PKG, 'psdto3d101.exe')], cwd=PKG)
    pid = proc.pid
    time.sleep(6)
    for h, cls, t, v in win.windows(pid):
        if cls in ('TForm3', 'TRegform'):
            u.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
    time.sleep(2)
    hwnd = [h for h, c, t, v in win.windows(pid) if c == 'TForm1'][0]
    win.command(hwnd, 3)
    time.sleep(2.5)

    dlg = None
    for i in range(20):
        d = [h for h, c, t, v in win.windows(pid) if v and c == '#32770']
        if d:
            dlg = d[0]
            break
        time.sleep(0.5)
    if not dlg:
        print('没等到文件对话框')
        return 1
    print('填文件名 ->', TARGET)
    print('fill ok:', fill_dialog(dlg, TARGET))

    err = ''
    t0 = time.time()
    while time.time() - t0 < 25:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm') and h != dlg:
                kids = [k[2][:60] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                err = kids[0] if kids else '(dialog)'
                capture(h, r'C:\Home\Workspace\UGit\psdto\_work\dlg2022b.png')
                break
        if err:
            break
        time.sleep(0.6)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    print('结果:', err if err else '无弹框')
    print('标题:', title)
    print('alive:', proc.poll() is None)
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
