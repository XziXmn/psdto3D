"""Disassemble a window around an address in a PE image (Delphi code segment)."""
import sys

import capstone
import pefile
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

path, va_hex = sys.argv[1], sys.argv[2]
before = int(sys.argv[3]) if len(sys.argv) > 3 else 48
after = int(sys.argv[4]) if len(sys.argv) > 4 else 32
va = int(va_hex, 16)

pe = pefile.PE(path, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
base = pe.OPTIONAL_HEADER.ImageBase
data = open(path, 'rb').read()

iat = {}
for d in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
    dll = d.dll.decode() if isinstance(d.dll, bytes) else d.dll
    for f in d.imports:
        iat[base + f.address] = dll + '!' + (f.name.decode() if f.name else 'ord%d' % f.ordinal)

sec = None
for s in pe.sections:
    lo = base + s.VirtualAddress
    if lo <= va < lo + max(s.Misc_VirtualSize, s.SizeOfRawData):
        sec = s
if sec is None:
    raise SystemExit('address not in any section')
start = base + sec.VirtualAddress
blob = data[sec.PointerToRawData: sec.PointerToRawData + sec.SizeOfRawData]

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True
md.skipdata = True

target_off = va - start
window_start = max(0, target_off - 0x200)
window_end = min(len(blob), target_off + 0x200)
win_va = start + window_start
insns = list(md.disasm(blob[window_start:window_end], win_va))

# locate the instruction containing/nearest the address
idx = None
for i, ins in enumerate(insns):
    if ins.address <= va < ins.address + ins.size:
        idx = i
        break
if idx is None:
    idx = next((i for i, ins in enumerate(insns) if ins.address >= va), 0)
lo = max(0, idx - before)
hi = min(len(insns), idx + after)
print('image base 0x%x, section %s, fault window around 0x%x (instruction %s)' % (
    base, sec.Name.rstrip(b'\x00').decode(), va, insns[idx].address if insns else '?'))
for j in range(lo, hi):
    x = insns[j]
    note = ''
    try:
        o = x.operands
    except capstone.CsError:
        o = []
    if len(o) == 1 and o[0].type == X86_OP_MEM and o[0].mem.base == 0 and o[0].mem.index == 0:
        t = iat.get(o[0].mem.disp & 0xFFFFFFFF)
        if t:
            note = '   ; ' + t
    mark = '>>' if j == idx else '  '
    print('%s %08x  %-10s %s%s' % (mark, x.address, x.mnemonic, x.op_str, note))
