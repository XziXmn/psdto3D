"""Dump the state of the first short stream read that raises EReadError.

`0x415F1B` is the tail of a generic ReadBuffer helper:
    call [stream+0xc]        ; stream.Read(buf, count)
    cmp  ebx, eax            ; wanted vs got
    je   done
    ... create EReadError ... raise

So 0x415F04 is only reached when a read came up short. Hook it and record:
pushad image (edi esi ebp esp ebx edx ecx eax), plus the caller's return address.
Also dump a 16-byte prefix of the target buffer so we can see whether it is zeros.

Usage:
    python tools/probe_shortread.py <cmyktiff2.dll> -o out.dll
"""
import argparse
import struct
import sys

import pefile

SITE = 0x415F04          # 8b 0d a8 c3 48 00   mov ecx,[0x48C3A8]
REPLAY = bytes.fromhex('8b0da8c34800')
RESUME = SITE + len(REPLAY)
REC_RVA = 0x200          # offset inside our new section
PATH_RVA = 0x280
IAT_CREATEFILE = 0x4903D8
IAT_WRITEFILE = 0x4901F0
IAT_CLOSEHANDLE = 0x4903E4
WRITTEN_RVA = 0x8F000    # BSS scratch (write counter)
GENERIC_WRITE = 0x40000000
OUT_NAME = b'_read_fail.bin' + bytes(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args()

    d = bytearray(open(a.src, 'rb').read())
    pe = pefile.PE(a.src)
    ib = pe.OPTIONAL_HEADER.ImageBase

    def align(v, al):
        return (v + al - 1) // al * al

    def va2off(va):
        for s in pe.sections:
            base = ib + s.VirtualAddress
            if base <= va < base + s.SizeOfRawData:
                return s.PointerToRawData + (va - base)
        raise SystemExit('VA 0x%X not in file' % va)

    last = pe.sections[-1]
    sec_rva = align(last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData), 0x1000)
    sec_va = ib + sec_rva
    rec_va = sec_va + REC_RVA
    path_va = sec_va + PATH_RVA

    b = bytearray()
    b += bytes.fromhex('9c')                                   # pushfd
    b += bytes.fromhex('60')                                   # pushad
    b += bytes.fromhex('e8') + bytes(4)                        # call $+5
    b += bytes.fromhex('5b')                                   # pop ebx
    base = sec_va + 7                                          # pushfd(1)+pushad(1)+call(5) = 7, pop ebx 就在这里
    rel = lambda va: va - base

    # 复制 pushad 的 32 字节到 REC
    b += bytes.fromhex('8bc4')                                 # mov eax,esp
    b += bytes.fromhex('89c6')                                 # mov esi,eax
    b += bytes.fromhex('8d bb') + struct.pack('<i', rel(rec_va))   # lea edi,[ebx+rec]
    b += bytes.fromhex('b908000000')                            # mov ecx,8
    b += bytes.fromhex('f3a5')                                  # rep movsd
    # 调用者返回地址: [esp + 36 + 0x0C]
    b += bytes.fromhex('8b8424') + struct.pack('<I', 0x30)      # mov eax,[esp+0x30]
    b += bytes.fromhex('8983') + struct.pack('<i', rel(rec_va + 32))   # mov [ebx+rec+32],eax
    # 目标缓冲区前 16 字节: edi 在 pushad 镜像的 [esp+0], 即 REC+0
    b += bytes.fromhex('8b03')                                  # mov eax,[ebx]   (= saved edi? no) -> see note
    # 简化：跳过 buffer 前缀，避免误读未映射内存

    # CreateFile("_read_fail.bin")
    for imm in (0, 0x80, 2, 0, 0, GENERIC_WRITE):
        b += bytes.fromhex('68') + struct.pack('<I', imm)
    b += bytes.fromhex('8d83') + struct.pack('<i', rel(path_va))
    b += bytes.fromhex('50')
    b += bytes.fromhex('ff93') + struct.pack('<i', rel(IAT_CREATEFILE))
    b += bytes.fromhex('8bf0')                                  # mov esi,eax
    b += bytes.fromhex('83f8ff')                                # cmp eax,-1
    jz = len(b); b += bytes.fromhex('7400')
    b += bytes.fromhex('68') + struct.pack('<I', 0)
    b += bytes.fromhex('8d93') + struct.pack('<i', rel(WRITTEN_RVA))
    b += bytes.fromhex('52')
    b += bytes.fromhex('68') + struct.pack('<I', 36)            # push 36
    b += bytes.fromhex('8d83') + struct.pack('<i', rel(rec_va))
    b += bytes.fromhex('50')
    b += bytes.fromhex('56')
    b += bytes.fromhex('ff93') + struct.pack('<i', rel(IAT_WRITEFILE))
    b += bytes.fromhex('56')
    b += bytes.fromhex('ff93') + struct.pack('<i', rel(IAT_CLOSEHANDLE))
    skip = len(b)
    b[jz + 1] = (skip - (jz + 2)) & 0xFF
    b += bytes.fromhex('61')                                   # popad
    b += bytes.fromhex('9d')                                   # popfd
    b += REPLAY
    j = len(b)
    b += bytes.fromhex('e9') + struct.pack('<i', RESUME - (sec_va + j + 5))

    body = bytes(b)
    payload = bytearray(body)
    payload += bytes(PATH_RVA - len(payload)) if len(payload) < PATH_RVA else bytes(0)
    payload += OUT_NAME
    payload += bytes(align(len(payload), 0x200) - len(payload))

    raw = align(len(d), 0x200)
    d += bytes(raw - len(d))
    d += payload

    fh = pe.FILE_HEADER.get_file_offset()
    oh = pe.OPTIONAL_HEADER.get_file_offset()
    nsec = pe.FILE_HEADER.NumberOfSections
    sh = oh + pe.FILE_HEADER.SizeOfOptionalHeader + nsec * 40
    struct.pack_into('<8sIIIIIIHHI', d, sh, b'.shortrd', len(payload),
                     sec_rva, len(payload), raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, fh + 2, nsec + 1)
    struct.pack_into('<I', d, oh + 56, align(sec_rva + len(payload), 0x1000))

    off = va2off(SITE)
    if bytes(d[off:off + 6]) != REPLAY:
        raise SystemExit('site bytes unexpected: %s' % bytes(d[off:off + 6]).hex())
    d[off:off + 5] = bytes.fromhex('e9') + struct.pack('<i', sec_va - (SITE + 5))

    open(a.output, 'wb').write(bytes(d))
    print('cave %d 字节 @ VA 0x%X, hook 0x%X -> 0x%X' % (len(body), sec_va, SITE, sec_va))
    print('written %s (%d bytes)' % (a.output, len(d)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
