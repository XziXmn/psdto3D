"""把装载器的两个"行块循环次数"改成用记录数 [0x52315C]，而不是 [ebp-0x60]。

背景（本轮实测）
----------------
`Invalid numeric input` 的根因：0x511408 里两个行块循环的次数来自 [ebp-0x60]（由 0x4D2F14
按行 8 的 flag + 层数算出），对本工程算出 ~70，而文件里只有 32 行 → 令牌流错位。

上一轮的补丁把它换成 [ebp-0x54]，实测那也不是层数（跑出第 69 条记录 → 越界
`AV 0x511ADC Write of address 027B4000`）。

正解：用 [0x52315C]——导入 PSD 之后它就是层数 32（记录表就是按它 SetLength 的）。

实现：代码洞 0x514324（220 字节全 0）里放两个桩，原指令改成 5 字节 jmp。

    python tools/patch_loader_count2.py <exe> [--dry-run] [--report r.json]
"""
import argparse
import json
import os
import struct
import sys

import pefile

CAVE_A = 0x514324
CAVE_B = 0x514340
SITE_A = 0x511A03          # mov eax,[ebp-0x60]
SITE_B = 0x511A81
JMP_IF_NEG_A = 0x511A81    # 原 jl 目标
JMP_IF_NEG_B = 0x51215D
CONT_A = 0x511A0A          # 原 jl 之后
CONT_B = 0x511A8C
COUNT_GLOBAL = 0x52315C


def stub(neg_target, cont_target):
    """mov eax,[COUNT_GLOBAL]; test eax,eax; jl neg; jmp cont"""
    b = bytearray()
    b += b"\xA1" + struct.pack("<I", COUNT_GLOBAL)      # mov eax,[imm32]
    b += b"\x85\xC0"                                     # test eax,eax
    b += b"\x0F\x8C" + struct.pack("<i", neg_target - 0)  # 占位，稍后重算
    b += b"\xE9" + struct.pack("<i", cont_target - 0)
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    pe = pefile.PE(a.exe)
    ib = pe.OPTIONAL_HEADER.ImageBase
    data = bytearray(open(a.exe, "rb").read())

    def va2off(va):
        r = va - ib
        for s in pe.sections:
            if s.VirtualAddress <= r < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
                d = r - s.VirtualAddress
                if d < s.SizeOfRawData:
                    return s.PointerToRawData + d
        raise SystemExit("VA 0x%X 不在任何节里" % va)

    # 检查洞是不是空的
    for cave in (CAVE_A, CAVE_B):
        off = va2off(cave)
        if any(data[off:off + 24]):
            raise SystemExit("洞 0x%X 已被占用（不是全 0）" % cave)

    def build_at(cave, site, neg, cont):
        b = bytearray()
        b += b"\xA1" + struct.pack("<I", COUNT_GLOBAL)          # mov eax,[count]
        b += b"\x85\xC0"                                         # test eax,eax
        jl_at = cave + len(b)                                    # 0F 8C 的位置
        b += b"\x0F\x8C" + struct.pack("<i", neg - (jl_at + 6))
        jmp_at = cave + len(b)
        b += b"\xE9" + struct.pack("<i", cont - (jmp_at + 5))
        return bytes(b)

    stub_a = build_at(CAVE_A, SITE_A, JMP_IF_NEG_A, CONT_A)
    stub_b = build_at(CAVE_B, SITE_B, JMP_IF_NEG_B, CONT_B)

    def patch_site(site, cave):
        off = va2off(site)
        rel = cave - (site + 5)
        data[off:off + 5] = b"\xE9" + struct.pack("<i", rel)

    if not a.dry_run:
        oa = va2off(CAVE_A)
        data[oa:oa + len(stub_a)] = stub_a
        ob = va2off(CAVE_B)
        data[ob:ob + len(stub_b)] = stub_b
        patch_site(SITE_A, CAVE_A)
        patch_site(SITE_B, CAVE_B)

    rep = {
        "exe": a.exe,
        "dry_run": a.dry_run,
        "cave_a": hex(CAVE_A), "stub_a": stub_a.hex(),
        "cave_b": hex(CAVE_B), "stub_b": stub_b.hex(),
        "sites": [hex(SITE_A), hex(SITE_B)],
        "count_global": hex(COUNT_GLOBAL),
    }
    if not a.dry_run:
        pe.close()
        tmp = a.exe + ".tmp"
        with open(tmp, "wb") as f:
            f.write(bytes(data))
        os.replace(tmp, a.exe)
        rep["written"] = True
    if a.report:
        open(a.report, "w", encoding="utf-8").write(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
