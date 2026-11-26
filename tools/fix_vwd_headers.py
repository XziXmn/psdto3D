"""Wait for the preview output, then rewrite the UG-variant TIFF headers of vwd*.gjs to standard TIFF.

    python tools/fix_vwd_headers.py --dir C:\\ok3dtemp --timeout 300
"""
import argparse
import glob
import os
import struct
import time

STD = b'II\x2a\x00\x08\x00\x00\x00'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=r'C:\ok3dtemp')
    ap.add_argument('--timeout', type=float, default=300)
    a = ap.parse_args()

    t0 = time.time()
    last = None
    stable = 0
    while time.time() - t0 < a.timeout:
        files = sorted(glob.glob(os.path.join(a.dir, 'vwd[0-9][0-9][0-9].gjs')))
        if len(files) >= 11:
            sizes = tuple(os.path.getsize(f) for f in files)
            if sizes == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                last = sizes
                stable = 0
        time.sleep(1.0)

    files = sorted(glob.glob(os.path.join(a.dir, 'vwd[0-9][0-9][0-9].gjs')))
    fixed = 0
    for f in files:
        with open(f, 'r+b') as fh:
            head = fh.read(8)
            if head[:2] == b'UG':
                fh.seek(0)
                fh.write(STD)
                fixed += 1
    print('files=%d fixed=%d' % (len(files), fixed))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
