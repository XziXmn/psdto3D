"""给 cmyktiff2.dll 装探针：把合并函数里的栈帧 dump 到文件。

无狗 / 有狗各跑一次，两份 blob 做 diff，不同的字节就是硬件狗提供的数值。

三个设计要点
------------
1. DLL 会重定位（实载 0xD30000），穴里不能有绝对地址：`call $+5 / pop ebx`
   取基址，IAT / 字符串 / BSS 缓冲全部相对 ebx 寻址。
2. 落盘位置不依赖工作目录也不依赖 ACL：每个 dump 依次尝试
   `<exe 目录>\_pX.bin` → `C:\Users\Public\_pX.bin` → `C:\_pX.bin`。
   exe 目录是运行时用 GetModuleFileNameA 算出来的（软件自己会 chdir）。
3. 第一个钩子挂在 **PE 入口点**，只写 4 字节标记 —— 只要 DLL 被加载它就出现，
   用来区分"DLL 没被加载"和"钩子没跑到"。
"""
import argparse
import struct
import sys

import capstone
import pefile

# site_va 或 'EP'；filename；dump 源（'ebp' + 偏移，或 'abs'）；长度
HOOKS = [
    ('EP',        b'_p0.bin', 'abs', 0,      4),
    (0x47F7B2,    b'_pa.bin', 'ebp', -0x2E0, 0x2C0),
    (0x47F847,    b'_pb.bin', 'ebp', -0x2E0, 0x2C0),
    (0x47F8E9,    b'_pc.bin', 'ebp', -0x2E0, 0x2C0),
    (0x47F90F,    b'_pe.bin', 'ebp', -0x2E0, 0x2C0),
    (0x47FBF1,    b'_pf.bin', 'ebp', -0x2E0, 0x2C0),
]
IAT_GETMODULE = 0x4901D4
IAT_CREATEFILE = 0x4903D8
IAT_WRITEFILE = 0x4901F0
IAT_CLOSEHANDLE = 0x4903E4
WRITTEN_VA = 0x48F000
PATHBUF_VA = 0x48F100
BLOCK = 0x200
GEN = 0x40000000
PUBLIC_FMT = b'C:\Users\Public\'
ROOT_FMT = b'C:\'


def lea(modrm, disp):
    return bytes([0x8D, modrm]) + struct.pack('<i', disp)


def call_ebx(disp):
    return bytes.fromhex('ff93') + struct.pack('<i', disp)


def split_at_site(pe, data, site_va):
    """从 site 开始反汇编，凑够 >=5 字节的完整指令；返回 (replay, resume_va)。"""
    off = None
    for s in pe.sections:
        base = pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress
        if base <= site_va < base + max(s.Misc_VirtualSize, s.SizeOfRawData):
            off = s.PointerToRawData + (site_va - base)
            break
    if off is None:
        raise SystemExit('site 0x%X not mapped' % site_va)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    total = b''
    for ins in md.disasm(data[off:off + 32], site_va):
        total += ins.bytes
        if len(total) >= 5:
            return total, site_va + len(total)
    raise SystemExit('cannot split at 0x%X' % site_va)


