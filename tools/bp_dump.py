"""在 exe 里下断点，把命中瞬间的栈帧 dump 到文件。

用途：psdto3d101.exe 在 0xD26FC 调用 0xE32FC 读取并解密 cmyk3d_Ini.enc，
返回后 0xD2709 用四个 == 0x7B 校验明文。断在 0xD2701（call 之后、校验之前），
此刻 [ebp-0x341..ebp] 里就是解密好的参数。

    python tools/bp_dump.py <pkg> <project> <out.tif> --sites 0xD2701:0x341 ...

每个 site 命中后写 _bp_<va>.bin（附带 _bp_<va>.txt 记录 eip/eax/ebp）。
"""
import argparse
import ctypes
import os
import struct
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win
from trace_exception import (DEBUG_EVENT, EXCEPTION_DEBUG_EVENT,
                             EXIT_PROCESS_DEBUG_EVENT)
from trace_stack_at_raise import (CONTEXT, CONTEXT_FULL, CONTEXT_SIZE,
                                  get_context, rpm)

k32 = ctypes.windll.kernel32
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.SetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]


def wpm(pid, addr, data):
    h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
    if not h:
        return False
    n = ctypes.c_size_t()
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr), data, len(data),
                                ctypes.byref(n))
    k32.CloseHandle(h)
    return bool(ok)


def set_ctx(tid, ctx):
    th = k32.OpenThread(0x0008 | 0x0002 | 0x0010 | 0x0040, False, tid)
    if not th:
        return False
    raw = ctypes.create_string_buffer(CONTEXT_SIZE + 64)
    dst = (ctypes.addressof(raw) + 15) & ~15
    ctypes.memmove(dst, ctypes.addressof(ctx), CONTEXT_SIZE)
    ok = k32.SetThreadContext(th, ctypes.c_void_p(dst))
    k32.CloseHandle(th)
    return bool(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg')
    ap.add_argument('project')
    ap.add_argument('out')
    ap.add_argument('--sites', default='0xD2701:0x341')
    ap.add_argument('--cmds', default='3@2,16@12')
    ap.add_argument('--duration', type=float, default=90)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--base', default='0x400000', help='exe 的加载基址，site 会加上它')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    out = os.path.abspath(a.out)
    sched = sorted((float(t), int(c)) for c, t in
                   (x.split('@') for x in a.cmds.split(',')))
    base = int(a.base, 16)
    sites = []
    for spec in a.sites.split(','):
        va, ln = spec.split(':')
        sites.append((int(va, 16) + base, int(ln, 16)))
    print('sites: %s' % ', '.join('0x%X' % v for v, _ in sites), flush=True)
    live = {}          # va -> (orig_byte, n_hits)
    for va, ln in sites:
        b = rpm(0, 0, 0)  # noop guard
        live[va] = [None, 0, ln]

    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg,
                                      os.path.abspath(a.project), out)
    pid = rep['pid']
    print('pid=%d' % pid, flush=True)
    time.sleep(1.0)
    hwnd = None
    for _ in range(40):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)
    print('hwnd=%s' % hwnd, flush=True)
    if not hwnd:
        raise SystemExit('没有主窗口')

    if not k32.DebugActiveProcess(pid):
        raise SystemExit('DebugActiveProcess 失败')

    hproc = k32.OpenProcess(0x1F0FFF, False, pid)
    print('hproc=%s err=%d' % (hproc, k32.GetLastError()), flush=True)
    for va in live:
        cur = rpm(pid, va, 1)
        if not cur:
            raise SystemExit('读不到 0x%X (OpenProcess 1F0FFF=%s)'
                             % (va, k32.OpenProcess(0x1F0FFF, False, pid)))
        live[va][0] = cur
        wpm(pid, va, b'\xcc')
        print('断点 0x%X (原字节 %s)' % (va, cur.hex()), flush=True)

    t0 = time.time()
    next_cmd = 0
    step_pending = None      # (va, tid)
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if next_cmd < len(sched) and el >= sched[next_cmd][0]:
            cmd = sched[next_cmd][1]
            next_cmd += 1
            win.command(hwnd, cmd)
            print('t=%.1fs 发命令 %d' % (el, cmd), flush=True)
        ev = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(ev), 100):
            continue
        handled = False
        if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            code = ev.u.Exception.ExceptionRecord.ExceptionCode
            if code == 0x80000003:                       # breakpoint
                ctx, _ = get_context(pid, ev.dwThreadId)
                if ctx:
                    site = ctx.Eip - 1
                    if site in live:
                        ebp = ctx.Ebp
                        ln = live[site][2]
                        blob = rpm(pid, ebp - ln, ln + 0x40)
                        if blob:
                            fn = '_bp_%06X.bin' % site
                            with open(os.path.join(pkg, fn), 'wb') as f:
                                f.write(blob)
                            with open(os.path.join(pkg, fn[:-4] + '.txt'), 'w') as f:
                                f.write('site=%08X ebp=%08X eax=%08X edx=%08X ecx=%08X esp=%08X\n'
                                        % (site, ebp, ctx.Eax, ctx.Edx, ctx.Ecx, ctx.Esp))
                                f.write('stack args: ')
                                sa = rpm(pid, ctx.Esp, 0x80)
                                if sa:
                                    f.write(sa.hex(' ') + '\n')
                        live[site][1] += 1
                        print('t=%.1fs hit 0x%X ebp=%08X eax=%08X'
                              % (el, site, ebp, ctx.Eax), flush=True)
                        # 恢复原字节 -> 回退 eip -> 单步 -> 再装断点
                        wpm(pid, site, live[site][0])
                        ctx.Eip = site
                        ctx.EFlags |= 0x100
                        set_ctx(ev.dwThreadId, ctx)
                        step_pending = site
                        handled = True
            elif code == 0x80000004:                     # single step
                if step_pending is not None:
                    wpm(pid, step_pending, b'\xcc')
                    ctx, _ = get_context(pid, ev.dwThreadId)
                    if ctx:
                        ctx.EFlags &= ~0x100
                        set_ctx(ev.dwThreadId, ctx)
                    step_pending = None
                    handled = True
        elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            print('进程退出 t=%.1fs' % el, flush=True)
            k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
            break
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId,
                               DBG_CONTINUE if handled else DBG_CONTINUE)

    for va, rec in live.items():
        print('0x%X 命中 %d 次' % (va, rec[1]), flush=True)
    try:
        k32.DebugActiveProcessStop(pid)
    except Exception:
        pass
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
