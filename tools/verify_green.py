"""Verify a psdto3d 绿色版 package: header flags, manifest, licence patch bytes,
local settings file, and (optionally) a live start-up smoke test.

    python verify_green.py --dir "psdto3d2022绿色版" --exe psdto3d101.exe --launch

Exit code 0 means every check passed.
"""
import argparse
import json
import struct
import subprocess
import sys
import time
import os

import pefile

NO_KEY_ANSI = b"The system did not find any software key, please insert it."


def checks(path, launch=False, timeout=6.0):
    out = []
    with open(path, 'rb') as f:
        data = f.read()
    pe = pefile.PE(data=data)

    def add(name, ok, detail):
        out.append((name, bool(ok), detail))

    add('file present', True, '%d bytes, sha256 %s' %
        (len(data), __import__('hashlib').sha256(data).hexdigest()))
    add('machine is x86 (0x14c)', pe.FILE_HEADER.Machine == 0x14c,
        'machine=0x%x' % pe.FILE_HEADER.Machine)
    laa = bool(pe.FILE_HEADER.Characteristics & 0x0020)
    add('IMAGE_FILE_LARGE_ADDRESS_AWARE set (4 GiB on x64)', laa,
        'characteristics=0x%04x' % pe.FILE_HEADER.Characteristics)

    # licence gate bytes
    try:
        hits = [i for i in range(len(data)) if data.startswith(NO_KEY_ANSI, i)]
        str_va = pe.OPTIONAL_HEADER.ImageBase + pe.get_rva_from_offset(hits[0])
        ref = data.find(b'\xb8' + struct.pack('<I', str_va))
        jne = ref - 0x80 + data[ref - 0x80:ref].rfind(b'\x3d' + struct.pack('<I', 0xFFFFFBE3)) + 5
        gate1 = data[jne] == 0xEB
        te = data.find(b'\x31\xc0', ref, ref + 0x40) != -1
        add('licence gate 1 patched (jmp over the key abort)', gate1,
            'file 0x%x = 0x%02x' % (jne, data[jne]))
        add('licence gate 2 patched (forces licensed path)', te,
            'xor eax,eax present in the second gate')
    except Exception as exc:  # noqa: BLE001
        add('licence gate bytes', False, repr(exc))

    # manifest
    level = None
    r = getattr(pe, 'DIRECTORY_ENTRY_RESOURCE', None)
    for e in (r.entries if r else []):
        if e.struct.Id != 24:
            continue
        for d in e.directory.entries:
            for lang in d.directory.entries:
                info = lang.data.struct
                off = pe.get_offset_from_rva(info.OffsetToData)
                blob = data[off:off + info.Size].decode('utf-8', 'replace')
                if 'requestedExecutionLevel' in blob:
                    level = blob.split('level="')[1].split('"')[0]
    add('manifest requests asInvoker (no UAC prompt)', level == 'asInvoker', 'level=%s' % level)

    # settings file lives next to the exe
    inf = os.path.join(os.path.dirname(path), 'psdto3d104.inf')
    add('portable settings file beside the exe', os.path.isfile(inf), inf if os.path.isfile(inf) else 'missing')

    # dependency present
    tiff = os.path.join(os.path.dirname(path), 'cmyktiff2.dll')
    add('cmyktiff2.dll shipped', os.path.isfile(tiff), tiff if os.path.isfile(tiff) else 'missing')

    if launch:
        proc = subprocess.Popen([path], cwd=os.path.dirname(path))
        time.sleep(timeout)
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import win  # local helper shipped next to this script
            wins = win.windows(proc.pid)
            main = [w for w in wins if w[1] == 'TForm1' and w[3]]
            msg = [w for w in wins if w[1] == 'TMessageForm' and w[3]]
            add('live start-up: main window visible', bool(main), str(main[:1]))
            add('live start-up: no modal message box', not msg, str(msg[:1]))
        except Exception as exc:  # noqa: BLE001
            add('live start-up check', False, repr(exc))
        finally:
            proc.kill()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--launch', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    path = os.path.join(a.dir, a.exe)
    res = checks(path, a.launch)
    if a.json:
        print(json.dumps([{'check': n, 'ok': ok, 'detail': d} for n, ok, d in res], indent=2, ensure_ascii=False))
    else:
        for n, ok, d in res:
            print('%s  %-52s %s' % ('PASS' if ok else 'FAIL', n, d))
    sys.exit(0 if all(ok for _, ok, _ in res) else 1)


if __name__ == '__main__':
    main()
