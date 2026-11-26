"""把加密狗当磁盘整块读出来（需要管理员权限）。"""
import ctypes
import sys
from ctypes import wintypes

BS = chr(92)
k32 = ctypes.windll.kernel32
k32.CreateFileA.restype = wintypes.HANDLE
k32.CreateFileA.argtypes = [wintypes.LPCSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                            wintypes.HANDLE]
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                 ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]


def open_dev(path):
    h = k32.CreateFileA(path.encode(), 0x80000000, 3, None, 3, 0, None)
    hv = int(h) & 0xFFFFFFFFFFFFFFFF
    if hv == 0xFFFFFFFFFFFFFFFF:
        return None, k32.GetLastError()
    return hv, 0


def read_at(h, off, n):
    newpos = ctypes.c_longlong(0)
    k32.SetFilePointerEx(wintypes.HANDLE(h), ctypes.c_longlong(off),
                         ctypes.byref(newpos), 0)
    buf = ctypes.create_string_buffer(n)
    got = wintypes.DWORD(0)
    ok = k32.ReadFile(wintypes.HANDLE(h), buf, n, ctypes.byref(got), None)
    if not ok:
        return None, k32.GetLastError()
    return buf.raw[:got.value], 0


def main():
    paths = [BS * 2 + '.' + BS + 'PhysicalDrive' + s for s in sys.argv[2:]] or \
            [BS * 2 + '.' + BS + 'PhysicalDrive1']
    for p in paths:
        h, err = open_dev(p)
        print(p, 'handle', h, 'err', err)
        if h is None:
            continue
        data = b''
        off = 0
        total = 1049088
        while off < total:
            b, e = read_at(h, off, min(65536, total - off))
            if b is None:
                print('  read fail at', off, 'err', e)
                break
            if not b:
                break
            data += b
            off += len(b)
        print('  read', len(data), 'bytes')
        out = 'dongle/' + ('phys%d.bin' % int(p.rsplit('Drive', 1)[-1]))
        with open(out, 'wb') as f:
            f.write(data)
        print('  saved', out)


if __name__ == '__main__':
    main()
