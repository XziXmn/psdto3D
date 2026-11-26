"""给调试中的进程在 API 入口下断点，记录参数（文件名 / IOCTL 码）。

用来回答：exe 什么时候去开 \\\\.\\MyUSBKey、什么时候读 .enc，调用者是谁。

    python tools/bp_watch.py <pkg> <project> <out.tif> \
        --apis CreateFileA:5242BC:s,DeviceIoControl:52449C:d \
        --cmds 3@2,16@30 --duration 60
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
                             EXIT_PROCESS_DEBUG_EVENT, modules, owning)
from trace_stack_at_raise import (CONTEXT, CONTEXT_FULL, CONTEXT_SIZE,
                                  get_context, rpm)

k32 = ctypes.windll.kernel32
DBG_CONTINUE = 0x00010002
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.SetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
BASE = 0x400000


def wpm(pid, addr, data):
    h = k32.OpenProcess(0x1F0FFF, False, pid)
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


def read_cstr(pid, addr, maxlen=260):
    b = rpm(pid, addr, maxlen)
    if not b:
        return None
    z = b.find(b'\x00')
    if z >= 0:
        b = b[:z]
    try:
        return b.decode('gbk', 'replace')
    except Exception:
        return b.decode('latin1', 'replace')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg')
    ap.add_argument('project')
    ap.add_argument('out')
    ap.add_argument('--apis', required=True,
                    help='Name:IATVA:kind[,Name:IATVA:kind...]  kind: s=字符串在[esp+4], d=dword在[esp+8]')
    ap.add_argument('--cmds', default='3@2,16@30')
    ap.add_argument('--duration', type=float, default=60)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--log', default='_watch.txt')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    out = os.path.abspath(a.out)
    sched = sorted((float(t), int(c)) for c, t in
                   (x.split('@') for x in a.cmds.split(',')))
    specs = [x.split(':') for x in a.apis.split(',')]

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
    if not k32.DebugActiveProcess(pid):
        raise SystemExit('DebugActiveProcess 失败')

    hproc = k32.OpenProcess(0x1F0FFF, False, pid)
    armed = []       # (addr, name, kind, orig_byte)
    for name, iat, kind in specs:
        raw = rpm(pid, BASE + int(iat, 16), 4)
        if not raw:
            print('IAT 读不到 %s' % name, flush=True)
            continue
        addr = struct.unpack('<I', raw)[0]
        orig = rpm(pid, addr, 1)
        if not orig:
            print('代码读不到 %s @0x%X' % (name, addr), flush=True)
            continue
        wpm(pid, addr, b'\xcc')
        armed.append((addr, name, kind, orig))
        print('挂上 %s @0x%X (IAT 0x%X)' % (name, addr, BASE + int(iat, 16)), flush=True)

    logf = open(os.path.join(pkg, a.log), 'w', encoding='utf-8')
    t0 = time.time()
    next_cmd = 0
    step_pending = None
    hits = 0
    mods = None
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if next_cmd < len(sched) and el >= sched[next_cmd][0]:
            cmd = sched[next_cmd][1]
            next_cmd += 1
            win.command(hwnd, cmd)
            print('t=%.1fs 发命令 %d' % (el, cmd), flush=True)
            logf.write('--- t=%.1fs 命令 %d\n' % (el, cmd))
            logf.flush()
        ev = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(ev), 100):
            continue
        if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            code = ev.u.Exception.ExceptionRecord.ExceptionCode
            if code == 0x80000003:
                ctx, _ = get_context(pid, ev.dwThreadId)
                if ctx:
                    eip = ctx.Eip - 1
                    hit = [x for x in armed if x[0] == eip]
                    if hit:
                        addr, name, kind, orig = hit[0]
                        if mods is None:
                            mods = modules(pid)
                        ret = rpm(pid, ctx.Esp, 4)
                        reta = struct.unpack('<I', ret)[0] if ret else 0
                        mn, off = owning(reta, mods) if mods else ('?', 0)
                        if kind == 's':
                            sp = rpm(pid, ctx.Esp + 4, 4)
                            pa = struct.unpack('<I', sp)[0] if sp else 0
                            arg = read_cstr(pid, pa)
                            line = '%s("%s")  <- %s+0x%X' % (name, arg, mn, off)
                        else:
                            sp = rpm(pid, ctx.Esp + 8, 4)
                            v = struct.unpack('<I', sp)[0] if sp else 0
                            line = '%s(0x%08X)  <- %s+0x%X' % (name, v, mn, off)
                        logf.write('t=%.1fs %s\n' % (el, line))
                        logf.flush()
                        hits += 1
                        if hits <= 200:
                            print('t=%.1fs %s' % (el, line), flush=True)
                        wpm(pid, addr, orig)
                        ctx.Eip = addr
                        ctx.EFlags |= 0x100
                        set_ctx(ev.dwThreadId, ctx)
                        step_pending = addr
                        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
                        continue
            elif code == 0x80000004:
                if step_pending is not None:
                    wpm(pid, step_pending, b'\xcc')
                    ctx, _ = get_context(pid, ev.dwThreadId)
                    if ctx:
                        ctx.EFlags &= ~0x100
                        set_ctx(ev.dwThreadId, ctx)
                    step_pending = None
                    k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
                    continue
        elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            print('进程退出 t=%.1fs' % el, flush=True)
            k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
            break
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)

    print('共记录 %d 次' % hits, flush=True)
    logf.close()
    try:
        k32.DebugActiveProcessStop(pid)
    except Exception:
        pass
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
