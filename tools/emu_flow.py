"""Run the emulator package through a menu schedule, no dialog IAT patching.

The emulator DLL answers the common dialogs itself (via _dlgopen.txt / _dlgsave.txt),
so this driver only has to push menu commands and dismiss message boxes.

    python tools/emu_flow.py --pkg _work/emu1 --cmds 7@8,10@25,12@40,16@95 --duration 150
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


def kill_leftovers():
    subprocess.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--cmds', default='7@8,10@25,12@40,16@95')
    ap.add_argument('--duration', type=float, default=150)
    ap.add_argument('--keep-open', action='store_true')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    logp = os.path.join(pkg, '_dongle.log')
    for p in (logp,):
        if os.path.exists(p):
            os.remove(p)

    kill_leftovers()
    time.sleep(0.5)

    si = subprocess.STARTUPINFO()
    proc = subprocess.Popen([os.path.join(pkg, a.exe)], cwd=pkg,
                            startupinfo=si, close_fds=True)
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
    ok_words = ('ok', '确定', '是', 'yes', 'close', '关闭')
    t0 = time.time()
    nxt = 0
    sent = []
    next_dismiss = 0.0
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if nxt < len(sched) and el >= sched[nxt][0]:
            win.command(hwnd, sched[nxt][1])
            sent.append((round(el, 1), sched[nxt][1]))
            nxt += 1
        if el >= next_dismiss:
            next_dismiss = el + 1.5
            for h, cls, title, vis in win.windows(pid):
                if not vis or cls == 'TForm1' or cls == 'TApplication':
                    continue
                kids = win.children(h, 3)
                target = None
                for kh, kcls, ktxt in kids:
                    if kcls in ('TButton', 'Button') and (ktxt or '').strip().lower() in ok_words:
                        target = kh
                        break
                if target is None:
                    for kh, kcls, ktxt in kids:
                        if kcls in ('TButton', 'Button'):
                            target = kh
                            break
                if target:
                    win.click(target)
        time.sleep(0.2)

    alive = proc.poll() is None
    if alive and not a.keep_open:
        subprocess.run(['taskkill', '/PID', str(pid), '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out = {'pid': pid, 'cmds': sent, 'alive_at_end': alive,
           'log_bytes': os.path.getsize(logp) if os.path.exists(logp) else 0}
    print(json.dumps(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
