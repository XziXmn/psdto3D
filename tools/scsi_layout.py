"""精确量 501 字节应答的结构：头/回显起点/尾。

对每条 501 读，用"前一条 496 写"去对齐，求：
  · 在应答里，写入块 [16:] 出现在哪个偏移（没有则记为纯数据响应）
  · 该块之前有多少字节、之后有多少字节，以及它们的具体内容

    python tools/scsi_layout.py
"""
import argparse
import re
import sys

CDB_RE = re.compile(
    r"SCSI cdb\[16\]=([0-9A-Fa-f]{32}) dtl=(\d+) dash=(\d+) timeout=\d+ dbuf=([0-9A-Fa-f]+) data=([0-9A-Fa-f]*)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default=r"归档\实验\_export_test\scsi_record.txt")
    a = ap.parse_args()
    txt = open(a.record, "rb").read().decode("latin1", "replace")
    ops = []
    for m in CDB_RE.finditer(txt):
        cdb = bytes.fromhex(m.group(1))
        ops.append({"op": cdb[0], "addr": cdb[4] | (cdb[5] << 8),
                    "len": cdb[2] | (cdb[3] << 8), "dtl": int(m.group(2)),
                    "data": bytes.fromhex(m.group(5)) if m.group(5) else b""})

    blk = None          # 最近一次 496 写
    cmd = None          # 最近一次 10 写
    print("=== 501 字节读的结构 ===")
    for i, o in enumerate(ops):
        if o["op"] == 0xDD:
            if o["len"] == 496:
                blk = o["data"]
            elif o["len"] == 10 and o["addr"] == 0x1F0:
                cmd = o["data"]
            continue
        if o["op"] != 0xD1 or o["dtl"] != 501:
            continue
        r = o["data"]
        needle = blk[16:] if blk else b""
        pos = r.find(needle) if needle else -1
        print("\n  #%02d 命令=%s" % (i, cmd.hex(" ") if cmd else "-"))
        print("       应答长度 %d" % len(r))
        if pos >= 0:
            print("       回显块出现在偏移 %d（长 %d）" % (pos, len(needle)))
            print("       块前 %d 字节: %s" % (pos, r[:pos].hex(" ")))
            tail = r[pos + len(needle):]
            print("       块后 %d 字节: %s" % (len(tail), tail.hex(" ")))
        else:
            # 纯数据响应：按 dword 打印前 20 个
            import struct
            n = min(len(r) // 4, 20)
            vals = struct.unpack_from("<%dI" % n, r, 0)
            print("       非回显响应，前 %d 个 dword: %s" % (n, [hex(v) for v in vals]))
            print("       尾 5 字节: %s" % r[-5:].hex(" "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
