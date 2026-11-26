"""Build a probe DLL: dump the merge function's stack frame to a file.

Why: without the dongle the export aborts with a floating-point exception inside
mergtotiff. The numbers it needs come from the hardware key, so we dump the frame
on a licensed machine and diff it against an unlicensed one.

Design notes
------------
1. The DLL is relocated at load time (it actually lands at 0xD30000), so the cave
   must not contain absolute addresses: get the base with `call $+5 / pop ebx`
   and address IAT slots, strings and BSS scratch relative to ebx.
2. Output location: first the exe's own folder (computed at runtime with
   GetModuleFileNameA - the app chdir()s, so relative paths are useless), then a
   list of candidate cache dirs (C:/D:/E:\\ok3dtemp, C:\\Users\\Public). First one
   that opens wins.
3. The first hook sits on the PE entry point and writes a 4-byte marker, so
   `_p0.bin` appearing proves this DLL was actually loaded at all.
4. CODE's trailing bytes beyond VirtualSize are vendor data read by file offset,
   so they must not be touched; the cave goes in a new .psd3d section.

Usage:
    python tools/mkprobe.py <src.dll> -o probe.dll
"""
import argparse
import struct
import sys

import capstone
import pefile

HOOKS = [
    # (site, filename, dump source, dump length)
    (0x47F7B2, '_pa.bin', 'ebp', 0x2C0),
    (0x47F847, '_pb.bin', 'ebp', 0x2C0),
    (0x47F90F, '_pe.bin', 'ebp', 0x2C0),
    (0x47FBF1, '_pf.bin', 'ebp', 0x2C0),
]
IAT_GETMODULE = 0x4901D4
IAT_CREATEFILE = 0x4903D8
IAT_WRITEFILE = 0x4901F0
IAT_CLOSEHANDLE = 0x4903E4
WRITTEN_VA = 0x48F000
HANDLE_VA = 0x48F080
PATHBUF_VA = 0x48F100
DUMP_EBP = -0x2E0
BLOCK = 0x300
GENERIC_WRITE = 0x40000000

# 候选缓存目录（含结尾反斜杠），最后以空串结束
CANDIDATE_DIRS = [
    b'C:\\ok3dtemp\\',
    b'D:\\ok3dtemp\\',
    b'E:\\ok3dtemp\\',
    b'C:\\Users\\Public\\',
]


def lea(modrm, disp):
    return bytes([0x8D, modrm]) + struct.pack('<i', disp)


def call_ebx(disp):
    return bytes.fromhex('ff93') + struct.pack('<i', disp)


def push(imm):
    return bytes.fromhex('68') + struct.pack('<I', imm)


def va2off(pe, va):
    """VA -> file offset, scanning section headers (raw sizes, not virtual)."""
    for s in pe.sections:
        base = pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress
        if base <= va < base + s.SizeOfRawData:
            return s.PointerToRawData + (va - base)
    raise SystemExit('VA 0x%X not backed by file data' % va)


def ins_at(pe, data, va):
    """Disassemble from `va` until at least 5 bytes are covered."""
    off = va2off(pe, va)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    total = b''
    for ins in md.disasm(data[off:off + 40], va):
        total += ins.bytes
        if len(total) >= 5:
            return total, va + len(total)
    raise SystemExit('cannot split at 0x%X' % va)


def copy_esi_to_edi(b):
    """`while (*edi++ = *esi++);`"""
    start = len(b)
    b.extend(bytes.fromhex('8a06'))
    b.extend(bytes.fromhex('8807'))
    b.extend(bytes.fromhex('46'))
    b.extend(bytes.fromhex('47'))
    b.extend(bytes.fromhex('84c0'))
    b.extend(bytes.fromhex('75'))
    b.extend(bytes([(start - (len(b) + 1)) & 0xFF]))


def copy_edx_to_edi(b):
    """`while (*edi++ = *edx++);`"""
    start = len(b)
    b.extend(bytes.fromhex('8a02'))
    b.extend(bytes.fromhex('8807'))
    b.extend(bytes.fromhex('42'))
    b.extend(bytes.fromhex('47'))
    b.extend(bytes.fromhex('84c0'))
    b.extend(bytes.fromhex('75'))
    b.extend(bytes([(start - (len(b) + 1)) & 0xFF]))


def try_create(b, rel, pathbuf_va):
    """CreateFile(PATHBUF, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, NORMAL, 0)."""
    for imm in (0, 0x80, 2, 0, 0, GENERIC_WRITE):
        b.extend(push(imm))
    b.extend(lea(0x83, rel(pathbuf_va)))
    b.extend(bytes.fromhex('50'))
    b.extend(call_ebx(rel(IAT_CREATEFILE)))


