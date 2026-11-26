"""看某个导出函数的调用约定与参数数量（objdump 里 ret N 的 N 就是栈参字节数）。

    python tools/export_abi.py <dll> <exportname> [--n 40]
"""
import argparse
import sys

import capstone
import pefile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("name")
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()

    pe = pefile.PE(a.dll)
    ib = pe.OPTIONAL_HEADER.ImageBase
    exp = pe.DIRECTORY_ENTRY_EXPORT
    target = None
    for s in exp.symbols:
        if s.name and s.name.decode() == a.name:
            target = ib + s.address
            break
    if target is None:
        print("导出里没有 %s" % a.name)
        return 1
    # 解析到文件
    data = None
    for sec in pe.sections:
        va = ib + sec.VirtualAddress
        if va <= target < va + max(sec.Misc_VirtualSize, sec.SizeOfRawData):
            data = sec.get_data()[target - va:target - va + 4096]
            break
    if data is None:
        print("地址 0x%X 不在任何段里" % target)
        return 1
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    print("%s @ 0x%X" % (a.name, target))
    n = 0
    rets = []
    for ins in md.disasm(data, target):
        print("  %08X  %-20s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic + " " + ins.op_str))
        if ins.mnemonic.startswith("ret"):
            rets.append((ins.address, ins.mnemonic + " " + ins.op_str))
            if len(rets) >= 3:
                break
        n += 1
        if n >= a.n:
            break
    print()
    for addr, txt in rets:
        print("RET: %08X  %s" % (addr, txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
