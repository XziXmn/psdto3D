"""Rename a PSD layer in place (same-length or shorter) without touching the layout.

PSDTO3D refuses a PSD whose layer is named "Background"; renaming that layer to a
short name makes the file acceptable while keeping every other byte identical.

    python psdrename.py in.psd out.psd --index 0 --name bg
"""
import argparse
import struct
import sys


def locate_names(data):
    """Return [(name_offset, name_len)] for each layer record, in file offsets."""
    out = []
    p = 26
    for _ in range(2):
        ln = struct.unpack('>I', data[p:p + 4])[0]
        p += 4 + ln
    layer_mask_len = struct.unpack('>I', data[p:p + 4])[0]
    p += 4
    layer_info_len = struct.unpack('>I', data[p:p + 4])[0]
    p += 4
    if layer_info_len == 0:
        return out
    count = struct.unpack('>h', data[p:p + 2])[0]
    p += 2
    for _ in range(abs(count)):
        p += 16
        nch = struct.unpack('>H', data[p:p + 2])[0]
        p += 2 + nch * 6 + 8 + 4          # channels, blend sig/key, opacity+clipping+flags+filler
        extra_len = struct.unpack('>I', data[p:p + 4])[0]
        p += 4
        extra_end = p + extra_len
        mask_len = struct.unpack('>I', data[p:p + 4])[0]
        p += 4 + mask_len
        br_len = struct.unpack('>I', data[p:p + 4])[0]
        p += 4 + br_len
        name_len = data[p]
        out.append((p, name_len))
        p = extra_end
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--index', type=int, nargs='+', required=True)
    ap.add_argument('--name', required=True)
    a = ap.parse_args()
    data = bytearray(open(a.src, 'rb').read())
    names = locate_names(data)
    new = a.name.encode('gbk')
    for idx in a.index:
        off, ln = names[idx]
        if len(new) > ln:
            raise SystemExit('name %r longer than the existing %d bytes' % (a.name, ln))
        data[off] = len(new)
        data[off + 1:off + 1 + ln] = new + b'\x00' * (ln - len(new))
        print('layer %d renamed (%d -> %d bytes)' % (idx, ln, len(new)))
    open(a.dst, 'wb').write(bytes(data))
    print('written', a.dst)
    return 0


if __name__ == '__main__':
    sys.exit(main())
