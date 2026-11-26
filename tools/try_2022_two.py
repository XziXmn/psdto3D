# -*- coding: utf-8 -*-
"""2022 版：用真实对话框分别打开 32 层 / 50 层工程，对比结果并截图。"""
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


def close_reg(pid):
    for h, cls, t, v in win.windows(pid):
        if cls in ('TForm3', 'TRegform'):
            u.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)


def set_file(dlg, path):
    # 直接给对话框发 WM_SETTEXT 到所有 Edit，再点 IDOK
    edits = [h for h, cls, txt in win.children(dlg, 4) if cls == 'Edit']
    for e in edits:
        u.SendMessageW(ctypes.c_void_p(e), 0x000C, 0, ctypes.c_wchar_p(path))
    time.sleep(0.3)
    u.PostMessageW(ctypes.c_void_p(dlg), 0x0111, 1, 0)
    return len(edits)


def run(project, tag):
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    proc = sp.Popen([os.path.join(PKG, 'psdto3d101.exe')], cwd=PKG)
    pid = proc.pid
    time.sleep(6)
    close_reg(pid)
    time.sleep(1.5)
    hwnd = [h for h, c, t, v in win.windows(pid) if c == 'TForm1'][0]
    win.command(hwnd, 3)
    time.sleep(2.5)
    d = [h for h, c, t, v in win.windows(pid) if v and c == '#32770']
    if not d:
        print(tag, '没等到对话框')
        sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return
    n = set_file(d[0], project)
    print('%s 设置编辑框 %d 个' % (tag, n))

    err = ''
    t0 = time.time()
    while time.time() - t0 < 20:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm') and h != d[0]:
                kids = [k[2][:50] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                err = kids[0] if kids else '(dialog)'
                capture(h, r'C:\Home\Workspace\UGit\psdto\_work\dlg2022_%s.png' % tag)
                break
        if err:
            break
        time.sleep(0.5)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    still = [h for h, c, t, v in win.windows(pid) if v and c == '#32770']
    print('%s 结果=%s 对话框还在=%s 标题=%s' % (tag, err or '无弹框', bool(still), title))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def main():
    run(r'C:\bio\step_2_marker.tw3d2', '32层可开')
    run(r'C:\Home\Workspace\UGit\psdto\_work\2022ok\test50.tw3d2', '50层')
    return 0


if __name__ == '__main__':
    sys.exit(main())
