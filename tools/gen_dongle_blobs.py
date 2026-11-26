"""从真实会话里抽出"参数型"501 应答块，生成 C 头文件。

输出 dongle_blobs.h：
    K_ECHO_KEYS[]   需要回显的命令键（cmd 前 4 字节）
    K_DATA_KEYS[]   需要返回固定参数块的命令键
    K_DATA_BLOBS[]  对应 501 字节块
"""
import re
import sys

RECORD = r"C:\Home\Workspace\UGit\psdto\归档\实验\_export_test\scsi_record.txt"
OUT = r"C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_blobs.h"

CDB_RE = re.compile(
    r"SCSI cdb\[16\]=([0-9A-Fa-f]{32}) dtl=(\d+) dash=(\d+) timeout=\d+ dbuf=([0-9A-Fa-f]+) data=([0-9A-Fa-f]*)")


def main():
    txt = open(RECORD, "rb").read().decode("latin1", "replace")
    ops = []
    for m in CDB_RE.finditer(txt):
        cdb = bytes.fromhex(m.group(1))
        ops.append({"op": cdb[0], "addr": cdb[4] | (cdb[5] << 8),
                    "len": cdb[2] | (cdb[3] << 8), "dtl": int(m.group(2)),
                    "data": bytes.fromhex(m.group(5)) if m.group(5) else b""})

    blk = None
    cmd = None
    echo_keys, data_keys, blobs = [], [], []
    for o in ops:
        if o["op"] == 0xDD:
            if o["len"] == 496:
                blk = o["data"]
            elif o["len"] == 10 and o["addr"] == 0x1F0:
                cmd = o["data"]
            continue
        if o["op"] != 0xD1 or o["dtl"] != 501 or cmd is None:
            continue
        key = int.from_bytes(cmd[:4], "little")
        r = o["data"]
        is_echo = blk is not None and r[16:16 + len(blk[16:])] == blk[16:]
        if is_echo:
            if key not in echo_keys:
                echo_keys.append(key)
        else:
            if key not in data_keys:
                data_keys.append(key)
                blobs.append(r)
                print("参数型命令 key=0x%08X  前 16 dword: %s" % (
                    key, [hex(v) for v in __import__("struct").unpack_from("<16I", r, 0)]))

    lines = ["/* 由 tools/gen_dongle_blobs.py 从 归档/实验/_export_test/scsi_record.txt 生成，勿手改 */",
             "#ifndef DONGLE_BLOBS_H", "#define DONGLE_BLOBS_H", ""]
    lines.append("static const unsigned K_ECHO_KEYS[] = { %s };" %
                 ", ".join("0x%08Xu" % k for k in echo_keys))
    lines.append("static const unsigned K_DATA_KEYS[] = { %s };" %
                 ", ".join("0x%08Xu" % k for k in data_keys))
    for i, b in enumerate(blobs):
        lines.append("static const unsigned char K_DATA_BLOB_%d[501] = {" % i)
        for j in range(0, 501, 20):
            lines.append("    " + ", ".join("0x%02X" % x for x in b[j:j + 20]) + ",")
        lines.append("};")
    lines.append("static const unsigned char *K_DATA_BLOBS[] = { %s };" %
                 ", ".join("K_DATA_BLOB_%d" % i for i in range(len(blobs))))
    lines.append("")
    lines.append("#define K_ECHO_COUNT (sizeof(K_ECHO_KEYS)/sizeof(unsigned))")
    lines.append("#define K_DATA_COUNT (sizeof(K_DATA_KEYS)/sizeof(unsigned))")
    lines.append("")
    lines.append("#endif")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("写出", OUT)
    print("回显型 key:", [hex(k) for k in echo_keys])
    print("参数型 key:", [hex(k) for k in data_keys])
    return 0


if __name__ == "__main__":
    sys.exit(main())
