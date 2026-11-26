# -*- coding: utf-8 -*-
"""99 版：把 50 层工程路径填进对话框并打开，看是否成功。"""
import ctypes
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win
from winshot import capture

u = ctypes.windll.user32
PKG = r'C:\Home\Workspace\UGit\psdto\_work\99test'


def find_edit_and_button(dlg):
    edit = None
    btn = None

    def walk(hwnd):
        nonlocal edit, btn
        cls = ctypes.create_unicode_buffer(128)
        u.GetClassNameW(ctypes.c_void_p(hwnd), cls, 128)
        c = cls.value
        if c == 'ComboBoxEx32' and edit is None:
            cb = u.GetWindow(ctypes.c_void_p(hwnd), 5)
            while cb:
                if ctypes.create_unicode_buffer(128):
                    pass
                u.GetClassNameW(ctypes.c_void_p(cb), cls, 128)
                if cls.value == 'ComboBox':
                    e = u.GetWindow(ctypes.c_void_p(cb), 5)
                    while e:
                        u.GetClassNameW(ctypes.c_void_p(e), cls, 128)
                        if cls.value == 'Edit':
                            edit = e
                            break
                        e = u.GetWindow(ctypes.c_void_p(e), 2)
                cb = u.GetWindow(ctypes.c_void_p(cb), 2)
        if c == 'Button':
            buf = ctypes.create_unicode_buffer(64)
            u.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 64)
            if '打开' in buf.value or 'Open' in buf.value:
                btn = hwnd
        child = u.GetWindow(ctypes.c_void_p(hwnd), 5)
        while child:
            walk(child)
            child = u.GetWindow(ctypes.c_void_p(child), 2)

    walk(dlg)
    return edit, btn


def main():
    sp.run(['taskkill', '/IM', 'psdto3d.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    proc = sp.Popen([os.path.join(PKG, 'psdto3d.exe')], cwd=PKG)
    pid = proc.pid
    time.sleep(7)
    hwnd = [h for h, c, t, v in win.windows(pid) if c == 'TForm1'][0]
    win.command(hwnd, 3)
    time.sleep(2.5)
    d = [h for h, c, t, v in win.windows(pid) if v and c == '#32770']
    if not d:
        print('没有对话框')
        return 1
    edit, btn = find_edit_and_button(d[0])
    print('edit=%s btn=%s' % (edit, btn))
    target = os.path.join(PKG, 'a99.gxwj')
    u.SendMessageA(ctypes.c_void_p(edit), 0x000C, 0, ctypes.c_char_p(target.encode('gbk')))
    time.sleep(0.5)
    buf = ctypes.create_string_buffer(300)
    u.GetWindowTextA(ctypes.c_void_p(edit), buf, 300)
    print('回读文件名:', buf.value.decode('gbk', 'replace'))
    u.SendMessageW(ctypes.c_void_p(btn), 0x00F5, 0, 0)   # BM_CLICK
    time.sleep(1.5)

    err = ''
    t0 = time.time()
    while time.time() - t0 < 25:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm') and h != d[0]:
                kids = [k[2][:60] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                err = kids[0] if kids else '(dialog)'
                capture(h, r'C:\Home\Workspace\UGit\psdto\_work\dlg99_open.png')
                break
        if err:
            break
        time.sleep(0.6)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    print('结果:', err or '无弹框')
    print('标题:', title)
    print('alive:', proc.poll() is None)
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
