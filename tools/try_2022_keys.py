# -*- coding: utf-8 -*-
"""2022：用键盘把路径打进文件对话框（最可靠），对比 32 层 / 50 层工程。"""
import ctypes
import os
import subprocess as sp
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win
from winshot import capture

u = ctypes.windll.user32
PKG = r'C:\Home\Workspace\UGit\psdto\_work\2022ok'

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT)]
    _anonymous_ = ('i',)
    _fields_ = [('type', wintypes.DWORD), ('i', _I)]


def type_unicode(text):
    for ch in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ki.wVk = 0
            inp.ki.wScan = ord(ch)
            inp.ki.dwFlags = flags
            u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def press(vk):
    for flags in (0, 0x0002):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        inp.ki.dwFlags = flags
        u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def close_reg(pid):
    for h, cls, t, v in win.windows(pid):
        if cls in ('TForm3', 'TRegform'):
            u.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)


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
        print(tag, '没有对话框')
        sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return
    u.SetForegroundWindow(ctypes.c_void_p(d[0]))
    time.sleep(0.5)
    type_unicode(project)
    time.sleep(0.6)
    press(VK_RETURN)
    time.sleep(1.0)

    err = ''
    t0 = time.time()
    while time.time() - t0 < 20:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm') and h != d[0]:
                kids = [k[2][:50] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                err = kids[0] if kids else '(dialog)'
                capture(h, r'C:\Home\Workspace\UGit\psdto\_work\dlg22_%s.png' % tag)
                break
        if err:
            break
        time.sleep(0.5)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    print('%s -> %s | 标题=%s' % (tag, err or '无弹框', title))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def main():
    run(r'C:\bio\step_2_marker.tw3d2', '32layer')
    run(r'C:\Home\Workspace\UGit\psdto\_work\2022ok\test50.tw3d2', '50layer')
    return 0


if __name__ == '__main__':
    sys.exit(main())