def make_block(base_va, suffix_va, resume_va, replay, src_kind, src_off, length):
    b = bytearray()
    rel = lambda va: va - base_va
    b.extend(bytes.fromhex('9c60'))                  # pushfd; pushad
    b.extend(bytes.fromhex('e8') + bytes(4))         # call $+5
    b.extend(bytes.fromhex('5b'))                    # pop ebx

    # ---- 先把 exe 目录前缀写进 PATHBUF ----
    b.extend(bytes.fromhex('68') + struct.pack('<I', 0x100))
    b.extend(lea(0x83, rel(PATHBUF_VA)))
    b.extend(bytes.fromhex('50'))
    b.extend(bytes.fromhex('31c0'))
    b.extend(bytes.fromhex('50'))
    b.extend(call_ebx(rel(IAT_GETMODULE)))
    b.extend(bytes.fromhex('85c0'))
    jz_all = len(b)
    b.extend(bytes.fromhex('7400'))
    b.extend(bytes.fromhex('8bc8'))                  # mov ecx,eax
    b.extend(lea(0x93, rel(PATHBUF_VA)))             # lea edx,[ebx+PATHBUF]
    scan = len(b)
    b.extend(bytes.fromhex('49'))                    # dec ecx
    b.extend(bytes.fromhex('803c0a5c'))              # cmp byte [edx+ecx],'\'
    b.extend(bytes.fromhex('75'))
    b.extend(bytes([(scan - (len(b) + 1)) & 0xFF]))
    b.extend(bytes.fromhex('41'))                    # inc ecx
    b.extend(bytes.fromhex('8d3c0a'))                # lea edi,[edx+ecx]

    # 三个候选落盘点：<exedir>suffix / C:\Users\Public\suffix / C:\suffix
    cands = [('prefix', None), ('fixed', PUBLIC_FMT), ('fixed', ROOT_FMT)]
    jumps = []
    for kind, prefix in cands:
        if kind == 'prefix':
            b.extend(lea(0xb3, rel(suffix_va)))      # lea esi,[ebx+suffix]
            copy = len(b)
            b.extend(bytes.fromhex('8a06'))
            b.extend(bytes.fromhex('8807'))
            b.extend(bytes.fromhex('46'))
            b.extend(bytes.fromhex('47'))
            b.extend(bytes.fromhex('84c0'))
            b.extend(bytes.fromhex('75'))
            b.extend(bytes([(copy - (len(b) + 1)) & 0xFF]))
        else:
            # 用固定前缀覆盖 PATHBUF，再接 suffix
            b.extend(lea(0xbb, rel(fixed_va[prefix])))   # lea edi,[ebx+fixed]
            b.extend(lea(0x83, rel(PATHBUF_VA)))         # lea eax,[ebx+PATHBUF]
            mov = len(b)
            b.extend(bytes.fromhex('8a17'))              # mov dl,[edi]
            b.extend(bytes.fromhex('8810'))              # mov [eax],dl
            b.extend(bytes.fromhex('47'))
            b.extend(bytes.fromhex('40'))
            b.extend(bytes.fromhex('84d2'))
            b.extend(bytes.fromhex('75'))
            b.extend(bytes([(mov - (len(b) + 1)) & 0xFF]))
            # PATHBUF 现在以 '\' 结尾，再接 suffix
            b.extend(bytes.fromhex('8d78ff'))            # lea edi,[eax-1]
            b.extend(lea(0xb3, rel(suffix_va)))
            copy = len(b)
            b.extend(bytes.fromhex('8a06'))
            b.extend(bytes.fromhex('8807'))
            b.extend(bytes.fromhex('46'))
            b.extend(bytes.fromhex('47'))
            b.extend(bytes.fromhex('84c0'))
            b.extend(bytes.fromhex('75'))
            b.extend(bytes([(copy - (len(b) + 1)) & 0xFF]))
        # CreateFile(PATHBUF)
        for imm in (0, 0x80, 2, 0, 0, GEN):
            b.extend(bytes.fromhex('68') + struct.pack('<I', imm))
        b.extend(lea(0x83, rel(PATHBUF_VA)))
        b.extend(bytes.fromhex('50'))
        b.extend(call_ebx(rel(IAT_CREATEFILE)))
        b.extend(bytes.fromhex('8bf0'))                  # mov esi,eax
        b.extend(bytes.fromhex('83f8ff'))                # cmp eax,-1
        jumps.append(len(b))
        b.extend(bytes.fromhex('7500'))                  # jne -> got

    # 全部失败：跳过
    to_skip = len(b)
    b.extend(bytes.fromhex('e9') + bytes(4))

    got = len(b)
    for j in jumps:
        b[j + 1] = (got - (j + 2)) & 0xFF
    # WriteFile(esi, src, len, &written, 0)
    b.extend(bytes.fromhex('68') + struct.pack('<I', 0))
    b.extend(lea(0x93, rel(WRITTEN_VA)))
    b.extend(bytes.fromhex('52'))
    b.extend(bytes.fromhex('68') + struct.pack('<I', length))
    if src_kind == 'ebp':
        b.extend(lea(0x85, src_off))
    else:
        b.extend(lea(0x83, rel(suffix_va)))
    b.extend(bytes.fromhex('50'))
    b.extend(bytes.fromhex('56'))
    b.extend(call_ebx(rel(IAT_WRITEFILE)))
    b.extend(bytes.fromhex('56'))
    b.extend(call_ebx(rel(IAT_CLOSEHANDLE)))

    skip = len(b)
    struct.pack_into('<i', b, to_skip + 1, skip - (to_skip + 5))
    b[jz_all + 1] = (skip - (jz_all + 2)) & 0xFF
    b.extend(bytes.fromhex('619d'))
    b.extend(replay)
    jmp_at = len(b)
    b.extend(bytes.fromhex('e9'))
    b.extend(struct.pack('<i', resume_va - (base_va + jmp_at + 4)))
    return bytes(b)


fixed_va = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args()

    d = bytearray(open(a.src, 'rb').read())
    pe = pefile.PE(a.src)
    code = pe.sections[0]
    ib = pe.OPTIONAL_HEADER.ImageBase

    def align(v, al):
        return (v + al - 1) // al * al

    last = pe.sections[-1]
    cave_rva = align(last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData), 0x1000)
    cave_va = ib + cave_rva
    n = len(HOOKS)
    suffix_base = cave_va + BLOCK * n

    # 先算出各部分 VA
    suffix_va, fixed_area = {}, []
    off = 0
    for h in HOOKS:
        suffix_va[h[1]] = suffix_base + off
        off += len(h[1]) + 1
    fixed_base = suffix_base + off
    for pfx in (PUBLIC_FMT, ROOT_FMT):
        fixed_va[pfx] = fixed_base + sum(len(x) + 1 for x in fixed_area)
        fixed_area.append(pfx)

    payload = bytearray()
    sites = []
    for i, (site, name, kind, soff, length) in enumerate(HOOKS):
        if site == 'EP':
            site_va = ib + pe.OPTIONAL_HEADER.AddressOfEntryPoint
        else:
            site_va = site
        replay, resume = split_at_site(pe, d, site_va)
        blk_va = cave_va + i * BLOCK
        blk = make_block(blk_va + 7, suffix_va[name], resume, replay
