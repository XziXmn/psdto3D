"""找"谁写 +0x2C"：全 CODE 段反汇编，筛出目标操作数是 disp=0x2C 的字节写。

    python tools/find2c.py <exe> [--disp 2C] [--write-only]

输出：地址、字节、助记符、以及写入的立即数（若有）。
顺带统计 disp=0x2C 的**读**，方便区分"写状态"和"读状态"。
"""
import argparse
import struct
import sys

import capstone
import pefile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--disp", default="2C")
    ap.add_argument("--write-only", action="store_true")
    ap.add_argument("--scale", type=int, default=-1, help="只保留 mem.scale 等于它的命中（-1=不过滤）")
    a = ap.parse_args()

    pe = pefile.PE(a.exe)
    ib = pe.OPTIONAL_HEADER.ImageBase
    code_sec = None
    for s in pe.sections:
        name = s.Name.rstrip(b"\0").decode("latin1")
        if name in ("CODE", ".text"):
            code_sec = s
            break
    if code_sec is None:
        raise SystemExit("no CODE section")
    data = code_sec.get_data()
    base = ib + code_sec.VirtualAddress
    disp = int(a.disp, 16)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True          # Delphi 的 CODE 段夹着数据，不跳过会立刻停住
    writes, reads = [], []
    for ins in md.disasm(data, base):
        if ins.id == 0:               # skipdata 产生的伪指令
            continue
        try:
            ops = ins.operands
        except capstone.CsError:
            continue
        if not ops:
            continue
        mem = None
        for op in ops:
            if op.type == capstone.x86.X86_OP_MEM:
                mem = op
                break
        if mem is None or mem.mem.disp != disp:
            continue
        if a.scale >= 0 and mem.mem.scale != a.scale:
            continue
        # 判断是否写：第一个操作数是同一个内存操作数
        first = ops[0]
        is_write = (first.type == capstone.x86.X86_OP_MEM and
                    first.mem.disp == disp and
                    first.mem.base == mem.mem.base and
                    first.mem.index == mem.mem.index)
        item = (ins.address, ins.bytes.hex(), "%s %s" % (ins.mnemonic, ins.op_str))
        if is_write:
            writes.append(item)
        else:
            reads.append(item)

    print("== 写 [+0x%02X] 共 %d 处 ==" % (disp, len(writes)))
    for addr, b, t in writes:
        print("  %08X  %-24s %s" % (addr, b, t))
    if not a.write_only:
        print("== 读 [+0x%02X] 共 %d 处 ==" % (disp, len(reads)))
        for addr, b, t in reads[:40]:
            print("  %08X  %-24s %s" % (addr, b, t))
        if len(reads) > 40:
            print("  ... 省略 %d 条" % (len(reads) - 40))
    return 0


if __name__ == "__main__":
    sys.exit(main())
