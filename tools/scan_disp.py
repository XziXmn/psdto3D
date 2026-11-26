"""原始字节扫"访问 +disp 的指令"——不依赖线性反汇编（Delphi 的 CODE 段含数据，
线性扫描会错位，capstone 全段扫会漏）。

先用 ModRM 规则生成候选模式，命中后用 capstone 从该地址反汇编一条来确认。

    python tools/scan_disp.py <exe> --disp 2C [--size 1|4]
"""
import argparse
import sys

import capstone
import pefile


def build_patterns(disp, size):
    """返回 [(字节模式前缀, 说明, 额外立即数字节数)]，都带 2 字节 modrm+disp 或 1 字节 disp8。"""
    out = []
    if disp <= 0x7F:
        imm_len = {1: 1, 4: 4}[size]
        opcodes = {1: (b"\xC6", b"\x88"), 4: (b"\xC7", b"\x89")}[size]
        for op in opcodes:
            for modrm_hi in range(8):
                m = bytes([0x40 | (modrm_hi << 3) | 0x00, disp])
                out.append((op + m, "modrm=%02X" % m[0], imm_len if op in (b"\xC6", b"\xC7") else 0))
                for rm in range(8):
                    m2 = bytes([0x40 | (modrm_hi << 3) | rm, disp])
                    if (op + m2) not in [x[0] for x in out]:
                        out.append((op + m2, "modrm=%02X" % m2[0], imm_len if op in (b"\xC6", b"\xC7") else 0))
    # disp32 形式
    d4 = disp.to_bytes(4, "little")
    opcodes = {1: (b"\xC6", b"\x88"), 4: (b"\xC7", b"\x89")}[size]
    for op in opcodes:
        for rm in range(8):
            out.append((op + bytes([0x80 | rm]) + d4, "modrm=%02X disp32" % (0x80 | rm), 1 if size == 1 else 4))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--disp", default="2C")
    ap.add_argument("--size", type=int, default=1, choices=[1, 4])
    a = ap.parse_args()
    disp = int(a.disp, 16)

    pe = pefile.PE(a.exe)
    ib = pe.OPTIONAL_HEADER.ImageBase
    secs = []
    for s in pe.sections:
        secs.append((s.Name.rstrip(b"\0").decode("latin1"), ib + s.VirtualAddress,
                     s.get_data(), s.PointerToRawData, s.SizeOfRawData))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    pats = build_patterns(disp, a.size)
    seen = set()
    total = 0
    for name, va0, data, raw, rsz in secs:
        if name not in ("CODE", ".text"):
            continue
        for pat, note, _imm in pats:
            start = 0
            while True:
                j = data.find(pat, start)
                if j < 0:
                    break
                start = j + 1
                va = va0 + j
                if va in seen:
                    continue
                # 确认这确实是"指令起点"：从 j-1..j-6 里找能对齐到 va 的起点
                ok = False
                for back in range(0, 7):
                    if j - back < 0:
                        continue
                    for ins in md.disasm(data[j - back:j - back + 16], va - back):
                        if ins.address == va:
                            ok = True
                            print("  %08X  %-22s %s   [%s]" % (
                                va, ins.bytes.hex(), ins.mnemonic + " " + ins.op_str, note))
                        break
                    if ok:
                        break
                if not ok:
                    print("  %08X  %-22s (未对齐，可能误命中)   [%s]" % (va, pat.hex(), note))
                seen.add(va)
                total += 1
    print("合计 %d 处候选（disp=0x%02X size=%d）" % (total, disp, a.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
