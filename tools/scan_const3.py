# -*- coding: utf-8 -*-
"""扫描 0x21/0x20/0x22 相关的比较与移动指令，定位 33 层上限。"""
import re
import sys

import pefile

PATS = {
    'cmp eax,0x21': '83f821',
    'cmp ecx,0x21': '83f921',
    'cmp edx,0x21': '83fa21',
    'cmp eax,0x20': '83f820',
    'mov eax,0x21': 'b821000000',
    'mov edx,0x21': 'ba21000000',
    'mov ecx,0x21': 'b921000000',
    'mov [..],0x21': 'c605',      # 占位，下面单独处理
}


def main(path):
    d = open(path, 'rb').read()
    pe = pefile.PE(path, fast_load=True)
    code = [s for s in pe.sections if s.Name.startswith(b'CODE')][0]
    lo, hi = code.PointerToRawData, code.PointerToRawData + code.SizeOfRawData
    base = pe.OPTIONAL_HEADER.ImageBase + code.VirtualAddress
    print('==', path.split('\\')[-1])
    for label, pat in PATS.items():
        if label.startswith('mov [..]'):
            continue
        b = bytes.fromhex(pat)
        hits = [m.start() for m in re.finditer(re.escape(b), d[lo:hi])]
        if hits and len(hits) <= 30:
            print('  %-14s %2d 处: %s' % (label, len(hits),
                                          ' '.join('%08X' % (base + h) for h in hits[:10])))
    pe.close()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        main(p)