def store_handle(b, rel, handle_va):
    """mov [ebx+handle_va], eax —— 不能拿 esi 存句柄，它可能是列表游标"""
    b.extend(bytes.fromhex('8983') + struct.pack('<i', rel(handle_va)))


def make_block(blk_va, suffix_va, list_va, resume_va, replay, src, length):
    b = bytearray()
    base_va = blk_va + 7            # `pop ebx` 的地址，ebx 相对寻址一律以它为基准
    rel = lambda va: va - base_va

    b.extend(bytes.fromhex('9c60'))                    # pushfd; pushad
    b.extend(bytes.fromhex('e8') + bytes(4))           # call $+5
    b.extend(bytes.fromhex('5b'))                      # pop ebx

    jumps = []

    # ---------- 尝试 1：exe 所在目录 ----------
    b.extend(push(0x100))
    b.extend(lea(0x83, rel(PATHBUF_VA)))
    b.extend(bytes.fromhex('50'))
    b.extend(bytes.fromhex('31c0'))                    # xor eax,eax  (hModule=NULL)
    b.extend(bytes.fromhex('50'))
    b.extend(call_ebx(rel(IAT_GETMODULE)))
    b.extend(bytes.fromhex('85c0'))                    # test eax,eax
    jz_exe = len(b)
    b.extend(bytes.fromhex('0f84') + bytes(4))
    b.extend(bytes.fromhex('8bc8'))                    # mov ecx,eax
    b.extend(lea(0x93, rel(PATHBUF_VA)))               # lea edx,[ebx+buf]
    scan = len(b)
    b.extend(bytes.fromhex('49'))                      # dec ecx
    b.extend(bytes.fromhex('803c0a5c'))                # cmp byte[edx+ecx],'\'
    b.extend(bytes.fromhex('75'))
    b.extend(bytes([(scan - (len(b) + 1)) & 0xFF]))
    b.extend(bytes.fromhex('41'))                      # inc ecx
    b.extend(bytes.fromhex('8d3c0a'))                  # lea edi,[edx+ecx]
    b.extend(lea(0xb3, rel(suffix_va)))                # lea esi,[ebx+suffix]
    copy_esi_to_edi(b)
    try_create(b, rel, PATHBUF_VA)
    store_handle(b, rel, HANDLE_VA)
    b.extend(bytes.fromhex('83f8ff'))                  # cmp eax,-1
    jumps.append(len(b))
    b.extend(bytes.fromhex('7500'))                    # jne got

    # ---------- 尝试 2..N：候选缓存目录 ----------
    b.extend(lea(0xb3, rel(list_va)))                  # lea esi,[ebx+list]
    nxt = len(b)
    b.extend(bytes.fromhex('8a06'))                    # mov al,[esi]
    b.extend(bytes.fromhex('84c0'))                    # test al,al
    jz_end = len(b)
    b.extend(bytes.fromhex('0f84') + bytes(4))         # je -> 全部失败
    b.extend(lea(0xbb, rel(PATHBUF_VA)))               # lea edi,[ebx+buf]
    copy_esi_to_edi(b)                                 # 复制目录前缀（含 NUL）
    b.extend(bytes.fromhex('4f'))                      # dec edi  -> 回到 NUL 处
    b.extend(lea(0x93, rel(suffix_va)))                # lea edx,[ebx+suffix]
    copy_edx_to_edi(b)                                 # 接上文件名
    try_create(b, rel, PATHBUF_VA)
    store_handle(b, rel, HANDLE_VA)
    b.extend(bytes.fromhex('83f8ff'))                  # cmp eax,-1
    jumps.append(len(b))
    b.extend(bytes.fromhex('7500'))                    # jne got
    b.extend(bytes.fromhex('e9'))
    b.extend(struct.pack('<i', nxt - (len(b) + 4)))    # jmp nxt

    to_skip = len(b)
    b.extend(bytes.fromhex('e9') + bytes(4))           # jmp skip
    got = len(b)
    b.extend(bytes.fromhex('8bb3') + struct.pack('<i', rel(HANDLE_VA)))   # mov esi,[ebx+HANDLE]
    for j in jumps:
        b[j + 1] = (got - (j + 2)) & 0xFF

    # ---------- WriteFile ----------
    b.extend(push(0))
    b.extend(lea(0x93, rel(WRITTEN_VA)))
    b.extend(bytes.fromhex('52'))
    b.extend(push(length))
    if src == 'ebp':
        b.extend(lea(0x85, DUMP_EBP))
    else:
        b.extend(lea(0x83, rel(suffix_va)))
    b.extend(bytes.fromhex('50'))
    b.extend(bytes.fromhex('56'))
    b.extend(call_ebx(rel(IAT_WRITEFILE)))
    b.extend(bytes.fromhex('56'))
    b.extend(call_ebx(rel(IAT_CLOSEHANDLE)))

    skip = len(b)
    struct.pack_into('<i', b, to_skip + 1, skip - (to_skip + 5))
    struct.pack_into('<i', b, jz_end + 2, skip - (jz_end + 6))
    struct.pack_into('<i', b, jz_exe + 2, skip - (jz_exe + 6))
    b.extend(bytes.fromhex('619d'))                    # popad; popfd
    b.extend(replay)
    jmp_at = len(b)
    b.extend(bytes.fromhex('e9'))
    b.extend(struct.pack('<i', resume_va - (blk_va + jmp_at + 5)))
    return bytes(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--prefix', default='',
                    help='dump 文件名前缀，用来区分是哪个 DLL 被加载')
    ap.add_argument('--site', default=None,
                    help='覆盖钩子地址（十六进制），用于其它 DLL')
    a = ap.parse_args()

    global HOOKS
    if a.prefix:
        HOOKS = [(s_, '_%s%s' % (a.prefix, n_[1:]), k_, l_) for (s_, n_, k_, l_) in HOOKS]
    if a.site:
        site = int(a.site, 16)
        HOOKS = [(site, '_za.bin', 'ebp', 0x2C0)]

    d = bytearray(open(a.src, 'rb').read())
    pe = pefile.PE(a.src)
    code = pe.sections[0]
    ib = pe.OPTIONAL_HEADER.ImageBase

    def align(v, al):
        return (v + al - 1) // al * al

    ep_va = ib + pe.OPTIONAL_HEADER.AddressOfEntryPoint
    last = pe.sections[-1]
    cave_rva = align(last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData), 0x1000)
    cave_va = ib + cave_rva

    suffix_base = cave_va + BLOCK * len(HOOKS)
    suffixes, off = {}, 0
    for _, name, _, _ in HOOKS:
        suffixes[name] = suffix_base + off
        off += len(name) + 1
    list_va = suffix_base + off

    payload = bytearray()
    sites = []
    for i, (site, name, src, length) in enumerate(HOOKS):
        site_va = ep_va if site == 'EP' else site
        replay, resume = ins_at(pe, d, site_va)
        blk_va = cave_va + i * BLOCK
        blk = make_block(blk_va, suffixes[name], list_va, resume, replay, src, length)
        if len(blk) > BLOCK:
            raise SystemExit('block %d too big: %d > %d' % (i, len(blk), BLOCK))
        payload.extend(blk)
        payload.extend(bytes(BLOCK - len(blk)))
        sites.append((site_va, blk_va, name))
    for _, name, _, _ in HOOKS:
        payload.extend(name.encode() + bytes(1))
    for cd in CANDIDATE_DIRS:
        payload.extend(cd + bytes(1))
    payload.extend(bytes(1))                      # 空串 = 列表结束
    payload.extend(bytes(align(len(payload), 0x200) - len(payload)))

    new_raw = align(len(d), 0x200)
    d.extend(bytes(new_raw - len(d)))
    d.extend(payload)

    fh = pe.FILE_HEADER.get_file_offset()
    oh = pe.OPTIONAL_HEADER.get_file_offset()
    nsec = pe.FILE_HEADER.NumberOfSections
    sh_off = oh + pe.FILE_HEADER.SizeOfOptionalHeader + nsec * 40
    struct.pack_into('<8sIIIIIIHHI', d, sh_off, b'.psd3d' + bytes(2), len(payload),
                     cave_rva, len(payload), new_raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', d, fh + 2, nsec + 1)
    struct.pack_into('<I', d, oh + 56, align(cave_rva + len(payload), 0x1000))

    for site_va, blk_va, name in sites:
        off = va2off(pe, site_va)
        d[off:off + 5] = bytes.fromhex('e9') + struct.pack('<i', blk_va - (site_va + 5))
        print('hook %-8s 0x%X -> 0x%X' % (name, site_va, blk_va))

    open(a.output, 'wb').write(bytes(d))
    print('.psd3d VA=0x%X len=%d sections %d->%d'
          % (cave_va, len(payload), nsec, nsec + 1))
    print('written %s (%d bytes)' % (a.output, len(d)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
