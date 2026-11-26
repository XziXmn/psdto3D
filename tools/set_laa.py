# -*- coding: utf-8 -*-
"""Set IMAGE_FILE_LARGE_ADDRESS_AWARE (0x20) on the exe and fix the PE checksum."""
import io
import os
import struct
import sys


def patch(path):
    data = bytearray(io.open(path, 'rb').read())
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    coff = e_lfanew + 4
    ch = struct.unpack_from('<H', data, coff + 18)[0]
    if ch & 0x20:
        print('%s: 已是 LARGE_ADDRESS_AWARE (0x%04X)' % (os.path.basename(path), ch))
    else:
        struct.pack_into('<H', data, coff + 18, ch | 0x20)
        print('%s: Characteristics 0x%04X -> 0x%04X' % (os.path.basename(path), ch, ch | 0x20))

    # 重新计算 PE 校验和
    opt = coff + 20
    magic = struct.unpack_from('<H', data, opt)[0]
    csum_off = opt + 64
    struct.pack_into('<I', data, csum_off, 0)
    total = 0
    for i in range(0, len(data) - 1, 2):
        total += struct.unpack_from('<H', data, i)[0]
        total = (total & 0xFFFF) + (total >> 16)
    if len(data) % 2:
        total += data[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    checksum = (total + len(data)) & 0xFFFFFFFF
    struct.pack_into('<I', data, csum_off, checksum)
    io.open(path, 'wb').write(bytes(data))
    print('   magic=0x%04X checksum=0x%08X' % (magic, checksum))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        patch(p)
