"""Drive a package through a menu schedule and print a timeline (title / dialogs / temp files).

Useful to see where a long import stalls:

    python tools/flow_timeline.py --pkg _work/2022emu --cmds 7@8,10@30,12@50,16@110 --duration 220
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32


def title_of(hwnd):
    b = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(ctypes.c_void_p(hwnd), b, 256)
    return b.value


def temp_state():
    d = r'C:\ok3dtemp'
    if not os.path.isdir(d):
        return 'no temp dir'
    n = len(os.listdir(d))
    sz = 0
    for name in os.listdir(d):
        try:
            sz += os.path.getsize(os.path.join(d, name))
        except OSError:
            pass
    return '%d files %.1f MB' % (n, sz / 1e6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--cmds', default='7@8,10@30,12@50,16@110')
    ap.add_argument('--duration', type=float, default=220)
    ap.add_argument('--pre-sleep', type=float, default=5.0)
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    subprocess.run(['taskkill', '/IM', a.exe, '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    proc = subprocess.Popen([os.path.join(pkg, a.exe)], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.25)
    if not hwnd:
        print(json.dumps({'error': 'no main window'}))
        return 1

    sched = sorted((float(t), int(c)) for c, t in (x.split('@') for x in a.cmds.split(',')))
    t0 = time.time() + a.pre_sleep
    started = time.time()
    nxt = 0
    last_title = None
    last_temp = None
    print('t=0.0 title=%r temp=%s' % (title_of(hwnd), temp_state()))
    while time.time() - started < a.duration:
        el = time.time() - started - a.pre_sleep
        if nxt < len(sched) and el >= sched[nxt][0]:
            win.command(hwnd, sched[nxt][1])
            print('t=%.0f SEND menu %d' % (el, sched[nxt][1]))
            nxt += 1
        t = title_of(hwnd)
        if t != last_title:
            last_title = t
            print('t=%.0f title=%r' % (el, t))
        st = temp_state()
        if st != last_temp:
            last_temp = st
            print('t=%.0f temp=%s' % (el, st))
        for h, cls, title, vis in win.windows(pid):
            if vis and cls in ('TMessageForm', '#32770'):
                kids = win.children(h, 1)
                txt = [k[2] for k in kids if k[1] in ('Static', 'TStaticText') and k[2]]
                print('t=%.0f DIALOG %s %r %s' % (el, cls, title, txt[:2]))
                for kh, kcls, ktxt in win.children(h, 2):
                    if kcls in ('TButton', 'Button'):
                        win.click(kh)
                        break
        time.sleep(0.9)
    print('alive:', proc.poll() is None, 'out2022.tif:', os.path.exists(r'C:\bio\out2022.tif'))
    subprocess.run(['taskkill', '/PID', str(pid), '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
