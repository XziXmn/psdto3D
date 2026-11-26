"""Fix the `Invalid numeric input` dialog when opening projects whose PSD sits
in the same directory (PSDTO3D 2022).

Root cause (established 2026-11-17)
-----------------------------------
Opening a project whose line-1 PSD resolves inside the project directory runs
the full loader 0x511408.  Its token grammar is

    line 3  "99100 <layers> <w> <h>"
    block   <layers> angle lines      (one integer each)
    block   <layers> "angle group scale" lines   (scale is a FLOAT)
    rest    curve headers "a b c count" + <count> integer point pairs

The two block loops take their iteration count from [ebp-0x60], computed by the
layout helper 0x4D2F14 from the line-8 flags + layer count.  For current files
that value does not equal the layer count, so the token stream misaligns and
the curve-header reader (integer reads, helper 0x403334) lands on the layer
lines' float scales ("1.00000000000000E+0000").  Val-as-integer fails ->
InOutRes=106 -> Delphi raises EInOutError `Invalid numeric input`; the SEH-swallowed
aftermath leaves half-built tables (the `blank canvas` symptom).

The format spec is `<layers> integers + <layers> layer lines` (see
docs/工程文件格式.md), i.e. both loop counts must simply be the layer count,
which the function already holds in [ebp-0x54].

What this patch does
--------------------
Two 3-byte, length-identical rewrites in 0x511408:

    0x511A03  mov eax,[ebp-0x60]  ->  mov eax,[ebp-0x54]   (angle-line loop)
    0x511A81  mov eax,[ebp-0x60]  ->  mov eax,[ebp-0x54]   (layer-line loop)

    python patch_layout_count.py <exe> [--report r.json] [--dry-run] [--force]
"""
import argparse
import json
import os
import shutil
import struct
import sys

import pefile

SITES = [
    {'va': 0x511A03, 'why': 'angle-line loop count'},
    {'va': 0x511A81, 'why': 'layer-line loop count'},
]
BEFORE = bytes.fromhex('8b45a0')   # mov eax, [ebp-0x60]
AFTER = bytes.fromhex('8b45ac')    # mov eax, [ebp-0x54]


def va_to_off(pe, va):
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + s.SizeOfRawData:
            return s.PointerToRawData + (rva - s.VirtualAddress)
    raise SystemExit('va 0x%x not mapped' % va)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('--report', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(data=bytes(data))

    already = True
    plan = []
    for site in SITES:
        off = va_to_off(pe, site['va'])
        cur = bytes(data[off:off + 3])
        if cur == AFTER:
            plan.append((site, off, 'patched'))
        elif cur == BEFORE:
            already = False
            plan.append((site, off, 'clean'))
        else:
            raise SystemExit('site 0x%x bytes %s unexpected' % (site['va'], cur.hex()))

    if already and not a.force:
        print('already patched; nothing to do')
        return 0

    for site, off, st in plan:
        print('site 0x%x (%s): %s -> %s' %
              (site['va'], site['why'], bytes(data[off:off + 3]).hex(), AFTER.hex()))

    if a.dry_run:
        print('dry run: nothing written')
        return 0

    if not os.path.exists(a.exe + '.pre_layoutcount'):
        shutil.copy2(a.exe, a.exe + '.pre_layoutcount')

    for site, off, st in plan:
        if st == 'clean' or a.force:
            data[off:off + 3] = AFTER

    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))

    report = {
        'exe': os.path.abspath(a.exe),
        'backup': a.exe + '.pre_layoutcount',
        'patch': 'block-loop count := layer count ([ebp-0x54])',
        'sites': [{'va': hex(s['va']), 'why': s['why'],
                   'before': BEFORE.hex(), 'after': AFTER.hex()} for s in SITES],
        'checksum': hex(checksum),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
