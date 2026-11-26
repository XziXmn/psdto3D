"""Attach a debugger to an already-stubbed psdto3d instance, trigger PSD import,
and report every exception with its owning module and offset."""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win
from trace_exception import DEBUG_EVENT, EXCEPTION_DEBUG_EVENT, EXIT_PROCESS_DEBUG_EVENT, modules, owning

k32 = ctypes.windll.kernel32
DBG_CONTINUE = 0x00010002


def main():
    pkg = os.path.abspath(sys.argv[1])
    psd = os.path.abspath(sys.argv[2])
    cmd = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    duration = float(sys.argv[4]) if len(sys.argv) > 4 else 25.0

    rep, hproc = dialogless_launch.launch(os.path.join(pkg, 'psdto3d101.exe'), pkg, psd,
                                          os.path.join(pkg, '_out.tif'))
    pid = rep['pid']
    print('pid=%d' % pid)
    time.sleep(1.0)
    if not k32.DebugActiveProcess(pid):
        raise SystemExit('DebugActiveProcess failed: %s' % ctypes.WinError())
    print('attached')

    posted = False
    t0 = time.time()
    rows = []
    while time.time() - t0 < duration:
        ev = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(ev), 120):
            if not posted:
                win.command(rep.get('main_hwnd') or [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0], cmd)
                posted = True
                print('posted cmd %d at t=%.1f' % (cmd, time.time() - t0))
            continue
        cont = DBG_CONTINUE
        if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            rec = ev.u.Exception.ExceptionRecord
            addr = rec.ExceptionAddress or 0
            n = min(rec.NumberParameters or 0, 15)
            params = [rec.ExceptionInformation[i] or 0 for i in range(n)]
            name, off = owning(addr, modules(pid))
            row = {'t': round(time.time() - t0, 1), 'after_cmd': posted,
                   'code': hex(rec.ExceptionCode), 'first': bool(ev.u.Exception.dwFirstChance),
                   'module': name, 'offset': hex(off), 'params': [hex(p) for p in params]}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False))
        elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            print('exited')
            break
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont)

    print('--- summary')
    for r in rows:
        if r['after_cmd']:
            print('  AFTER-CMD %-10s %-18s +%s params=%s' %
                  (r['code'], r['module'], r['offset'], ','.join(r['params'][:3])))
    print('  total=%d, after_cmd=%d' % (len(rows), sum(1 for r in rows if r['after_cmd'])))
    k32.DebugActiveProcessStop(pid)
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
