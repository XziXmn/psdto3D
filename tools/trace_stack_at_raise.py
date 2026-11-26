"""Attach a debugger and walk the stack at the `Invalid numeric input` raise.

    python tools/trace_stack_at_raise.py <pkg> <project> [seconds]

On Delphi exceptions (0xEEDFADE), reads the thread context (16-byte-aligned
CONTEXT as required on x64), walks the EBP chain of the raising thread, and
prints each frame's return address resolved to module+offset. Delphi stack
frames keep EBP chains intact unless compiled with -O+ frame elimination.
"""
import ctypes
import os
import struct
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win
from trace_exception import DEBUG_EVENT, EXCEPTION_DEBUG_EVENT, EXIT_PROCESS_DEBUG_EVENT, modules, owning

k32 = ctypes.windll.kernel32
DBG_CONTINUE = 0x00010002
CONTEXT_FULL = 0x10007
CONTEXT_SIZE = 800


class CONTEXT(ctypes.Structure):
    _fields_ = [('ContextFlags', wintypes.DWORD),
                ('Dr0', wintypes.DWORD), ('Dr1', wintypes.DWORD), ('Dr2', wintypes.DWORD),
                ('Dr3', wintypes.DWORD), ('Dr6', wintypes.DWORD), ('Dr7', wintypes.DWORD),
                ('FloatSave', ctypes.c_byte * 112),
                ('SegGs', wintypes.DWORD), ('SegFs', wintypes.DWORD), ('SegEs', wintypes.DWORD),
                ('SegDs', wintypes.DWORD),
                ('Edi', wintypes.DWORD), ('Esi', wintypes.DWORD), ('Ebx', wintypes.DWORD),
                ('Edx', wintypes.DWORD), ('Ecx', wintypes.DWORD), ('Eax', wintypes.DWORD),
                ('Ebp', wintypes.DWORD), ('Eip', wintypes.DWORD), ('SegCs', wintypes.DWORD),
                ('EFlags', wintypes.DWORD), ('Esp', wintypes.DWORD), ('SegSs', wintypes.DWORD),
                ('ExtendedRegisters', ctypes.c_byte * 512)]


def rpm(pid, addr, size):
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not h:
        return None
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    k32.CloseHandle(h)
    return buf.raw[:got.value] if ok else None


def get_context(pid, tid):
    th = k32.OpenThread(0x0008 | 0x0040, False, tid)   # GET_CONTEXT | QUERY_INFORMATION
    if not th:
        return None, 'OpenThread failed'
    raw = ctypes.create_string_buffer(CONTEXT_SIZE + 64)
    addr = (ctypes.addressof(raw) + 15) & ~15
    ctx = CONTEXT.from_address(addr)
    ctx.ContextFlags = CONTEXT_FULL
    k32.Wow64GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    ok = k32.Wow64GetThreadContext(th, addr)   # 32-bit debuggee under a 64-bit debugger
    k32.CloseHandle(th)
    if not ok:
        return None, 'GetThreadContext failed: %s' % ctypes.WinError()
    return ctx, None


def main():
    pkg = os.path.abspath(sys.argv[1])
    project = os.path.abspath(sys.argv[2])
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

    rep, hproc = dialogless_launch.launch(os.path.join(pkg, 'psdto3d101.exe'), pkg, project,
                                          os.path.join(pkg, '_trace.tif'))
    pid = rep['pid']
    time.sleep(1.0)
    if not k32.DebugActiveProcess(pid):
        raise SystemExit('DebugActiveProcess failed')
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    win.command(hwnd, 3)

    t0 = time.time()
    reported = 0
    while time.time() - t0 < duration:
        ev = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(ev), 200):
            continue
        cont = DBG_CONTINUE
        if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            rec = ev.u.Exception.ExceptionRecord
            params = [rec.ExceptionInformation[i] for i in range(min(rec.NumberParameters, 7))]
            if rec.ExceptionCode == 0xEEDFADE and reported < 4:
                ctx, err = get_context(pid, ev.dwThreadId)
                mods = modules(pid)
                if ctx:
                    print('=== delphi raise: obj=0x%08x site=0x%08x (t=%.1fs) ===' %
                          (params[1] if len(params) > 1 else 0,
                           params[0] if params else 0, time.time() - t0))
                    print('  eax=%08x ebx=%08x ecx=%08x edx=%08x esi=%08x edi=%08x' %
                          (ctx.Eax, ctx.Ebx, ctx.Ecx, ctx.Edx, ctx.Esi, ctx.Edi))
                    ebp = ctx.Ebp
                    for i in range(16):
                        fr = rpm(pid, ebp, 8)
                        if not fr or len(fr) < 8:
                            break
                        nxt, ret = struct.unpack('<II', fr)
                        name, off = owning(ret, mods)
                        print('  frame %2d ebp=%08x ret=0x%08x (%s+0x%x)' % (i, ebp, ret, name, off))
                        if nxt <= ebp or nxt > 0x7FFF0000:
                            break
                        ebp = nxt
                    reported += 1
                    if reported >= 4:
                        print('(stopping context reports)')
                else:
                    print('context unavailable: %s' % err)
        elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            break
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont)

    try:
        k32.DebugActiveProcessStop(pid)
    except Exception:
        pass
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
