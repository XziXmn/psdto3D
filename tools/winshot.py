# -*- coding: utf-8 -*-
"""Capture a window via PrintWindow (works without an interactive desktop grab)."""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
import subprocess as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32
g = ctypes.windll.gdi32


def capture(hwnd, path):
    r = wt.RECT()
    u.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        raise RuntimeError('bad rect')
    hdc = u.GetWindowDC(ctypes.c_void_p(hwnd))
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(ctypes.c_void_p(hwnd), mdc, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
                    ('biPlanes', wt.WORD), ('biBitCount', wt.WORD),
                    ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
                    ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG),
                    ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    from PIL import Image
    img = Image.frombuffer('RGB', (w, h), buf, 'raw', 'BGRX', 0, 1)
    img.save(path)
    return img.size


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
    time.sleep(6)
    print('size', capture(hwnd, out))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
