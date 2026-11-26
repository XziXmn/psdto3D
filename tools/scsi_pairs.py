"""把真实会话按"写→读"配对，验证 501 字节应答的内容来源。

假设：write(addr=0, len=496, buf) 之后，write(addr=0x1F0, len=10, cmd) 再
read(addr=0x1F0, len+5) 得到的 501 字节 = 4 个 dword 头 + 刚写的 496 字节（或其变换）。

验证方法：对每一对 (496 写, 501 读)，检查应答里是否包含写入的字节序列。

    python tools/scsi_pairs.py
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
        ops.append({
            "op": cdb[0], "addr": cdb[4] | (cdb[5] << 8),
            "len": cdb[2] | (cdb[3] << 8), "dtl": int(m.group(2)),
            "data": bytes.fromhex(m.group(5)) if m.group(5) else b"",
        })

    print("=== 写操作明细 ===")
    for i, o in enumerate(ops):
        if o["op"] == 0xDD:
            print("  #%02d 写 addr=0x%04X len=%-4d  %s" % (
                i, o["addr"], o["len"], o["data"][:48].hex(" ")))

    print("\n=== 每对 (先写 496 / 后读 501) 的对应关系 ===")
    last496 = None
    for i, o in enumerate(ops):
        if o["op"] == 0xDD and o["len"] == 496:
            last496 = o["data"]
        if o["op"] == 0xD1 and o["dtl"] == 501:
            resp = o["data"]
            head = resp[:16]
            body = resp[16:]
            print("\n  #%02d 读 501：头=%s" % (i, head.hex(" ")))
            if last496:
                # 看 body 前 32 字节与 last496 前 32 字节的关系
                print("      上次写的 496 前32: %s" % last496[:32].hex(" "))
                print("      应答 body 前32    : %s" % body[:32].hex(" "))
                same = body[:len(last496)] == last496
                print("      body == 上次写的块 ? %s" % same)
                if not same:
                    diff = [(k, last496[k], body[k]) for k in range(min(len(last496), len(body)))
                            if last496[k] != body[k]][:6]
                    print("      前几处不同(偏移,写,读):", diff)
            else:
                print("      （前面没有 496 字节的写）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
