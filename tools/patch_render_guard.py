"""Guard every group-table render check in PSDTO3D (fixes 0x5023C7-class AVs).

Why the crash happens
---------------------
Several render/export loops validate each layer against the interleaved
per-group table:

    movsx edx, ax                  ; group number (1..99)
    mov  ecx, [0x52309c]           ; interleaved per-group table
    mov  edx, [ecx + edx*4 - 4]    ; table[group-1]  (slot pointer)
    mov  ecx, [0x523158]           ; view index
    mov  edx, [edx + ecx*4]        ; <-- AV: slot nil / table nil / index OOB

The table is (re)built by 0x509E44 in three phases; while a large PSD is still
loading a repaint can run between the outer SetLength (all slots nil) and the
per-slot fills, so table[group-1] is nil and the read faults at address 0.

What this patch does
--------------------
Replaces the 34-byte check block at each site with a jump into a code cave that
re-runs the same comparison but treats "unknown" as a match (layer is drawn):

    table nil / group > len(table) / slot nil / view index >= len(slot)  ->  match
    otherwise compare table[group-1][idx] against the layer number as before.

Only edx/ecx are touched; eax (the group, still read by the fallthrough
`cmp ax,0x64`) is preserved, and ecx is restored to the layer number on the
match exit so the original fallthrough state is reproduced exactly.

Modes
-----
    patch_render_guard.py <exe>            # the two built-in sites (import/export)
    patch_render_guard.py <exe> --scan     # every unguarded copy, cave per site
    patch_render_guard.py <exe> --scan --force
"""
import argparse
import json
import os
import shutil
import struct
import sys

import capstone
import pefile

BASE = 0x400000

CHECK_PREFIX = bytes.fromhex(
    '0fbfd0'          # movsx edx, ax
    '8b0d9c305200'    # mov ecx, [0x52309c]
    '8b5491fc'        # mov edx, [ecx+edx*4-4]
    '8b0d58315200'    # mov ecx, [0x523158]
    '8b148a'          # mov edx, [edx+ecx*4]
    '0fbf4df6'        # movsx ecx, word [ebp-0xa]
    '3bd1'            # cmp edx, ecx
)  # 28 bytes
SITE_LEN = 34  # prefix (28) + 0F 85 rel32 (6)

SITES = [
    {'name': 'import/paint', 'va': 0x5023B4, 'mismatch': 0x502BDB, 'fallthrough': 0x5023D6},
    {'name': 'export',       'va': 0x501080, 'mismatch': 0x501833, 'fallthrough': 0x5010A2},
]

TABLE_A = 0x52309C   # interleaved per-group table (read here)
IDX_G = 0x523158     # view index


def build_guard(cave_va, fall_va, mismatch_va, ebp_off=0xA):
    """Assemble the guarded comparison; returns bytes."""
    code = bytearray()
    code += b'\x0f\xbf\xd0'                                   # movsx edx, ax
    code += b'\x8b\x0d' + struct.pack('<I', TABLE_A)
    code += b'\x85\xc9'
    jz1 = len(code); code += b'\x74\x00'                      # je match
    code += b'\x3b\x51\xfc'                                   # cmp edx, [ecx-4]
    jg1 = len(code); code += b'\x7f\x00'                      # jg match
    code += b'\x8b\x54\x91\xfc'                               # mov edx, [ecx+edx*4-4]
    code += b'\x85\xd2'
    jz2 = len(code); code += b'\x74\x00'                      # je match
    code += b'\x8b\x0d' + struct.pack('<I', IDX_G)
    code += b'\x3b\x4a\xfc'                                   # cmp ecx, [edx-4]
    jge1 = len(code); code += b'\x7d\x00'                     # jge match
    code += b'\x8b\x14\x8a'                                   # mov edx, [edx+ecx*4]
    code += b'\x0f\xbf\x4d' + bytes([(256 - ebp_off) & 0xFF])
    code += b'\x3b\xd1'
    jne1 = len(code); code += b'\x0f\x85\x00\x00\x00\x00'     # jne mismatch
    match_off = len(code)
    code += b'\x0f\xbf\x4d' + bytes([(256 - ebp_off) & 0xFF])
    jmp_fall = len(code); code += b'\xe9\x00\x00\x00\x00'     # jmp fall
    jmp_mis = len(code); code += b'\xe9\x00\x00\x00\x00'      # jmp mismatch

    code[jz1 + 1] = match_off - (jz1 + 2)
    code[jg1 + 1] = match_off - (jg1 + 2)
    code[jz2 + 1] = match_off - (jz2 + 2)
    code[jge1 + 1] = match_off - (jge1 + 2)
    struct.pack_into('<i', code, jne1 + 2, mismatch_va - (cave_va + jne1 + 6))
    struct.pack_into('<i', code, jmp_fall + 1, fall_va - (cave_va + jmp_fall + 5))
    struct.pack_into('<i', code, jmp_mis + 1, mismatch_va - (cave_va + jmp_mis + 5))
    return bytes(code)


def va_to_off(pe, va):
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + s.SizeOfRawData:
            return s.PointerToRawData + (rva - s.VirtualAddress)
    raise SystemExit('va 0x%x not mapped' % va)


