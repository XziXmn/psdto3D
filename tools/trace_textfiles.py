"""Trace every text-file open (helper 0x402fac) in a live psdto3d via INT3 breakpoints.

    python tools/trace_textfiles.py <pkg> <project> [seconds]

Stops at 0x402fac (eax=@TextRec, edx=name string), logs the name, and also logs
calls to 0x5043f0 (PSD load) and 0x511408 (project parse). 0x402fac is replaced
with INT3 for the trace; the original byte is restored on first hit so the app
continues normally.
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
from trace_exception import DEBUG_EVENT, EXCEPTION_DEBUG_EVENT, EXIT_PROCESS_DEBUG_EVENT

k32 = ctypes.windll.kernel32
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
BP_OPEN = 0x402FAC       # text-file open/reset helper
BP_PSD = 0x5043F0        # PSD load
BP_PARSE = 0x511408      # project parse
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


class Proc:
    def __init__(self, hproc):
        self.h = hproc

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        ok = k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
        return buf.raw[:got.value] if ok else None

    def write(self, addr, data):
        old = ctypes.create_string_buffer(len(data))
        got = ctypes.c_size_t()
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), old, len(data), ctypes.byref(got))
        buf = ctypes.create_string_buffer(data, len(data))
        ok = k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(got))
        return old.raw if ok else None

    def dword(self, addr):
        b = self.read(addr, 4)
        return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0

    def delphi_str(self, addr):
        """eax/edx hold a pointer to the string variable (pointer to chars, len at -4)."""
        if not addr or addr < 0x10000:
            return None
        p = self.dword(addr)
        if not p or p < 0x10000:
            return None
        ln = struct.unpack('<i', self.read(p - 4, 4) or b'\0\0\0\0')[0]
        if not 0 <= ln < 1024:
            return None
        return (self.read(p, max(ln, 1)) or b'').decode('gbk', 'replace')


def get_ctx(hproc, tid):
    th = k32.OpenThread(0x0008 | 0x0040, False, tid)
    if not th:
        return None
    raw = ctypes.create_string_buffer(CONTEXT_SIZE + 64)
    addr = (ctypes.addressof(raw) + 15) & ~15
    ctx = CONTEXT.from_address(addr)
    ctx.ContextFlags = 0x10007
    k32.Wow64GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    k32.Wow64GetThreadContext(th, addr)
    k32.CloseHandle(th)
    return ctx


def set_ctx(hproc, tid, ctx):
    th = k32.OpenThread(0x0008 | 0x0010 | 0x0040, False, tid)
    if not th:
        return
    raw = ctypes.create_string_buffer(CONTEXT_SIZE + 64)
    addr = (ctypes.addressof(raw) + 15) & ~15
    ctypes.memmove(addr, ctypes.addressof(ctx), CONTEXT_SIZE)
    k32.Wow64SetThreadContext.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    k32.Wow64SetThreadContext(th, addr)
    k32.CloseHandle(th)


def main():
    pkg = os.path.abspath(sys.argv[1])
    project = os.path.abspath(sys.argv[2])
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 25.0

    rep, hproc = dialogless_launch.launch(os.path.join(pkg, 'psdto3d101.exe'), pkg, project,
                                          os.path.join(pkg, '_trace.tif'))
    pid = rep['pid']
    time.sleep(1.0)
    if not k32.DebugActiveProcess(pid):
        raise SystemExit('DebugActiveProcess failed')
    p = Proc(hproc)

    bps = {}
    for va, tag in [(BP_OPEN, 'OPEN'), (BP_PSD, 'PSD'), (BP_PARSE, 'PARSE')]:
        orig = p.write(va, b'\xcc')
        bps[va] = (tag, orig)

    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    win.command(hwnd, 3)

    t0 = time.time()
    lines = []
    while time.time() - t0 < duration:
        ev = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(ev), 200):
            continue
        cont = DBG_CONTINUE
        if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            rec = ev.u.Exception.ExceptionRecord
            if rec.ExceptionCode == 0x80000003:  # breakpoint
                ctx = get_ctx(hproc, ev.dwThreadId)
                if ctx:
                    eip = ctx.Eip
                    if eip - 1 in bps:
                        va = eip - 1
                        tag, orig = bps[va]
                        # restore original byte, rewind EIP
                        p.write(va, orig)
                        ctx.Eip = va
                        set_ctx(hproc, ev.dwThreadId, ctx)
                        if tag == 'OPEN':
                            name = p.delphi_str(ctx.Edx)
                            lines.append('OPEN  name=%r' % name)
                            print('[%6.2fs] OPEN  %r' % (time.time() - t0, name))
                        elif tag == 'PSD':
                            lines.append('PSD-LOAD')
                            print('[%6.2fs] PSD-LOAD' % (time.time() - t0))
                        elif tag == 'PARSE':
                            lines.append('PARSE-PROJECT')
                            print('[%6.2fs] PARSE-PROJECT' % (time.time() - t0))
                        # do not re-arm: single-shot per site
                    else:
                        cont = DBG_EXCEPTION_NOT_HANDLED
                else:
                    cont = DBG_EXCEPTION_NOT_HANDLED
            elif rec.ExceptionCode == 0xEEDFADE:
                print('[%6.2fs] DELPHI-RAISE obj=0x%08x' %
                      (time.time() - t0, params[1] if (params := [rec.ExceptionInformation[i]
                       for i in range(min(rec.NumberParameters, 7))]) and len(params) > 1 else 0))
            else:
                cont = DBG_EXCEPTION_NOT_HANDLED
        elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            break
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont)

    try:
        k32.DebugActiveProcessStop(pid)
    except Exception:
        pass
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    print('--- captured %d events' % len(lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
