"""按 VA 反汇编 PE（capstone）。用法: python tools/da.py <pe> <va_hex> [len]"""
import struct
import sys

import capstone


def load(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, e + 6)[0]
    soh = struct.unpack_from('<H', d, e + 20)[0]
    ib = struct.unpack_from('<I', d, e + 24 + 28)[0]
    secs = []
    s = e + 24 + soh
    for i in range(n):
        b = s + 40 * i
        nm = d[b:b + 8].rstrip(b'\0').decode('latin1')
        vs, va, rs, ro = struct.unpack_from('<IIII', d, b + 8)
        secs.append((nm, va, vs, ro, rs))
    return d, ib, secs


def va2off(secs, va):
    for nm, va0, vs, ro, rs in secs:
        if va0 <= va < va0 + max(vs, rs):
            o = ro + (va - va0)
            return o
    return None


def main():
    path = sys.argv[1]
    va = int(sys.argv[2], 16)
    ln = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x200
    d, ib, secs = load(path)
    o = va2off(secs, va)
    if o is None:
        raise SystemExit('VA 不在任何节里')
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False
    end = va + ln
    for ins in md.disasm(d[o:o + ln], va):
        print('%08X  %-24s %s %s' % (ins.address,
                                     ins.bytes.hex(' '),
                                     ins.mnemonic, ins.op_str))
        if ins.address >= end - 1:
            break


if __name__ == '__main__':
    main()
