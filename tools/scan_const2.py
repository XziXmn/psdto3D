# -*- coding: utf-8 -*-
"""扫描更多可能的层数上限常量（0x28/0x2a/0x2b/0x2c/0x32/0x3c/0x40 及其 mov 形式）。"""
import re
import sys

import pefile

PATS = {
    'cmp eax,0x2a': '83f82a',
    'cmp eax,0x2b': '83f82b',
    'cmp eax,0x2c': '83f82c',
    'cmp eax,0x32': '83f832',
    'cmp ecx,0x2a': '83f92a',
    'mov eax,0x28': 'b828000000',
    'mov edx,0x28': 'ba28000000',
    'mov ecx,0x28': 'b928000000',
    'push 0x28': '6a28',
    'push 0x2a': '6a2a',
}


def main(path):
    d = open(path, 'rb').read()
    pe = pefile.PE(path, fast_load=True)
    code = [s for s in pe.sections if s.Name.startswith(b'CODE')][0]
    lo, hi = code.PointerToRawData, code.PointerToRawData + code.SizeOfRawData
    base = pe.OPTIONAL_HEADER.ImageBase + code.VirtualAddress
    print('==', path.split('\\')[-1])
    for label, pat in PATS.items():
        b = bytes.fromhex(pat)
        hits = [m.start() for m in re.finditer(re.escape(b), d[lo:hi])]
        if hits and len(hits) < 40:
            vas = ' '.join('%08X' % (base + h) for h in hits[:8])
            print('  %-14s %2d 处: %s' % (label, len(hits), vas))
    pe.close()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        main(p)
