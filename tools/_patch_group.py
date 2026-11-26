"""99100 import never writes the group column. Fill it from the curve-layer mask."""
import os
import shutil
import struct
import pefile
import capstone

EXE = r"_work\2022\psdto3d101.exe"
SITE = 0x511AFA
BACK = 0x51215D
MASK = 0x19FFFFFF  # curve layers 0..24, 27, 28

pe = pefile.PE(EXE)
data = bytearray(pe.__data__)
ib = pe.OPTIONAL_HEADER.ImageBase
file_align = pe.OPTIONAL_HEADER.FileAlignment
sect_align = pe.OPTIONAL_HEADER.SectionAlignment
last = pe.sections[-1]
raw_off = (last.PointerToRawData + last.SizeOfRawData + file_align - 1) & ~(file_align - 1)
va = (last.VirtualAddress + last.Misc_VirtualSize + sect_align - 1) & ~(sect_align - 1)
raw_off = (last.PointerToRawData + last.SizeOfRawData + file_align - 1) & ~(file_align - 1)
cave = ib + va

code = bytearray()
def add(b):
    code.extend(b)

add(b"\x53\x56")                              # push ebx; push esi
add(b"\x31\xdb")                              # xor ebx, ebx
add(b"\xbe" + struct.pack("<I", MASK))        # mov esi, MASK
mark = len(code)
add(b"\x0f\xa3\xde")                          # bt esi, ebx
jc = len(code)
add(b"\x73\x00")                              # jnc clear
add(b"\x68\x64\x27\x51\x00")                  # push "+"
jmpw = len(code)
add(b"\xeb\x00")                              # jmp write
clear = len(code)
code[jc + 1] = (clear - (jc + 2)) & 0xFF
add(b"\x6a\x00")                              # push 0
write = len(code)
code[jmpw + 1] = (write - (jmpw + 2)) & 0xFF
add(b"\x0f\xb7\x0d\x5c\x31\x52\x00")          # movzx ecx, word [0x52315C]
add(b"\x29\xd9")                              # sub ecx, ebx
add(b"\x8b\x45\xfc")                          # mov eax, [ebp-4]
add(b"\x8b\x80\x0c\x03\x00\x00")              # mov eax, [eax+0x30C]
add(b"\xba\x01\x00\x00\x00")                  # mov edx, 1
rel_call = 0x48D628 - (cave + len(code) + 5)
add(b"\xe8" + struct.pack("<i", rel_call))
# +0x2C = 0xFF if the bit was set, else 0. Re-test.
add(b"\x0f\xa3\xde")                          # bt esi, ebx
setb = len(code)
add(b"\x73\x00")                              # jnc zero
add(b"\xb2\xff")                              # mov dl, 0xFF
zjmp = len(code)
add(b"\xeb\x00")
zero = len(code)
code[setb + 1] = (zero - (setb + 2)) & 0xFF
add(b"\x30\xd2")                              # xor dl, dl
store = len(code)
code[zjmp + 1] = (store - (zjmp + 2)) & 0xFF
add(b"\x89\xd8")                              # mov eax, ebx
add(b"\xc1\xe0\x03")                          # shl eax, 3
add(b"\x29\xd8")                              # sub eax, ebx
add(b"\x8b\x0d\xb4\x30\x52\x00")              # mov ecx, [0x5230B4]
add(b"\x88\x54\xc1\x2c")                      # mov [ecx+eax*8+0x2C], dl
add(b"\x43")                                  # inc ebx
add(b"\x3b\x5d\xac")                          # cmp ebx, [ebp-0x54]
jl = len(code)
disp = mark - (jl + 2)
add(b"\x7c" + struct.pack("<b", disp))
add(b"\x5e\x5b")                              # pop esi; pop ebx
rel_back = BACK - (cave + len(code) + 5)
add(b"\xe9" + struct.pack("<i", rel_back))

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
print("--- cave %X ---" % cave)
for ins in md.disasm(bytes(code), cave):
    print("%08X  %s %s" % (ins.address, ins.mnemonic, ins.op_str))

raw_size = (len(code) + file_align - 1) & ~(file_align - 1)
blob = bytes(code) + b"\x00" * (raw_size - len(code))
if len(data) < raw_off if False else raw_off:
    pass
if len(data) < raw_off:
    data += b"\x00" * (raw_off - len(data))
data = data[:raw_off] + blob

# section header sits immediately after the existing 8 headers
hdr = pe.DOS_HEADER.e_lfanew + 4 + 20 + pe.FILE_HEADER.SizeOfOptionalHeader
slot = hdr + 40 * pe.FILE_HEADER.NumberOfSections
name = b".cave\x00\x00\x00"
header = name
header += struct.pack("<I", len(code))
header += struct.pack("<I", va)
header += struct.pack("<I", raw_size)
header += struct.pack("<I", raw_off)
header += struct.pack("<I", 0)   # relocs
header += struct.pack("<I", 0)   # linenumbers
header += struct.pack("<HH", 0, 0)
header += struct.pack("<I", 0x60000020)
assert len(header) == 40
data[slot:slot + 40] = header

# NumberOfSections
ns_off = pe.DOS_HEADER.e_lfanew + 6
struct.pack_into("<H", data, ns_off, pe.FILE_HEADER.NumberOfSections + 1)
# SizeOfImage
# optional header starts at e_lfanew+24
opt = pe.DOS_HEADER.e_lfanew + 24
# SizeOfImage offset within optional: 56 for PE32
struct.pack_into("<I", data, opt + 56, (va + sect_align) & ~(sect_align - 1))

# redirect site
site_off = pe.get_offset_from_rva(SITE - ib)
rel = (cave - (SITE + 5)) & 0xFFFFFFFF
data[site_off:site_off + 5] = b"\xe9" + struct.pack("<I", rel)

if hasattr(pe, "close"):
    pe.close()
out = EXE + ".patched"
open(out, "wb").write(data)
pe2 = pefile.PE(out)
pe2.OPTIONAL_HEADER.CheckSum = pe2.generate_checksum()
pe2.write(out)
if hasattr(pe2, "close"):
    pe2.close()
os.replace(out, EXE)
print("section ok, replaced", EXE)
