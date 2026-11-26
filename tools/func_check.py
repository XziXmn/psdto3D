# -*- coding: utf-8 -*-
"""功能自检：按菜单序列点一遍，记录每步之后窗口标题/弹框/关键文件是否变化。

    python tools/func_check.py --pkg _work/emu1 --cmds "7@10,10@40,4@70,5@95" --duration 150
"""
import argparse
import ctypes
import json
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32


def title(hwnd):
    b = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(ctypes.c_void_p(hwnd), b, 256)
    return b.value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--cmds', required=True)
    ap.add_argument('--duration', type=float, default=150)
    ap.add_argument('--watch', default='', help='逗号分隔的待观察文件')
    ap.add_argument('--fill', default='', help='逗号分隔的文件对话框应答路径')
    a = ap.parse_args()

    fills = [f for f in a.fill.split(',') if f]

    pkg = os.path.abspath(a.pkg)
    sp.run(['taskkill', '/IM', a.exe, '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(0.5)
    proc = sp.Popen([os.path.join(pkg, a.exe)], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    if not hwnd:
        print(json.dumps({'error': 'no main window'}))
        return 1

    sched = sorted((float(t), int(c)) for c, t in (x.split('@') for x in a.cmds.split(',')))
    watch = [w for w in a.watch.split(',') if w]
    t0 = time.time()
    nxt = 0
    done = set()
    print('t=0.0 title=%r' % title(hwnd))
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if nxt < len(sched) and el >= sched[nxt][0]:
            cmd = sched[nxt][1]
            win.command(hwnd, cmd)
            print('t=%.1f SEND %d' % (el, cmd))
            nxt += 1
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('TMessageForm', '#32770'):
                kids = [k[2][:70] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
                # 文件对话框：有 文件名 编辑框就填路径再回车
                if fills:
                    edit = None
                    for kh, kcls, ktxt in win.children(h, 3):
                        if kcls in ('Edit', 'TEdit'):
                            edit = kh
                    if edit is not None:
                        u.SetWindowTextW(ctypes.c_void_p(edit), fills[0])
                        path = fills.pop(0)
                        print('t=%.1f FILL %s' % (el, path))
                        time.sleep(0.3)
                        for kh, kcls, ktxt in win.children(h, 3):
                            if kcls in ('Button',) and (ktxt or '').strip() and '打开' in (ktxt or ''):
                                win.click(kh)
                                break
                        else:
                            win.click(edit)
                            time.sleep(0.2)
                            u.PostMessageW(ctypes.c_void_p(h), 0x0100, 0x0D, 0)
                        time.sleep(0.5)
                        continue
                key = (cls, tuple(kids[:1]))
                if key not in done:
                    done.add(key)
                    print('t=%.1f DIALOG %s %r' % (el, cls, kids[:2]))
                for kh, kcls, ktxt in win.children(h, 2):
                    if kcls in ('TButton', 'Button'):
                        win.click(kh)
                        break
        for w in watch:
            if os.path.exists(w):
                print('t=%.1f FILE %s = %d' % (el, os.path.basename(w), os.path.getsize(w)))
                watch.remove(w)
        time.sleep(0.2)
    print('end title=%r alive=%s' % (title(hwnd), proc.poll() is None))
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
