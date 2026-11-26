# -*- coding: utf-8 -*-
"""导入 → 切到 3DSets 页签 → 预览，验证 TabSheet2Show 是否会把层数组分配好。"""
import ctypes
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32


def main():
    pkg = os.path.abspath(sys.argv[1])
    psd = sys.argv[2]
    tab_index = int(sys.argv[3]) if len(sys.argv) > 3 else 2
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
    print('导入后标题:', [t for h, c, t, v in win.windows(pid) if h == hwnd])

    pcs = [h for h, cls, t in win.children(hwnd, 4) if cls == 'TPageControl']
    idx = int(os.environ.get('PC_INDEX', '0'))
    pc = pcs[idx] if len(pcs) > idx else None
    print('pagecontrols:', len(pcs), 'using', idx)
    print('pagecontrol:', bool(pc))
    if pc:
        n = u.SendMessageW(ctypes.c_void_p(pc), 0x1304, 0, 0)
        print('页签数:', n)
        u.SendMessageW(ctypes.c_void_p(pc), 0x1300 + 52, tab_index, 0)   # TCM_SETCURSEL
        u.SendMessageW(ctypes.c_void_p(pc), 0x0200, 0, 0)                # WM_MOUSEMOVE
        time.sleep(2)
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:60] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                print('切页签后弹框:', kids[:1])

    win.command(hwnd, 12)
    err = ''
    t0 = time.time()
    while time.time() - t0 < 40:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:60] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.5)
    print('预览结果:', 'OK' if not err else err[:60])
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)


if __name__ == '__main__':
    main()
