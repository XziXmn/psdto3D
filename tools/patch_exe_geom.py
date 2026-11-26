"""Force the two page-geometry globals right before mergtotiff is called.

Background
----------
mergtotiff takes four Int64 page-geometry parameters. Two of them are computed
from the globals [0x523074] / [0x52307C] (micrometres, converted to 1/10000 inch
by *10000/25400 at the call site). Without the software key the "apply settings"
routine aborts at its licence check, so those two globals stay 0, mergtotiff gets
a zero page size and raises "Invalid floating point operation".

This patch hooks the call site (0x5060E1, the `fild qword [0x52307C]` right before
the export call), writes the two globals, replays the original instruction and
jumps back. EXPERIMENT: the values are the ones a licensed run produced for a
10x12 cm project, used to verify which global is width and which is height.

Usage:
    python tools/patch_exe_geom.py <exe> -o out.exe --w-um 56950 --h-um 120000
"""
import argparse
import struct
import sys

import pefile

SITE = 0x5060E1          # fild qword [0x52307C]   (6 bytes)
RESUME = 0x5060E7        # fdiv dword [0x5062D8]
G_C = 0x523074           # global read by the second fild at 0x5060FA
G_D = 0x52307C           # global read by the fild at SITE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--w-um', type=int, required=True, help='0x523074 的值（微米）')
    ap.add_argument('--h-um', type=int, required=True, help='0x52307C 的值（微米）')
    a = ap.parse_args()

    d = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(a.exe)
    ib = pe.OPTIONAL_HEADER.ImageBase

    def align(v, al):
        return (v + al - 1) // al * al

    def va2off(va):
        for s in pe.sections:
            base = ib + s.VirtualAddress
            if base <= va < base + s.SizeOfRawData:
                return s.PointerToRawData + (va - base)
        raise SystemExit('VA 0x%X not in file' % va)

    # ---- 新节 ----
    last = pe.sections[-1]
    cave_rva = align(last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData), 0x1000)
    cave_va = ib + cave_rva

    code = bytearray()
    code += bytes.fromhex('9c60')                                  # pushfd; pushad
    for g, val in ((G_C, a.w_um), (G_C + 4, 0), (G_D, a.h_um), (G_D + 4, 0)):
        code += bytes.fromhex('c705') + struct.pack('<I', g) + struct.pack('<I', val)
    code += bytes.fromhex('619d')                                  # popad; popfd
    code += bytes.fromhex('df2d') + struct.pack('<I', G_D)         # fild qword [G_D]
    jmp_at = len(code)
    code += bytes.fromhex('e9') + struct.pack('<i', RESUME - (cave_va + jmp_at + 5))
    body = bytes(code)
    print('cave: %d bytes @ VA 0x%X' % (len(body), cave_va))

    raw_len = align(len(body), 0x200)
    new_raw = align(len(d), 0x200)
    d += bytes(new_raw - len(d))
    d += body + bytes(raw_len - len(body))

    fh = pe.FILE_HEADER.get_file_offset()
    oh = pe.OPTIONAL_HEADER.get_file_offset()
    nsec = pe.FILE_HEADER.NumberOfSections
    sh_off = oh + pe.FILE_HEADER.SizeOfOptionalHeader + nsec * 40
    struct.pack_into('<8sIIIIIIHHI', d, sh_off, b'.geomfix' + bytes(0), len(body),
                     cave_rva, raw_len, new_raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, fh + 2, nsec + 1)
    struct.pack_into('<I', d, oh + 56, align(cave_rva + len(body), 0x1000))

    # ---- 注入点 ----
    off = va2off(SITE)
    old = bytes(d[off:off + 6])
    if old != bytes.fromhex('df2d7c305200'):
        raise SystemExit('site bytes unexpected: %s' % old.hex())
    d[off:off + 5] = bytes.fromhex('e9') + struct.pack('<i', cave_va - (SITE + 5))
    print('hook 0x%X -> 0x%X' % (SITE, cave_va))

    open(a.output, 'wb').write(bytes(d))
    print('written %s (%d bytes)' % (a.output, len(d)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
