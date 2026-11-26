# -*- coding: utf-8 -*-
"""尝试通过 WM_NOTIFY/TCN_SELCHANGE 触发 TPageControl 的 OnShow（从而分配层数组）。"""
import ctypes
import os
import struct
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32
TCN_SELCHANGE = -551
TCM_SETCURSEL = 0x1300 + 52


def main():
    pkg = os.path.abspath(sys.argv[1])
    psd = sys.argv[2]
    tab = int(sys.argv[3]) if len(sys.argv) > 3 else 0
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
    time.sleep(8)
    print('标题:', [t for h, c, t, v in win.windows(pid) if h == hwnd])

    pcs = [h for h, cls, t in win.children(hwnd, 4) if cls == 'TPageControl']
    for k, pc in enumerate(pcs):
        n = u.SendMessageW(ctypes.c_void_p(pc), 0x1304, 0, 0)
        print('pc%d 页签数=%d' % (k, n))
        if k == int(os.environ.get('PC_INDEX', '1')):
            u.SendMessageW(ctypes.c_void_p(pc), TCM_SETCURSEL, tab, 0)
            buf = struct.pack('<III', pc & 0xFFFFFFFF, 0, TCN_SELCHANGE & 0xFFFFFFFF)
            u.SendMessageW(ctypes.c_void_p(pc), 0x004E, 0, ctypes.cast(ctypes.create_string_buffer(buf), ctypes.c_void_p))
            time.sleep(2)
            print('  已发 TCN_SELCHANGE')

    win.command(hwnd, 12)
    err = ''
    t0 = time.time()
    while time.time() - t0 < 40:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k2[2][:60] for k2 in win.children(h, 2) if k2[1] in ('Static', 'TStaticText') and k2[2]]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.5)
    print('预览:', 'OK' if not err else err[:50])
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)


if __name__ == '__main__':
    main()
