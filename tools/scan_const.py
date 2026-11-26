# -*- coding: utf-8 -*-
"""在 CODE 段里按字节找与 0x28/0x29/0x40 的比较指令，定位层数上限的常量。"""
import re
import sys

import pefile

PATS = {
    'cmp eax,0x28': '83f828',
    'cmp ecx,0x28': '83f928',
    'cmp edx,0x28': '83fa28',
    'cmp eax,0x29': '83f829',
    'cmp eax,0x40': '83f840',
    'cmp eax,0x3c': '83f83c',
    'cmp eax,0x64': '83f864',
}


def main(path):
    d = open(path, 'rb').read()
    pe = pefile.PE(path, fast_load=True)
    code = [s for s in pe.sections if s.Name.startswith(b'CODE')][0]
    lo = code.PointerToRawData
    hi = lo + code.SizeOfRawData
    base = pe.OPTIONAL_HEADER.ImageBase + code.VirtualAddress
    print('==', path.split('\\')[-1], 'CODE', hex(lo), '-', hex(hi))
    for label, pat in PATS.items():
        b = bytes.fromhex(pat)
        hits = [m.start() for m in re.finditer(re.escape(b), d[lo:hi])]
        if hits:
            vas = ' '.join('%08X' % (base + h) for h in hits[:8])
            print('  %-14s %2d 处: %s' % (label, len(hits), vas))
    pe.close()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        main(p)
