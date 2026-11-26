"""Recompute the three config values mergtotiff gets from the encrypted blob.

Background
----------
At 0x47F9BA mergtotiff calls 0x4626B4 with 21 out-parameters; that routine is the
decryptor for the vendor's .enc blobs and needs the software key. Without it the
three doubles at [ebp-0x1A8] / [-0x1B0] / [-0x1B8] stay 0.

They are not secrets - they are derived from the four page parameters that arrived
from the caller:

    [-0x1A8] = 1.0                     (mode flag)
    [-0x1B0] = width_in  * lpi         (lenticules across)
    [-0x1B8] = height_in * dpi         (rows)

Verified against a licensed frame dump: 94.488 / 1474.0752.

This patch hooks 0x47F9BF (the `fld qword [ebp-0x1A8]` right after the call),
computes the three values, replays the original instruction and jumps back.

Usage:
    python tools/patch_merg_cfg.py <cmyktiff2.dll> -o out.dll
"""
import argparse
import struct
import sys

import capstone
import pefile

SITE = 0x47F9BF          # dd 85 58 fe ff ff   fld qword [ebp-0x1A8]
RESUME = 0x47F9C5        # d8 0d c8 32 48 00   fmul dword [0x4832C8]
SITE2 = 0x47FBF1         # 33 c0 89 85 e0 fe ff ff   xor eax,eax ; mov [ebp-0x120],eax
RESUME2 = 0x47FBF9


def disp(v):
    return struct.pack('<i', v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args()

    d = bytearray(open(a.src, 'rb').read())
    pe = pefile.PE(a.src)
    ib = pe.OPTIONAL_HEADER.ImageBase
    code = pe.sections[0]

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

    c = bytearray()
    c += bytes.fromhex('9c60')                                   # pushfd; pushad
    # [-0x1b0] = [-0x198] * [-0x190]     width_in * lpi
    c += bytes.fromhex('dd85') + disp(-0x198)                    # fld  qword [ebp-0x198]
    c += bytes.fromhex('dc8d') + disp(-0x190)                    # fmul qword [ebp-0x190]
    c += bytes.fromhex('dd9d') + disp(-0x1b0)                    # fstp qword [ebp-0x1b0]
    # [-0x1b8] = [-0x1a0] * [-0x188]     height_in * dpi
    c += bytes.fromhex('dd85') + disp(-0x1a0)
    c += bytes.fromhex('dc8d') + disp(-0x188)
    c += bytes.fromhex('dd9d') + disp(-0x1b8)
    # [-0x1a8] = 1.0
    c += bytes.fromhex('d9e8')                                   # fld1
    c += bytes.fromhex('dd9d') + disp(-0x1a8)                    # fstp qword [ebp-0x1a8]
    c += bytes.fromhex('619d')                                   # popad; popfd
    c += bytes.fromhex('dd85') + disp(-0x1a8)                    # 重放: fld qword [ebp-0x1A8]
    j = len(c)
    c += bytes.fromhex('e9') + struct.pack('<i', RESUME - (cave_va + j + 5))
    # ---- 第二块：把 [-0x124] / [-0x128] 换回来（无狗时对象报的是转置尺寸）----
    c2base = len(c)
    c += bytes.fromhex('9c60')
    c += bytes.fromhex('8b85') + disp(-0x124)      # mov eax,[ebp-0x124]
    c += bytes.fromhex('8b95') + disp(-0x128)      # mov edx,[ebp-0x128]
    c += bytes.fromhex('8995') + disp(-0x124)      # mov [ebp-0x124],edx
    c += bytes.fromhex('8985') + disp(-0x128)      # mov [ebp-0x128],eax
    c += bytes.fromhex('619d')
    c += bytes.fromhex('33c08985e0feffff')         # 重放 xor eax,eax ; mov [ebp-0x120],eax
    j2 = len(c)
    c += bytes.fromhex('e9') + struct.pack('<i', RESUME2 - (cave_va + j2 + 5))
    body = bytes(c)
    print('cave: %d 字节 @ VA 0x%X' % (len(body), cave_va))

    raw_len = align(len(body), 0x200)
    new_raw = align(len(d), 0x200)
    d += bytes(new_raw - len(d))
    d += body + bytes(raw_len - len(body))

    fh = pe.FILE_HEADER.get_file_offset()
    oh = pe.OPTIONAL_HEADER.get_file_offset()
    nsec = pe.FILE_HEADER.NumberOfSections
    sh_off = oh + pe.FILE_HEADER.SizeOfOptionalHeader + nsec * 40
    struct.pack_into('<8sIIIIIIHHI', d, sh_off, b'.mergecfg', len(body),
                     cave_rva, raw_len, new_raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, fh + 2, nsec + 1)
    struct.pack_into('<I', d, oh + 56, align(cave_rva + len(body), 0x1000))

    off = va2off(SITE)
    old = bytes(d[off:off + 6])
    if old != bytes.fromhex('dd8558feffff'):
        raise SystemExit('site bytes unexpected: %s' % old.hex())
    d[off:off + 5] = bytes.fromhex('e9') + struct.pack('<i', cave_va - (SITE + 5))
    print('hook 0x%X -> 0x%X' % (SITE, cave_va))
    off2 = va2off(SITE2)
    old2 = bytes(d[off2:off2 + 8])
    if old2 != bytes.fromhex('33c08985e0feffff'):
        raise SystemExit('site2 bytes unexpected: %s' % old2.hex())
    blk2_va = cave_va + c2base
    d[off2:off2 + 5] = bytes.fromhex('e9') + struct.pack('<i', blk2_va - (SITE2 + 5))
    print('hook 0x%X -> 0x%X   written %s (%d bytes)' % (SITE2, blk2_va, a.output, len(d)))
    open(a.output, 'wb').write(bytes(d))
    return 0


if __name__ == '__main__':
    sys.exit(main())
