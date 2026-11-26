"""Attach as a minimal debugger, trigger PSD import, and report every exception with
the owning module, so we can see which module actually fails."""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

DEBUG_ONLY_THIS_PROCESS = 0x2
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
EXIT_PROCESS_DEBUG_EVENT = 5

k32 = ctypes.windll.kernel32


class STARTUPINFO(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR), ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR), ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD),
                ('dwXCountChars', wintypes.DWORD), ('dwYCountChars', wintypes.DWORD),
                ('dwFillAttribute', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_void_p), ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD)]


class EXCEPTION_RECORD(ctypes.Structure):
    pass


EXCEPTION_RECORD._fields_ = [
    ('ExceptionCode', wintypes.DWORD), ('ExceptionFlags', wintypes.DWORD),
    ('ExceptionRecord', ctypes.POINTER(EXCEPTION_RECORD)),
    ('ExceptionAddress', ctypes.c_void_p), ('NumberParameters', wintypes.DWORD),
    ('ExceptionInformation', ctypes.c_void_p * 15)]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [('ExceptionRecord', EXCEPTION_RECORD), ('dwFirstChance', wintypes.DWORD)]


class DEBUG_EVENT_UNION(ctypes.Union):
    _fields_ = [('Exception', EXCEPTION_DEBUG_INFO), ('_pad', ctypes.c_byte * 176)]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [('dwDebugEventCode', wintypes.DWORD), ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD), ('u', DEBUG_EVENT_UNION)]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('th32ModuleID', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                ('GlblcntUsage', wintypes.DWORD), ('ProccntUsage', wintypes.DWORD),
                ('modBaseAddr', ctypes.c_void_p), ('modBaseSize', wintypes.DWORD),
                ('hModule', wintypes.HANDLE), ('szModule', ctypes.c_char * 256),
                ('szExePath', ctypes.c_char * 260)]


def modules(pid):
    out = []
    snap = k32.CreateToolhelp32Snapshot(0x8 | 0x10, pid)
    if snap == -1:
        return out
    me = MODULEENTRY32()
    me.dwSize = ctypes.sizeof(me)
    ok = k32.Module32First(snap, ctypes.byref(me))
    while ok:
        out.append((me.modBaseAddr or 0, me.modBaseSize, me.szModule.decode('mbcs', 'replace')))
        ok = k32.Module32Next(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return out


def owning(addr, mods):
    for base, size, name in mods:
        if base <= addr < base + max(size, 0x1000):
            return name, addr - base
    return '?', addr


def main():
    exe = os.path.abspath(sys.argv[1])
    cwd = os.path.dirname(exe)
    cmd = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 35.0
    si = STARTUPINFO(); si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()
    if not k32.CreateProcessW(exe, None, None, None, False, DEBUG_ONLY_THIS_PROCESS, None, cwd,
                              ctypes.byref(si), ctypes.byref(pi)):
        raise SystemExit('CreateProcess failed: %s' % ctypes.WinError())
    pid = pi.dwProcessId
    print('debuggee pid=%d' % pid)

    posted = False
    t0 = time.time()
    rows = []
    while time.time() - t0 < duration:
        ev = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(ev), 150):
            if not posted:
                mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
                if mw:
                    time.sleep(1.2)
                    win.command(mw[0][0], cmd)
                    posted = True
                    print('posted command %d at t=%.1fs' % (cmd, time.time() - t0))
            continue
        cont = DBG_CONTINUE
        if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            rec = ev.u.Exception.ExceptionRecord
            addr = rec.ExceptionAddress or 0
            n = min(rec.NumberParameters or 0, 15)
            params = [rec.ExceptionInformation[i] or 0 for i in range(n)]
            mods = modules(pid)
            name, off = owning(addr, mods)
            row = {'t': round(time.time() - t0, 1), 'phase': 'after-cmd' if posted else 'startup',
                   'code': hex(rec.ExceptionCode), 'first': bool(ev.u.Exception.dwFirstChance),
                   'module': name, 'offset': hex(off), 'address': hex(addr),
                   'params': [hex(p) for p in params]}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False))
        elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
            print('debuggee exited at t=%.1fs' % (time.time() - t0))
            break
        k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont)
    print('--- summary: %d exceptions' % len(rows))
    for r in rows:
        print('  %-11s %-8s %-22s +%s  params=%s' % (r['phase'], r['code'], r['module'], r['offset'], ','.join(r['params'][:4])))
    try:
        k32.TerminateProcess(pi.hProcess, 0)
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
