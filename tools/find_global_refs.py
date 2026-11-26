"""Find every instruction that reads or writes a global address (Delphi data segment)."""
import sys

import capstone
import pefile
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

path = sys.argv[1]
targets = {int(a, 16) for a in sys.argv[2:]}

pe = pefile.PE(path, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(path, 'rb').read()
sec = [s for s in pe.sections if s.Name.rstrip(b'\x00').decode(errors='replace') in ('CODE', '.text')][0]
start = base + sec.VirtualAddress
blob = data[sec.PointerToRawData: sec.PointerToRawData + sec.SizeOfRawData]

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True
md.skipdata = True

hits = {t: [] for t in targets}
for ins in md.disasm(blob, start):
    try:
        ops = ins.operands
    except capstone.CsError:
        continue
    for op in ops:
        addr = None
        if op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
            addr = op.mem.disp & 0xFFFFFFFF
        elif op.type == X86_OP_IMM:
            addr = op.imm & 0xFFFFFFFF
        if addr in hits:
            hits[addr].append((ins.address, ins.mnemonic, ins.op_str))

for t in sorted(hits):
    print('=== 0x%08x : %d references' % (t, len(hits[t])))
    for a, m, o in hits[t][:40]:
        print('   %08x  %-8s %s' % (a, m, o))
