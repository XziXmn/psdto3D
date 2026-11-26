"""PE 定点反汇编/搜索助手（按 VA 精确映射，不用 pefile 的 mapped image）。"""
import sys, pefile, capstone


class Mod:
    def __init__(self, path):
        self.path = path
        self.pe = pefile.PE(path)
        self.ib = self.pe.OPTIONAL_HEADER.ImageBase
        self.raw = open(path, 'rb').read()
        self.secs = []
        for s in self.pe.sections:
            self.secs.append((s.Name.rstrip(b'\0').decode('latin1'),
                              s.VirtualAddress, s.PointerToRawData,
                              s.Misc_VirtualSize, s.SizeOfRawData))

    def va2off(self, va):
        r = va - self.ib
        for n, vaddr, raw, vsz, rsz in self.secs:
            if vaddr <= r < vaddr + max(vsz, rsz):
                d = r - vaddr
                if d < rsz:
                    return raw + d
        return None

    def off2va(self, off):
        for n, vaddr, raw, vsz, rsz in self.secs:
            if raw <= off < raw + rsz:
                return self.ib + vaddr + (off - raw)
        return None

    def code(self):
        for n, vaddr, raw, vsz, rsz in self.secs:
            if n == 'CODE':
                return self.ib + vaddr, self.raw[raw:raw + vsz]
        return None, None


def dis(m, start_va, count=60):
    off = m.va2off(start_va)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    n = 0
    for ins in md.disasm(m.raw[off:off + count * 8], start_va):
        print('%08X  %-20s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic + ' ' + ins.op_str))
        n += 1
        if n >= count:
            break


def refs_to(m, va, span=128):
    """找 code 中指向 va(-delta) 的绝对立即数。"""
    base, code = m.code()
    hits = []
    for delta in range(0, span):
        pat = ((va - delta) & 0xFFFFFFFF).to_bytes(4, 'little')
        s = 0
        while True:
            j = code.find(pat, s)
            if j < 0:
                break
            hits.append((base + j, delta))
            s = j + 1
    return hits


def scan_imm(m, targets):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    base, code = m.code()
    out = []
    for ins in md.disasm(code, base):
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_IMM:
                v = op.imm & 0xFFFFFFFF
                if v in targets:
                    out.append((ins.address, ins.bytes.hex(),
                                ins.mnemonic + ' ' + ins.op_str, targets[v]))
    return out


if __name__ == '__main__':
    cmd = sys.argv[1]
    m = Mod(sys.argv[2])
    if cmd == 'dis':
        dis(m, int(sys.argv[3], 16), int(sys.argv[4]) if len(sys.argv) > 4 else 60)
    elif cmd == 'str':
        needle = sys.argv[3].encode()
        i = m.raw.find(needle)
        print('file off 0x%X -> VA 0x%X' % (i, m.off2va(i)))
        for r, d in refs_to(m, m.off2va(i) + 1):
            print('  ref 0x%X (target-1)' % r)
        for r, d in refs_to(m, m.off2va(i)):
            print('  ref 0x%X (exact)' % r)
