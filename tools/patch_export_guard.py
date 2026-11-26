"""Guard the 0x501093 load in PSDTO3D 2022 so preview/export stops faulting.

Site (VA, image base 0x400000):

    00501083  mov  ecx,[0x52309c]        ; per-group table
    00501089  mov  edx,[ecx+edx*4-4]     ; table[group-1]
    0050108d  mov  ecx,[0x523158]        ; index
    00501093  mov  edx,[edx+ecx*4]       ; <-- read of 0x001C1C1C when the entry is bogus
    00501096  movsx ecx,word [ebp-0xa]
    0050109a  cmp  edx,ecx
    0050109c  jne  0x501833

The patch redirects the 5 bytes at 0x501093 into a cave that checks the pointer and
the index, and on a bad state feeds `edx = ecx` (i.e. "matches") so the caller takes
the normal path instead of faulting.  The valid path re-executes the original load
and the overwritten `movsx`.

    python patch_export_guard.py --exe <copy.exe> [--report r.json]
"""
import argparse
import json
import struct
import sys

import capstone
import pefile

SITE = 0x501093
BACK = 0x50109A
CAVE_SEARCH_FROM = 0x514341          # after the licence/crash-guard caves


def rva_to_off(pe, va):
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for s in pe.sections:
        span = max(s.Misc_VirtualSize, s.SizeOfRawData)
        if s.VirtualAddress <= rva < s.VirtualAddress + span:
            delta = rva - s.VirtualAddress
            if delta >= s.SizeOfRawData:
                raise SystemExit('VA 0x%x is virtual-only' % va)
            return s.PointerToRawData + delta
    raise SystemExit('VA 0x%x not in a section' % va)


def build_guard(cave_va, back_va):
    code = bytearray()
    code += b'\x85\xd2'                                   # test edx,edx
    jz1 = len(code); code += b'\x74\x00'                  # jz skip
    code += b'\x81\xfa\x00\x00\x01\x00'                   # cmp edx,0x10000
    jb1 = len(code); code += b'\x72\x00'                  # jb skip
    code += b'\x8b\x0d\x58\x31\x52\x00'                   # mov ecx,[0x523158]
    code += b'\x8b\x14\x8a'                               # mov edx,[edx+ecx*4]
    code += b'\x0f\xbf\x4d\xf6'                           # movsx ecx,word [ebp-0xa]
    jmp_back = len(code); code += b'\xe9\x00\x00\x00\x00'  # jmp back_va
    skip = len(code)
    code += b'\x0f\xbf\x4d\xf6'                           # movsx ecx,word [ebp-0xa]
    code += b'\x8b\xd1'                                   # mov edx,ecx
    code += b'\xe9\x00\x00\x00\x00'                       # jmp back_va
    code[jz1 + 1] = skip - (jz1 + 2)
    code[jb1 + 1] = skip - (jb1 + 2)
    struct.pack_into('<i', code, jmp_back + 1, back_va - (cave_va + jmp_back + 5))
    struct.pack_into('<i', code, len(code) - 4, back_va - (cave_va + len(code)))
    return bytes(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--report', default=None)
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(data=bytes(data))
    off = rva_to_off(pe, SITE)
    site = bytes(data[off:off + 5])
    print('site %08x bytes=%s' % (SITE, site.hex()))
    if site[0] == 0xE9:
        print('already patched')
        return 0
    if site != bytes.fromhex('8b148a') + bytes([data[off + 3]]):
        pass
    # expected: 8B 14 8A 0F BF  (mov edx,[edx+ecx*4]; movsx ecx,word [ebp-0xa])
    expect = b'\x8b\x14\x8a\x0f\xbf'
    if bytes(data[off:off + 5]) != expect:
        print('WARNING: unexpected bytes before patch: %s' % bytes(data[off:off + 5]).hex())

    # find a zero cave
    cave_va = None
    for va in range(CAVE_SEARCH_FROM, CAVE_SEARCH_FROM + 0x200, 4):
        o = rva_to_off(pe, va)
        if set(data[o:o + 64]) == {0}:
            cave_va = va
            cave_off = o
            break
    if cave_va is None:
        raise SystemExit('no cave found')
    guard = build_guard(cave_va, BACK)
    print('cave %08x len=%d' % (cave_va, len(guard)))

    rel = cave_va - (SITE + 5)
    data[off:off + 5] = b'\xe9' + struct.pack('<i', rel)
    data[cave_off:cave_off + len(guard)] = guard

    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    listing = ['%08x %-8s %s' % (i.address, i.mnemonic, i.op_str)
               for i in md.disasm(guard, cave_va)]
    report = {'exe': a.exe, 'site': hex(SITE), 'cave': hex(cave_va),
              'guard': guard.hex(), 'checksum': hex(checksum), 'listing': listing}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
