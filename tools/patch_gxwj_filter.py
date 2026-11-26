"""Add *.gxwj (99-era project files) to the open-project dialog filter.

The DFM property stream stores the filter as  <name 'Filter'> <vaString 06>
<len> <value>.  The replacement value is kept at EXACTLY the original length
(51 chars) so no following property (`Left`, `Top`, ...) shifts - earlier
attempts that grew the string corrupted the stream and the exe refused to
start (SxS 14001).

    python patch_gxwj_filter.py <exe> [--report r.json]

old value (51): tw3d2;tw3d|*.tw3d2;*.tw3d|tw3d2|*.tw3d2|tw3d|*.tw3d
new value (51): tw3d2;tw3d;gxwj|*.tw3d2;*.tw3d;*.gxwj|tw3d2|*.tw3d2
"""
import argparse
import json
import os
import shutil
import struct
import sys

import pefile

OLD = b'tw3d2;tw3d|*.tw3d2;*.tw3d|tw3d2|*.tw3d2|tw3d|*.tw3d'
NEW = b'tw3d2;tw3d;gxwj|*.tw3d2;*.tw3d;*.gxwj|tw3d2|*.tw3d2'
assert len(OLD) == len(NEW) == 51
ANCHOR = b'\x06Filter\x06' + bytes([len(OLD)]) + OLD + b'\x04Left'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('--report', default=None)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    i = data.find(ANCHOR)
    if i == -1:
        if data.find(b'\x06Filter\x06' + bytes([len(NEW)]) + NEW + b'\x04Left') != -1:
            print('already patched')
            return 0
        raise SystemExit('filter anchor not found')
    off = i + 9
    print('filter value at file 0x%x' % off)

    if a.dry_run:
        print('dry run: nothing written')
        return 0

    if not os.path.exists(a.exe + '.pre_gxwjfilter'):
        shutil.copy2(a.exe, a.exe + '.pre_gxwjfilter')

    v = off
    data[v:v + len(OLD)] = NEW

    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))

    chk = bytes(data).find(b'\x06Filter\x06' + bytes([len(NEW)]) + NEW + b'\x04Left')
    report = {
        'exe': os.path.abspath(a.exe),
        'value_file_offset': hex(off),
        'new': NEW.decode(),
        'stream_ok': chk != -1,
        'checksum': hex(checksum),
        'backup': a.exe + '.pre_gxwjfilter',
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0 if report['stream_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
