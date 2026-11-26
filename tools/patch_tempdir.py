"""Force PSDTO3D's hard-coded work folder onto the system drive.

The application selects between "D:\\ok3dtemp\\", "E:\\ok3dtemp\\" and "C:\\ok3dtemp\\"
depending on some drive probe; on a machine without D:/E: it fails with
"Cannot create file \"D:\\ok3dtemp\\g1.bmp\"".  All three literals have the same
length, so rewriting the drive letter keeps the Delphi length prefix valid.

    python patch_tempdir.py --exe <exe> [--drive C] [--report r.json]
"""
import argparse
import json
import struct
import sys

import pefile

LITERALS = [b'D:\\ok3dtemp\\', b'E:\\ok3dtemp\\', b'C:\\ok3dtemp\\']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--drive', default='C')
    ap.add_argument('--report', default=None)
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(data=bytes(data))
    base = pe.OPTIONAL_HEADER.ImageBase
    patched = []
    for lit in LITERALS[:2]:
        target = bytes([ord(a.drive)]) + lit[1:]
        start = 0
        while True:
            i = data.find(lit, start)
            if i < 0:
                break
            # only inside a section's raw data
            ok = False
            for s in pe.sections:
                if s.PointerToRawData <= i < s.PointerToRawData + s.SizeOfRawData:
                    ok = True
                    break
            if ok:
                data[i:i + len(lit)] = target
                patched.append({'literal': lit.decode('latin1'), 'offset': hex(i),
                                'va': hex(base + pe.get_rva_from_offset(i))})
            start = i + 1
    if not patched:
        print('no temp-dir literal found')
        return 1
    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))
    rep = {'exe': a.exe, 'drive': a.drive, 'patched': patched, 'checksum': hex(checksum)}
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    if a.report:
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
