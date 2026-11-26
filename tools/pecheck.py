"""体检：壳 / 反调试 / 反汇编特征。

    python tools/pecheck.py <exe>

输出：节表与熵、入口点、导入表、TLS、可疑 API、常见壳特征。
"""
import math
import sys
from collections import Counter

import capstone
import pefile


SUSPECT_API = [
    "IsDebuggerPresent", "CheckRemoteDebuggerPresent", "NtQueryInformationProcess",
    "OutputDebugString", "GetTickCount", "QueryPerformanceCounter", "CloseHandle",
    "UnhandledExceptionFilter", "SetUnhandledExceptionFilter", "VirtualProtect",
    "VirtualAlloc", "GetModuleHandleA", "LoadLibraryA", "GetProcAddress",
    "CreateToolhelp32Snapshot", "Process32First", "Thread32First",
    "NtSetInformationThread", "SuspendThread", "GetThreadContext",
]


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    p = sys.argv[1]
    pe = pefile.PE(p)
    ib = pe.OPTIONAL_HEADER.ImageBase
    print("== 基本信息 ==")
    print("  ImageBase=0x%X  EntryPoint=0x%X  Subsystem=%d" % (
        ib, ib + pe.OPTIONAL_HEADER.AddressOfEntryPoint, pe.OPTIONAL_HEADER.Subsystem))
    print("  DllCharacteristics=0x%X  SizeOfImage=0x%X" % (
        pe.OPTIONAL_HEADER.DllCharacteristics, pe.OPTIONAL_HEADER.SizeOfImage))
    print("  TLS 目录:", "有" if pe.OPTIONAL_HEADER.DATA_DIRECTORY[9].VirtualAddress else "无")
    print("  资源目录:", "有" if pe.OPTIONAL_HEADER.DATA_DIRECTORY[2].VirtualAddress else "无")
    print("  重定位:", "有" if pe.OPTIONAL_HEADER.DATA_DIRECTORY[5].VirtualAddress else "无")
    print()
    print("== 节表（熵 > 7.0 通常意味着压缩/加密） ==")
    print("  %-10s %-10s %-10s %-8s %s" % ("名字", "VA", "虚拟大小", "熵", "备注"))
    for s in pe.sections:
        name = s.Name.rstrip(b"\0").decode("latin1")
        e = entropy(s.get_data())
        note = ""
        if e > 7.2:
            note = "**高熵**"
        if name.lower() in ("upx0", "upx1", ".aspack", ".adata", "petite", ".themida", ".vmp0"):
            note += " 壳特征"
        print("  %-10s 0x%-8X 0x%-8X %-8.2f %s" % (name, ib + s.VirtualAddress,
                                                   s.Misc_VirtualSize, e, note))
    print()
    print("== 导入的 DLL ==")
    dlls = []
    try:
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            d = entry.dll.decode()
            dlls.append(d)
            print("  %-24s %d 个函数" % (d, len(entry.imports)))
    except AttributeError:
        print("  （没有导入表！典型加壳特征）")
    print()
    got = {d.lower() for d in dlls}
    print("== 可疑 API ==")
    hits = []
    try:
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name:
                    n = imp.name.decode()
                    if n in SUSPECT_API:
                        hits.append(n)
                        print("  %-28s <- %s @ IAT 0x%X" % (n, entry.dll.decode(), imp.address))
    except AttributeError:
        pass
    if not hits:
        print("  （无）")
    print()
    # 找 exe 里对 IsDebuggerPresent 之类字符串/序号的使用
    raw = open(p, "rb").read()
    print("== 字面量特征 ==")
    for needle in (b"IsDebuggerPresent", b"CheckRemoteDebuggerPresent",
                   b"NtQueryInformationProcess", b"\\\\.\\NTICE", b"SOFTICE",
                   b"OLLYDBG", b"ollydbg", b"idaq", b"PEiD", b"protool"):
        i = raw.find(needle)
        print("  %-30s %s" % (needle.decode("latin1"), ("文件偏移 0x%X" % i) if i >= 0 else "无"))
    print()
    print("== 入口点附近反汇编（看是否有壳的跳板） ==")
    ep = pe.OPTIONAL_HEADER.AddressOfEntryPoint
    data = None
    for s in pe.sections:
        if s.VirtualAddress <= ep < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            data = s.get_data()[ep - s.VirtualAddress: ep - s.VirtualAddress + 200]
            break
    if data:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for i, ins in enumerate(md.disasm(data, ib + ep)):
            print("  %08X  %-18s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic + " " + ins.op_str))
            if i >= 18:
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
