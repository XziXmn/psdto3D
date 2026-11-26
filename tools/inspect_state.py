"""Inspect the live layer-table state inside a running psdto3d right before export.

Reads the globals used by the failing routine (0x501093):
    0x5230b4  layer record array (56-byte records, group byte at +0x2C)
    0x52315c  layer count (word)
    0x52309c  per-group table (dynamic array of lists)
    0x5230a0  second per-group table
    0x523158  index used by the failing read
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

k32 = ctypes.windll.kernel32
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

BASE = 0x400000


def read(pid, addr, size):
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)   # VM_READ | QUERY_INFORMATION
    if not h:
        raise SystemExit('OpenProcess failed')
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    k32.CloseHandle(h)
    return buf.raw[:got.value] if ok else None


def dword(pid, addr):
    b = read(pid, addr, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else None


def main():
    pkg = os.path.abspath(sys.argv[1])
    project = os.path.abspath(sys.argv[2])
    rep, _ = dialogless_launch.launch(os.path.join(pkg, 'psdto3d101.exe'), pkg, project,
                                      os.path.join(pkg, '_probe.tif'))
    pid = rep['pid']
    time.sleep(5)
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    win.command(hwnd, 3)          # open project
    time.sleep(8)

    g_records = dword(pid, 0x5230b4)
    g_table = dword(pid, 0x52309c)
    g_table2 = dword(pid, 0x5230a0)
    g_idx = dword(pid, 0x523158)
    raw = read(pid, 0x52315c, 2)
    nlayers = struct.unpack('<H', raw)[0] if raw else None
    print('layer records  = %s' % (hex(g_records) if g_records else g_records))
    print('group table    = %s' % (hex(g_table) if g_table else g_table))
    print('group table 2  = %s' % (hex(g_table2) if g_table2 else g_table2))
    print('[0x523158]     = %s' % (hex(g_idx) if g_idx is not None else None))
    print('layer count    = %s' % nlayers)

    if g_records and nlayers:
        for i in range(min(nlayers, 16)):
            rec = read(pid, g_records + i * 56, 56)
            if not rec:
                print('  layer %d: unreadable' % i)
                continue
            group = rec[0x2c]
            print('  layer %2d group=%3d  rec[0..7]=%s' % (i, group, rec[:8].hex()))
    if g_table:
        elem = read(pid, g_table, 16)
        print('  table[0..3] = %s' % (elem.hex() if elem else None))
        # Delphi dynamic array: length at table-4
        ln = dword(pid, g_table - 4)
        print('  table length = %s' % ln)

    win.command(hwnd, 16)         # export (crashes)
    time.sleep(4)
    for h, cls, title, vis in win.windows(pid):
        if cls == '#32770' and vis:
            kids = win.children(h, maxdepth=1)
            for kh, kcls, ktxt in kids:
                if kcls == 'Static' and ktxt:
                    print('  dialog text: %r' % ktxt)
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
