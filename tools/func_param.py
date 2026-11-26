# -*- coding: utf-8 -*-
"""改一个界面参数（按控件文本定位 TEdit）再跑导出，验证参数是否真的生效。

    python tools/func_param.py --pkg _work/emu1 --find 11 --set 13 --out C:\\bio\\out.psd
"""
import argparse
import ctypes
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32
u.SetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--find', required=True)
    ap.add_argument('--set', required=True)
    ap.add_argument('--cmds', default='12@40,16@150,17@200')
    ap.add_argument('--duration', type=float, default=330)
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(0.5)
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    if not hwnd:
        print('no window')
        return 1

    # 打开工程后改参数
    win.command(hwnd, 3)
    time.sleep(6)
    target = None
    for h, cls, txt in win.children(hwnd, 4):
        if cls == 'TEdit' and (txt or '').strip() == a.find:
            target = h
            break
    if not target:
        print('未找到文本为 %s 的 TEdit' % a.find)
        sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return 1
    u.SetWindowTextW(ctypes.c_void_p(target), a.set)
    print('已把 TEdit(%s) 改成 %s' % (a.find, a.set))

    sched = sorted((float(t), int(c)) for c, t in (x.split('@') for x in a.cmds.split(',')))
    t0 = time.time()
    nxt = 0
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if nxt < len(sched) and el >= sched[nxt][0]:
            win.command(hwnd, sched[nxt][1])
            print('t=%.0f SEND %d' % (el, sched[nxt][1]))
            nxt += 1
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('TMessageForm', '#32770'):
                kids = [k[2][:60] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                print('t=%.0f DIALOG %r' % (el, kids[:2]))
                for kh, kcls, ktxt in win.children(h, 2):
                    if kcls in ('TButton', 'Button'):
                        win.click(kh)
                        break
        time.sleep(0.2)
    print('alive=', proc.poll() is None)
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
