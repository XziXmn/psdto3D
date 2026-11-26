"""Convert PSDTO3D's "UG" TIFF variant (written by the 10.1 cmyktiff2.dll) into a standard TIFF.

The 10.1 build writes a structurally valid little-endian TIFF whose header and three tag
numbers are wrong:

    offset 0  55 47 A7 01 01 00 00 00   ->  49 49 2A 00 08 00 00 00
    entry 0   tag 0x19C9                ->  0x00FE   (NewSubfileType)
    entry 1   tag 0x0103                ->  0x0100   (ImageWidth)   <-- missing => width 0
    entry 6   tag 0x0112                ->  0x0111   (StripOffsets)

Everything else already matches a normal TIFF, so only these bytes are rewritten.

    python tools/ug2tiff.py --glob "C:\\ok3dtemp\\vwd*.gjs"
    python tools/ug2tiff.py --glob ... --watch 300     # wait for files, then convert
"""
import argparse
import glob
import os
import struct
import time

HEADER = b'II\x2a\x00\x08\x00\x00\x00'
FIXES = [(0, 0x00FE), (1, 0x0100), (6, 0x0111)]


def convert(path):
    with open(path, 'r+b') as fh:
        head = fh.read(8)
        if head[:2] != b'UG':
            return False
        fh.seek(0)
        fh.write(HEADER)
        n = struct.unpack('<H', (fh.read(2) or b'\x00\x00'))[0]
        for idx, tag in FIXES:
            if idx >= n:
                continue
            off = 10 + 12 * idx
            fh.seek(off)
            fh.write(struct.pack('<H', tag))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--glob', required=True)
    ap.add_argument('--watch', type=float, default=0)
    ap.add_argument('--min-count', type=int, default=0)
    a = ap.parse_args()

    if a.watch:
        t0 = time.time()
        last = None
        stable = 0
        while time.time() - t0 < a.watch:
            files = sorted(glob.glob(a.glob))
            if files and len(files) >= (a.min_count or len(files)):
                sizes = tuple(os.path.getsize(f) for f in files)
                if sizes == last:
                    stable += 1
                    if stable >= 3:
                        break
                else:
                    last = sizes
                    stable = 0
            time.sleep(1.0)

    files = sorted(glob.glob(a.glob))
    n = 0
    for f in files:
        if convert(f):
            n += 1
    print('files=%d converted=%d' % (len(files), n))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