def find_cave_run(data, need, min_off=0):
    """Return (off, va, size) of a zero run >= need at/after min_off:
    executable-section tail first, then any zero run in an executable section."""
    pe = pefile.PE(data=bytes(data))
    for s in pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        tail_off = max(s.PointerToRawData + s.Misc_VirtualSize, min_off)
        tail_end = s.PointerToRawData + s.SizeOfRawData
        if tail_end - tail_off >= need and set(data[tail_off:tail_off + need]) == {0}:
            va = pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress + (tail_off - s.PointerToRawData)
            return tail_off, va, tail_end - tail_off
    best_run = 0
    best_off = None
    for s in pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        blob = data[s.PointerToRawData: s.PointerToRawData + s.SizeOfRawData]
        run = 0
        for i, b in enumerate(blob):
            run = run + 1 if b == 0 else 0
            if run > best_run:
                best_run = run
                best_off = s.PointerToRawData + i - run + 1
    if best_off is None or best_run < need:
        raise SystemExit('no zero cave of %d bytes found' % need)
    for s in pe.sections:
        if s.PointerToRawData <= best_off < s.PointerToRawData + s.SizeOfRawData:
            va = pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress + (best_off - s.PointerToRawData)
            return best_off, va, best_run
    raise SystemExit('cave offset not in any section')


def scan_sites(blob, start_va):
    """Find every check copy by pattern; return per-site dicts with targets."""
    import re as _re
    pat = _re.compile(_re.escape(bytes.fromhex('0fbfd08b0d')) + b'(....)' +
                      _re.escape(bytes.fromhex('8b5491fc8b0d')) + b'(....)' +
                      _re.escape(bytes.fromhex('8b148a')) + b'(....)')
    sites = []
    for mm in pat.finditer(blob):
        va = start_va + mm.start()
        tail = blob[mm.start() + 26: mm.start() + 34]
        if tail[:2] != b'\x3b\xd1' or tail[2:4] != b'\x0f\x85':
            continue
        rel = struct.unpack('<i', tail[4:8])[0]
        sites.append({'name': 'scan@0x%x' % va, 'va': va,
                      'mismatch': va + 34 + rel, 'fallthrough': va + 34})
    return sites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('--report', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--scan', action='store_true',
                    help='scan for ALL unguarded check copies instead of the built-in sites')
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(data=bytes(data))
    code_sec = [s for s in pe.sections if s.Characteristics & 0x20000000][0]
    blob_off = code_sec.PointerToRawData
    blob = bytes(data[blob_off:blob_off + code_sec.SizeOfRawData])
    start_va = pe.OPTIONAL_HEADER.ImageBase + code_sec.VirtualAddress

    work = scan_sites(blob, start_va) if a.scan else SITES

    guards = []
    already = True
    for site in work:
        off = va_to_off(pe, site['va'])
        chunk = bytes(data[off:off + SITE_LEN])
        fixed = struct.pack('<i', site['mismatch'] - site['fallthrough'])
        expected = CHECK_PREFIX + b'\x0f\x85' + fixed
        if chunk == expected:
            already = False
            guards.append((site, off, 'clean', chunk))
        elif chunk[0] == 0xE9 and chunk[5:] == b'\x90' * (SITE_LEN - 5):
            guards.append((site, off, 'patched', chunk))
        else:
            raise SystemExit('site %s (0x%x) bytes mismatch: %s' %
                             (site['name'], site['va'], chunk.hex()))

    todo = [(s, o) for (s, o, st, _) in guards if st == 'clean' or a.force]
    if not todo and already and not a.force:
        print('all %d sites already patched; nothing to do' % len(work))
        return 0

    glen = len(build_guard(0, SITES[0]['fallthrough'], SITES[0]['mismatch']))
    caves = []
    cur_off = cur_va = cur_size = 0
    min_off = 0
    for _ in todo:
        if cur_size < glen:
            cur_off, cur_va, cur_size = find_cave_run(data, glen, min_off=min_off)
            min_off = cur_off + cur_size
        caves.append((cur_off, cur_va))
        cur_off += glen
        cur_va += glen
        cur_size -= glen
    print('%d site(s) to guard, caves allocated' % len(todo))

    if a.dry_run:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for i, (site, off) in enumerate(todo):
            gva = caves[i][1]
            g = build_guard(gva, site['fallthrough'], site['mismatch'])
            print('--- site %s 0x%x -> cave 0x%x (fall=0x%x, mis=0x%x)' %
                  (site['name'], site['va'], gva, site['fallthrough'], site['mismatch']))
            for ins in md.disasm(g, gva):
                print('  %08x  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
        print('dry run: nothing written')
        return 0

    if not os.path.exists(a.exe + '.pre_renderguard'):
        shutil.copy2(a.exe, a.exe + '.pre_renderguard')

    report = {'exe': os.path.abspath(a.exe), 'sites': []}
    for i, (site, off) in enumerate(todo):
        gva, goff = caves[i][1], caves[i][0]
        guard = build_guard(gva, site['fallthrough'], site['mismatch'])
        rel = gva - (site['va'] + 5)
        data[off:off + SITE_LEN] = b'\xe9' + struct.pack('<i', rel) + b'\x90' * (SITE_LEN - 5)
        data[goff:goff + len(guard)] = guard

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        entry = {
            'name': site['name'],
            'site_va': hex(site['va']),
            'site_before': guards[i][3].hex() if guards[i][2] == 'clean' else '',
            'site_after': bytes(data[off:off + SITE_LEN]).hex(),
            'cave_va': hex(gva),
            'cave_bytes': guard.hex(),
            'fallthrough_va': hex(site['fallthrough']),
            'mismatch_va': hex(site['mismatch']),
            'cave_listing': ['%08x %-8s %s' % (ins.address, ins.mnemonic, ins.op_str)
                             for ins in md.disasm(guard, gva)],
        }
        report['sites'].append(entry)
        print('patched %s: site 0x%x -> cave 0x%x' % (site['name'], site['va'], gva))

    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))
    report['checksum'] = hex(checksum)
    report['backup'] = a.exe + '.pre_renderguard'

    print(json.dumps({'checksum': hex(checksum), 'backup': report['backup'],
                      'sites': [{k: v for k, v in s.items() if k != 'cave_listing'}
                                for s in report['sites']]}, indent=2, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
