"""Search a Delphi PE for the crash site of the 3D generator.

The site reads:  mov eax,[<layerArrayGlobal>] ; mov eax,[eax+ebx*4] ; mov eax,[eax+edi*4]
The global address differs between builds, so the SIB pattern is used as the anchor.
"""
import sys

import capstone
import pefile
from capstone.x86 import X86_OP_MEM

path = sys.argv[1]
pe = pefile.PE(path, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(path, 'rb').read()
sec = [s for s in pe.sections if s.Name.rstrip(b'\x00') in (b'CODE', b'.text')][0]
start = base + sec.VirtualAddress
off0 = sec.PointerToRawData
blob = data[off0:off0 + sec.SizeOfRawData]

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True

anchors = []
i = blob.find(b'\x8b\x04\x98')
while i != -1:
    anchors.append(start + i)
    i = blob.find(b'\x8b\x04\x98', i + 1)

print('%s: %d anchors' % (path, len(anchors)))
for va in anchors:
    off = va - start
    insns = list(md.disasm(blob[off - 6:off + 12], va - 6))[:4]
    text = ' | '.join('%s %s' % (x.mnemonic, x.op_str) for x in insns)
    if '[eax + edi*4]' in text and 'ebx*4' in text:
        print('  MATCH va=0x%x' % va)
        for x in list(md.disasm(blob[off - 6:off + 14], va - 6))[:5]:
            print('      %08x %-8s %s' % (x.address, x.mnemonic, x.op_str))
