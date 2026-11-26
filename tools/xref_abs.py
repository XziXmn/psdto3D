"""找某个**绝对地址全局变量**的所有访问点（读/写），带上下文。

    python tools/xref_abs.py <exe> 0x523154 [--more 2]

用 capstone 全 CODE 段扫描（skipdata），筛 mem.base==0 且 disp==目标 的指令。
"""
import argparse
import sys

import capstone
import pefile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("addr")
    ap.add_argument("--more", type=int, default=6, help="每个命中点前后各多打几条")
    a = ap.parse_args()
    want = int(a.addr, 16)

    pe = pefile.PE(a.exe)
    ib = pe.OPTIONAL_HEADER.ImageBase
    sec = None
    for s in pe.sections:
        if s.Name.rstrip(b"\0").decode("latin1") in ("CODE", ".text"):
            sec = s
            break
    data = sec.get_data()
    base = ib + sec.VirtualAddress
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True

    insns = []
    for ins in md.disasm(data, base):
        if ins.id == 0:
            continue
        insns.append(ins)
    idx = {}
    for i, ins in enumerate(insns):
        idx[ins.address] = i

    hits = 0
    for i, ins in enumerate(insns):
        try:
            ops = ins.operands
        except capstone.CsError:
            continue
        found = False
        for op in ops:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == 0 and \
               op.mem.index == 0 and (op.mem.disp & 0xFFFFFFFF) == want:
                found = True
        if not found:
            continue
        hits += 1
        print("---- 0x%08X ----" % ins.address)
        for j in range(max(0, i - a.more), min(len(insns), i + a.more + 1)):
            t = insns[j]
            mark = ">>" if j == i else "  "
            print(" %s %08X  %-18s %s" % (mark, t.address, t.bytes.hex(), t.mnemonic + " " + t.op_str))
    print("\n共 %d 处访问 0x%08X" % (hits, want))
    return 0


if __name__ == "__main__":
    sys.exit(main())
