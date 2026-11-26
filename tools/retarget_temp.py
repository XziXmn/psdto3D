"""Re-point the hard-coded work folder literal to another C: folder of the same length.

    python retarget_temp.py <exe> C:\\ok3dtmp\\
"""
import struct
import sys

import pefile

exe = sys.argv[1]
new = sys.argv[2].encode('ascii')
assert len(new) in (11, 12), 'literal must stay the same length as the original'

data = bytearray(open(exe, 'rb').read())
pe = pefile.PE(data=bytes(data))
total = 0
for old in (b'C:\\ok3dtemp\\', b'C:\\ok3dtemp'):
    if len(old) != len(new):
        continue
    n = data.count(old)
    data = bytearray(bytes(data).replace(old, new))
    total += n
    print('replaced %r -> %r  x%d' % (old, new, n))
pe2 = pefile.PE(data=bytes(data))
cs = pe2.generate_checksum()
struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, cs)
open(exe, 'wb').write(bytes(data))
print('total %d, checksum 0x%08x' % (total, cs))
