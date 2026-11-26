"""Restore the user's original .gxwj bytes after an accidental in-place rewrite.

The original file stored the PSD path with GBK bytes (E:\\<D3><CE>\\1114\\1114 -1.psd)
and had a CR before the CRLF on every coordinate line (643 of them).
"""
import re
import sys

path = sys.argv[1]
want_size = int(sys.argv[2]) if len(sys.argv) > 2 else None
data = open(path, 'rb').read()
lines = re.split(rb'\r\n', data)
lines[0] = b'E:\\' + bytes([0xD3, 0xCE]) + b'\\1114\\1114 -1.psd'
out = []
for ln in lines:
    if ln.endswith(b' ') and out:
        ln = ln + b'\r'
    out.append(ln)
restored = b'\r\n'.join(out)
open(path, 'wb').write(restored)
print('size before %d, after %d, crcrlf %d' % (len(data), len(restored), restored.count(b'\r\r\n')))
if want_size is not None:
    print('expected %d -> %s' % (want_size, 'OK' if len(restored) == want_size else 'MISMATCH'))
print('line1 =', restored.split(b'\r\n')[0])
