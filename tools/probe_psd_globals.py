"""Read the globals passed to zu06.dll!writepsd during a PSD export.

Call site (10.1 exe 0x50B14C):
    push [0x52315E] push [0x5230D4] push [0x5230D0] push [0x5230FC]
    push [0x523174] push [0x523170] push [0x5231AC] push [0x5231A8]
    push [0x523234] push <filename>  call [0x523278]   ; writepsd
"""
import ctypes
import os
import struct
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

k32 = ctypes.windll.kernel32
k32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

GLOBALS = {
    '0x5231A8': 0x5231A8,
    '0x5231AC': 0x5231AC,
    '0x523170': 0x523170,
    '0x523174': 0x523174,
    '0x5230D0': 0x5230D0,
    '0x5230D4': 0x5230D4,
    '0x52315E': 0x52315E,
    '0x5230FC': 0x5230FC,
    '0x523074': 0x523074,
    '0x52307C': 0x52307C,
    '0x52306C': 0x52306C,
    '0x5231A0': 0x5231A0,
}


def rd(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return buf.raw[:got.value]
    return None


def main():
    pkg = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else r'_work/emu1')
    subprocess = sp
    subprocess.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'],
                   stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(0.5)
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    if not hwnd:
        print('no window')
        return 1
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)

    sched = [(10, 7), (45, 10), (70, 12), (150, 16)]
    t0 = time.time()
    done = 0
    while time.time() - t0 < 200:
        el = time.time() - t0
        if done < len(sched) and el >= sched[done][0]:
            win.command(hwnd, sched[done][1])
            print('t=%.0f send %d' % (el, sched[done][1]))
            done += 1
        time.sleep(0.2)

    print('--- globals after TIFF export')
    for name, addr in GLOBALS.items():
        raw = rd(h, addr, 4)
        if raw and len(raw) == 4:
            print('  %s = %d (0x%08X)' % (name, struct.unpack('<i', raw)[0], struct.unpack('<I', raw)[0]))
        else:
            print('  %s = <unreadable>' % name)

    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
