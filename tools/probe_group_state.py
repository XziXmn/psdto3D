"""Snapshot the group-table globals in a live 2022 build around a project open.

    python tools/probe_group_state.py <pkg-dir> <project.tw3d2>

Launches the package exe with dialog stubs (dialogless_launch), sends command 3
(open project), then dumps the globals used by the 0x5023C7 check loop:

    0x52309c  interleaved per-group table (read by the crash site)
    0x5230a0  per-group layer-list table (built at 0x509f1a..0x509f5e)
    0x5230b4  layer records (56 bytes, group byte at +0x2c)
    0x52315c  layer count (word)      0x523158  view index (dword)
    0x5230fc  angles                  0x52308c / 0x523090  row metrics
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


def read(pid, addr, size):
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not h:
        return None
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    k32.CloseHandle(h)
    return buf.raw[:got.value] if ok else None


def dword(pid, addr):
    b = read(pid, addr, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else None


def word(pid, addr):
    b = read(pid, addr, 2)
    return struct.unpack('<H', b)[0] if b and len(b) == 2 else None


def dump_table(pid, name, table_ptr):
    p = dword(pid, table_ptr)
    if not p:
        print('%s @0x%x = NULL (table not built)' % (name, table_ptr))
        return
    n = dword(pid, p - 4)
    print('%s @0x%x = 0x%08x  len=%d' % (name, table_ptr, p, n if n is not None else -1))
    for i in range(min(n or 0, 16)):
        slot = dword(pid, p + i * 4)
        if not slot:
            print('   slot[%d] = nil' % i)
            continue
        ln = dword(pid, slot - 4)
        vals = read(pid, slot, 4 * min(ln or 0, 8))
        head = struct.unpack('<%dI' % (len(vals) // 4), vals) if vals and len(vals) >= 4 else ()
        print('   slot[%d] = 0x%08x len=%s head=%s' % (i, slot, ln, list(head)))


def snapshot(pid, tag):
    print('--- state @%s ---' % tag)
    print('layer records [0x5230b4] = 0x%08x' % (dword(pid, 0x5230b4) or 0))
    print('layer count   [0x52315c] = %s' % word(pid, 0x52315c))
    print('view index    [0x523158] = %s' % dword(pid, 0x523158))
    print('angles        [0x5230fc] = %s' % dword(pid, 0x5230fc))
    print('row metrics   [0x52308c/0x523090] = %s / %s' %
          (dword(pid, 0x52308c), dword(pid, 0x523090)))
    dump_table(pid, 'groupA(interleaved)', 0x52309c)
    dump_table(pid, 'groupB(layerlist)', 0x5230a0)
    recs = dword(pid, 0x5230b4)
    n = word(pid, 0x52315c) or 0
    if recs and n:
        gs = []
        for i in range(min(n, 50)):
            rec = read(pid, recs + i * 56, 56)
            gs.append(rec[0x2c] if rec else '?')
        print('layer group bytes (first %d): %s' % (len(gs), gs))


def dialogs(pid):
    out = []
    for h, cls, title, vis in win.windows(pid):
        if cls == '#32770' and vis:
            texts = [t for _, c, t in win.children(h, maxdepth=1) if c == 'Static' and t]
            out.append((h, texts))
    return out


def main():
    pkg = os.path.abspath(sys.argv[1])
    project = os.path.abspath(sys.argv[2])
    out_tif = os.path.join(pkg, '_probe.tif')
    rep, _ = dialogless_launch.launch(os.path.join(pkg, 'psdto3d101.exe'), pkg,
                                      project, out_tif)
    pid = rep['pid']
    time.sleep(4)
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]

    snapshot(pid, 'before open')

    win.command(hwnd, 3)          # open project
    for i in range(10):
        time.sleep(2)
        dl = dialogs(pid)
        snapshot(pid, 'after open +%ds' % ((i + 1) * 2))
        if dl:
            for h, texts in dl:
                print('DIALOG: %r' % (texts,))
            break

    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
