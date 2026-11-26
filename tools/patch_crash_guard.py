"""Add a null-guard to the PSDTO3D 3D-view generator (fixes the 0x50A001 crash).

Why the crash happens
---------------------
The generator sizes its per-group layer tables by the maximum group number and
then walks every slot:

    mov  eax, [layerTable]        ; array of per-group lists (may hold nil slots)
    mov  eax, [eax + ebx*4]       ; list of layer indexes for group ebx
    ...
    mov  eax, [eax + edi*4]       ; <-- crash when the slot is nil (read of 0)

A project whose layer groups are sparse (e.g. every layer in group 5, so groups
1..4 exist as empty slots) therefore dereferences NULL.  See
docs/故障诊断_浮点异常与AV.md.

What this patch does
--------------------
It redirects the three loads at the fault site into a code cave that checks for a
nil table and a nil group list, and skips the inner iteration instead of reading
through NULL.  The normal path is byte-for-byte identical.

    python patch_crash_guard.py <exe> [--report report.json]
"""
import argparse
import json
import os
import shutil
import struct
import sys

import capstone
import pefile

# mov eax,[<layerTable>] ; mov eax,[eax+ebx*4] ; mov eax,[eax+edi*4]
SITE_PREFIX = b'\xa1'


def find_site(pe, blob, start):
    """Locate the 11-byte site: A1 <g> 8B 04 98 8B 04 B8."""
    needle = b'\x8b\x04\x98\x8b\x04\xb8'
    i = blob.find(needle)
    while i != -1:
        if i >= 5 and blob[i - 5] == 0xA1:
            return start + i - 5, blob[i - 5:i + 6]
        i = blob.find(needle, i + 1)
    raise SystemExit('fault site not found (pattern mismatch)')


def find_patched_site(pe, blob, start):
    """Detect an already-patched site: `E9 rel32` + 6 NOPs whose target starts with
    `mov eax,[g] ; test eax,eax ; jz`."""
    i = blob.find(b'\xe9')
    while i != -1:
        chunk = blob[i:i + 11]
        if len(chunk) == 11 and chunk[5:] == b'\x90' * 6:
            rel = struct.unpack('<i', chunk[1:5])[0]
            target = start + i + 5 + rel
            off = target - start
            if 0 <= off < len(blob) - 9:
                t = blob[off:off + 9]
                if t[0] == 0xA1 and t[5:7] == b'\x85\xc0' and t[7] == 0x74:
                    return start + i, chunk, target
        i = blob.find(b'\xe9', i + 1)
    return None, None, None


def find_cave(pe, data, blob_start, blob_len, need):
    """Return (va, file_offset) of a zero run at the end of the code section."""
    for s in pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        tail_off = s.PointerToRawData + s.Misc_VirtualSize
        tail_len = s.SizeOfRawData - s.Misc_VirtualSize
        if tail_len >= need and set(data[tail_off:tail_off + need]) == {0}:
            return pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress + s.Misc_VirtualSize, tail_off
    raise SystemExit('no zero cave found at the end of a code section')


