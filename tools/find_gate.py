"""Reproduce the static evidence for the psdto3d start-up licence gate.

Disassembles the CODE segment with capstone (skipdata on, Delphi keeps string
constants inside CODE), then prints the surroundings of the four licence
messages so the gate structure can be re-read without a disassembler GUI.

    python find_gate.py "Psdto3d\\psdto3d101.exe"
"""
import sys

import capstone
import pefile
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

LITERALS = {
    b'The system did not find any software key, please insert it.': 'NO_KEY',
    b'Register file error, because the key did not write the license number': 'REG_FILE_ERR',
    b'\\keyreg101.exe': 'KEYREG_EXE',
    b'The system can not find the specified software key, will cause an error': 'SPEC_KEY',
}


def main(path):
    pe = pefile.PE(path, fast_load=True)
    pe.parse_data_directories(directories=[
        pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    base = pe.OPTIONAL_HEADER.ImageBase
    raw = open(path, 'rb').read()

    iat = {}
    for d in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
        dll = d.dll.decode() if isinstance(d.dll, bytes) else d.dll
        for f in d.imports:
            iat[base + f.address] = dll + '!' + (f.name.decode() if f.name else 'ord%d' % f.ordinal)

    code = None
    for s in pe.sections:
        name = s.Name.rstrip(b'\x00').decode(errors='replace')
        if name in ('CODE', '.text'):
            code = (base + s.VirtualAddress, s.PointerToRawData, s.SizeOfRawData)
    if code is None:
        raise SystemExit('no code section found')
    va0, off0, size = code
    blob = raw[off0:off0 + size]

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    insns = list(md.disasm(blob, va0))
    print('%s: %d decoded instructions from 0x%x' % (path, len(insns), va0))

    targets = {}
    for needle, label in LITERALS.items():
        pos = raw.find(needle)
        if pos == -1:
            continue
        targets[base + pe.get_rva_from_offset(pos)] = label
    print('literals: %s' % {hex(k): v for k, v in targets.items()})

    for i, ins in enumerate(insns):
        try:
            ops = ins.operands
        except capstone.CsError:
            continue
        hit = None
        for op in ops:
            if op.type == X86_OP_IMM and (op.imm & 0xFFFFFFFF) in targets:
                hit = targets[op.imm & 0xFFFFFFFF]
            elif op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0 \
                    and (op.mem.disp & 0xFFFFFFFF) in targets:
                hit = targets[op.mem.disp & 0xFFFFFFFF]
        if not hit:
            continue
        print('\n=== %s referenced at 0x%x' % (hit, ins.address))
        for j in range(max(0, i - 20), min(len(insns), i + 8)):
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
            print('%s %08x  %-9s %s%s' % ('>>' if j == i else '  ', x.address, x.mnemonic, x.op_str, note))


if __name__ == '__main__':
    main(sys.argv[1])
