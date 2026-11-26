"""把真实会话（scsi_record.txt）解析成一条条 SCSI 事务，并与仿真表比对。

输出：
  · 真实会话里出现的 (op, addr, len, dtl) 序列与每条的应答字节
  · 仿真器 dongle_mem.h 里对应槽位的应答
  · 不一致清单（这才是 exe 觉得"狗不对"的根因候选）

    python tools/scsi_cmp.py [--record 归档/实验/_export_test/scsi_record.txt]
"""
import argparse
import os
import re
import sys

CDB_RE = re.compile(r"SCSI cdb\[16\]=([0-9A-Fa-f]{32}) dtl=(\d+) dash=(\d+) timeout=\d+ dbuf=([0-9A-Fa-f]+) data=([0-9A-Fa-f]*)")
TABLE_RE = re.compile(r"\{\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\"((?:[0-9A-Fa-f]{2})*)\"\s*,\s*\"((?:[0-9A-Fa-f]{2})*)\"\s*\}")


def parse_record(path):
    txt = open(path, "rb").read().decode("latin1", "replace")
    out = []
    for m in CDB_RE.finditer(txt):
        cdb = bytes.fromhex(m.group(1))
        dtl = int(m.group(2))
        dash = int(m.group(3))
        data = bytes.fromhex(m.group(5)) if m.group(5) else b""
        op = cdb[0]
        ln = cdb[2] | (cdb[3] << 8)
        addr = cdb[4] | (cdb[5] << 8)
        out.append({'op': op, 'addr': addr, 'len': ln, 'dtl': dtl, 'dash': dash, 'data': data})
    return out


def parse_table(path):
    txt = open(path, "r", encoding="utf-8", errors="replace").read()
    rows = []
    for m in TABLE_RE.finditer(txt):
        addr = int(m.group(1), 0)
        ln = int(m.group(2))
        st = bytes.fromhex(m.group(4))
        data = bytes.fromhex(m.group(5))
        rows.append({'addr': addr, 'len': ln, 'st': st, 'data': data, 'used': m.group(3)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default=r"归档\实验\_export_test\scsi_record.txt")
    ap.add_argument("--table", default=r"cmykdrop\dongle_mem.h")
    a = ap.parse_args()
    if not os.path.exists(a.record):
        raise SystemExit("没有 %s" % a.record)
    ops = parse_record(a.record)
    print("真实会话：%d 条 SCSI 事务" % len(ops))
    seq = [(o['op'], o['addr'], o['len'], o['dtl']) for o in ops]
    print("\n=== 事务序列（op/addr/len/dtl） ===")
    for i, s in enumerate(seq):
        op = "写" if s[0] == 0xDD else ("读" if s[0] == 0xD1 else "其它")
        print("  #%02d %s addr=0x%04X len=%-4d dtl=%-4d" % (i, op, s[1], s[2], s[3]))

    print("\n=== 读操作的应答（前 24 字节） ===")
    for i, o in enumerate(ops):
        if o['op'] != 0xD1:
            continue
        print("  #%02d addr=0x%04X dtl=%-4d resp=%s" % (
            i, o['addr'], o['dtl'], o['data'][:24].hex(" ")))

    if os.path.exists(a.table):
        rows = parse_table(a.table)
        print("\n=== 仿真表（dongle_mem.h）共 %d 槽 ===" % len(rows))
        for r in rows[:40]:
            print("  addr=0x%04X len=%-4d st=%s data=%s" % (
                r['addr'], r['len'], r['st'].hex(" "), r['data'][:16].hex(" ")))
        # 逐条比对
        print("\n=== 逐条比对 ===")
        bad = 0
        for i, o in enumerate(ops):
            if o['op'] != 0xD1:
                continue
            cand = [r for r in rows if r['addr'] == o['addr'] and r['len'] + 5 == o['dtl']]
            if not cand:
                print("  #%02d addr=0x%04X dtl=%d → 仿真表**没有**这个槽" % (i, o['addr'], o['dtl']))
                bad += 1
                continue
            r = cand[0]
            want = (r['data'] + r['st'])
            got = o['data']
            same = (want[:len(got)] == got[:len(want)])
            if not same:
                print("  #%02d addr=0x%04X dtl=%d → **不一致**" % (i, o['addr'], o['dtl']))
                print("      真狗: %s" % got[:24].hex(" "))
                print("      仿真: %s" % want[:24].hex(" "))
                bad += 1
        print("\n不一致/缺失 %d 条" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