def build_guard(cave_va, global_va, back_va, skip_va):
    code = bytearray()
    code += b'\xa1' + struct.pack('<I', global_va)      # mov eax,[global]
    code += b'\x85\xc0'                                  # test eax,eax
    jz1 = len(code); code += b'\x74\x00'                 # jz skip
    code += b'\x8b\x04\x98'                              # mov eax,[eax+ebx*4]
    code += b'\x85\xc0'                                  # test eax,eax
    jz2 = len(code); code += b'\x74\x00'                 # jz skip
    code += b'\x8b\x04\xb8'                              # mov eax,[eax+edi*4]
    jmp_back = len(code); code += b'\xe9\x00\x00\x00\x00'  # jmp back_va
    skip_off = len(code)
    code += b'\xe9\x00\x00\x00\x00'                      # jmp skip_va
    # resolve
    code[jz1 + 1] = skip_off - (jz1 + 2)
    code[jz2 + 1] = skip_off - (jz2 + 2)
    struct.pack_into('<i', code, jmp_back + 1, back_va - (cave_va + jmp_back + 5))
    struct.pack_into('<i', code, skip_off + 1, skip_va - (cave_va + skip_off + 5))
    return bytes(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('--report', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true', help='re-apply even when the guard is already present')
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(data=bytes(data))
    base = pe.OPTIONAL_HEADER.ImageBase
    code_sec = [s for s in pe.sections if s.Characteristics & 0x20000000][0]
    blob_off, blob_len = code_sec.PointerToRawData, code_sec.SizeOfRawData
    start_va = base + code_sec.VirtualAddress
    blob = bytes(data[blob_off:blob_off + blob_len])
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True

    patched_va, patched_bytes, cave_hint = find_patched_site(pe, blob, start_va)
    if patched_va is not None and not a.force:
        off = cave_hint - start_va
        code = blob[off:off + 29]
        dis = list(md.disasm(bytes(code), cave_hint))
        report = {
            'exe': os.path.abspath(a.exe),
            'state': 'already patched',
            'site_va': hex(patched_va),
            'site_bytes': patched_bytes.hex(),
            'cave_va': hex(cave_hint),
            'cave_listing': ['%08x %-8s %s' % (i.address, i.mnemonic, i.op_str) for i in dis],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if a.report:
            with open(a.report, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        return 0

    site_va, site_bytes = find_site(pe, blob, start_va)
    global_va = struct.unpack('<I', site_bytes[1:5])[0]
    print('site va=0x%x bytes=%s global=0x%x' % (site_va, site_bytes.hex(), global_va))
    # the code that follows the site
    back_va = site_va + 11            # mov edx,[<destTable>] ...
    # the skip target: "inc esi" right after the write
    follow = list(md.disasm(blob[site_va - start_va + 11: site_va - start_va + 40], back_va))
    skip_va = None
    for ins in follow:
        if ins.mnemonic == 'inc' and ins.op_str == 'esi':
            skip_va = ins.address
            break
    if skip_va is None:
        raise SystemExit('skip target (inc esi) not found')
    print('back=0x%x skip(inc esi)=0x%x' % (back_va, skip_va))

    cave_va, cave_off = find_cave(pe, data, blob_off, blob_len, 32)
    guard = build_guard(cave_va, global_va, back_va, skip_va)
    print('cave va=0x%x len=%d bytes=%s' % (cave_va, len(guard), guard.hex()))

    if a.dry_run:
        print('dry run: nothing written')
        return 0

    shutil.copy2(a.exe, a.exe + '.pre_guard')
    # jump at the site
    site_off = blob_off + (site_va - start_va)
    rel = cave_va - (site_va + 5)
    data[site_off:site_off + 11] = b'\xe9' + struct.pack('<i', rel) + b'\x90' * 6
    data[cave_off:cave_off + len(guard)] = guard

    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))

    verify = pefile.PE(a.exe, fast_load=True)
    blob2 = open(a.exe, 'rb').read()[blob_off:blob_off + blob_len]
    site_after = blob2[site_va - start_va: site_va - start_va + 11]
    cave_after = blob2[cave_va - start_va: cave_va - start_va + len(guard)]
    dis = list(md.disasm(bytes(cave_after), cave_va))
    report = {
        'exe': os.path.abspath(a.exe),
        'site_va': hex(site_va),
        'global': hex(global_va),
        'cave_va': hex(cave_va),
        'back_va': hex(back_va),
        'skip_va': hex(skip_va),
        'site_before': site_bytes.hex(),
        'site_after': site_after.hex(),
        'cave_bytes': guard.hex(),
        'checksum': hex(checksum),
        'cave_listing': ['%08x %-8s %s' % (i.address, i.mnemonic, i.op_str) for i in dis],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())

