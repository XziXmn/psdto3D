# -*- coding: utf-8 -*-
"""Press Ctrl+Alt+C in the running app (native language toggle) and screenshot."""
import ctypes
import os
import sys
import time
import subprocess as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win
from winshot import capture

u = ctypes.windll.user32
VK_CONTROL, VK_MENU, VK_C = 0x11, 0x12, 0x43
KEYEVENTF_KEYUP = 0x0002


def key(vk, up=False):
    u.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)
    time.sleep(0.05)


def main():
    pkg = sys.argv[1]
    out = sys.argv[2]
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    time.sleep(3)
    u.SetForegroundWindow(ctypes.c_void_p(hwnd))
    time.sleep(0.5)

    key(VK_CONTROL)
    key(VK_MENU)
    key(VK_C)
    key(VK_C, up=True)
    key(VK_MENU, up=True)
    key(VK_CONTROL, up=True)
    time.sleep(2.5)
    print('size', capture(hwnd, out))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
