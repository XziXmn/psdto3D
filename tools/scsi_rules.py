"""推导加密狗的真实协议规则（回显模型），供忠实仿真使用。

对每条读，尝试用"前面最近的写"来解释应答：
  R1: 应答 == 16 字节 0x7B 头 + 上次写[16:] + 5 字节尾
  R2: 应答 == 上次写[:len] + 5 字节状态
  R3: 其它（打印出来人工看）

    python tools/scsi_rules.py
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

    last = {}          # addr -> 最近一次写入的数据
    stats = {}
    for i, o in enumerate(ops):
        if o["op"] == 0xDD:
            last[o["addr"]] = o["data"]
            continue
        if o["op"] != 0xD1:
            continue
        resp = o["data"]
        w = last.get(o["addr"], b"")
        verdict = None
        if len(resp) >= 16 and resp[:16] == b"\x7b\x00\x00\x00" * 4:
            body = resp[16:]
            core = w[16:] if len(w) > 16 else b""
            tail = body[len(core):] if len(core) and body[:len(core)] == core else None
            if tail is not None:
                verdict = "R1 头16 + 写[16:] + 尾%d(%s)" % (len(tail), tail.hex())
        if verdict is None and w and resp[:len(w)] == w[:len(resp)]:
            verdict = "R2 回显写[:%d]" % len(resp)
        if verdict is None and len(resp) == 5:
            verdict = "R-ack %s（上次写 addr=0x%04X len=%d）" % (resp.hex(" "), o["addr"], len(w))
        if verdict is None:
            verdict = "R? 未匹配（上次写 len=%d）resp=%s" % (len(w), resp[:24].hex(" "))
        key = verdict.split("（")[0][:24]
        stats[key] = stats.get(key, 0) + 1
        print("  #%02d 读 addr=0x%04X dtl=%-4d → %s" % (i, o["addr"], o["dtl"], verdict))

    print("\n=== 规则统计 ===")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print("  %-26s %d 次" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
