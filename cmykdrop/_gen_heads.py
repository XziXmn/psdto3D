# 生成 24 字节头序列表（从带狗日志）
import re
def parse(p):
    ev = []
    for line in open(p, encoding="utf-8", errors="replace"):
        m = re.search(r"LOG 写 addr=([0-9A-Fa-f]+) len=(\d+) dtl=(\d+) data=(.*)", line)
        if m: ev.append(("W", int(m.group(1),16), int(m.group(2)), m.group(4).strip())); continue
        m = re.search(r"LOG 读 addr=([0-9A-Fa-f]+) dtl=(\d+) ret=(\d+) data=(.*)", line)
        if m: ev.append(("R", int(m.group(1),16), int(m.group(2)), m.group(4).strip()))
    return ev
ev = parse(r"C:\Home\Workspace\UGit\psdto\归档\实验\_review\licensed_scsi_full.log")
heads = []
cmds  = []
for i,(k,a,n,d) in enumerate(ev):
    if k=="R" and n==501:
        b = bytes.fromhex(d.replace(" ",""))
        heads.append(b)
        # 找它前面最近的 10 字节命令写
        c = None
        for j in range(i-1, max(-1,i-4), -1):
            if ev[j][0]=="W" and ev[j][2]==10:
                c = bytes.fromhex(ev[j][3].replace(" ","")); break
        cmds.append(c)
lines = []
for h, c in zip(heads, cmds):
    cs = c.hex() if c else "00"*10
    lines.append(cs + " " + h.hex())
open(r"C:\Home\Workspace\UGit\psdto\cmykdrop\resp_heads.h","w").write(
    "/* 带狗实测：cmd10 + 应答前24字节，按出现顺序 */\n"
    "static const char *K_RESP_HEADS[] = {\n"
    + "".join('  "%s",\n' % l for l in lines) + "};\n"
    "static const int K_RESP_N = %d;\n" % len(lines))
print("生成 %d 条" % len(lines))
for l in lines: print("  ", l)
