# -*- coding: utf-8 -*-
"""用真狗 50 层会话的完整数据替换回放表事件 0-12（对齐 op/addr/dtl）。
导出阶段的事件 13-85 保持旧抓取不动。"""
import io
import re

LOG = r'C:\Users\moo\Desktop\_dongle.log'
TBL = r'C:\Home\Workspace\UGit\pspto\cmykdrop\replay_table.h'
TBL = r'C:\Home\Workspace\UGit\psdto\cmykdrop\replay_table.h'

seq = []
pending = None
for line in open(LOG, encoding='gbk', errors='replace'):
    m = re.match(r'CAP dio op=([0-9A-F]{2}) addr=([0-9A-F]{4}) dtl=(\d+)', line)
    if m:
        pending = (m.group(1), m.group(2), int(m.group(3)))
        continue
    m = re.match(r'CAP pay op=([0-9A-F]{2}) addr=([0-9A-F]{4}) len=(\d+) data=([0-9A-F]*)', line)
    if m and pending and (m.group(1), m.group(2), int(m.group(3))) == pending:
        seq.append((pending[0], int(pending[1], 16), pending[2], m.group(4)))
        pending = None

src = io.open(TBL, encoding='utf-8', errors='replace').read()
n_repl = 0

for i, (op, addr, dtl, hexdata) in enumerate(seq):
    if i > 12:
        break
    pat = re.compile(r'(\{/\*%d\*/\s*0x[0-9A-Fa-f]{2},\s*0x[0-9A-Fa-f]{4},\s*%d,\s*\{)([^}]*)(\}\})' % (i, dtl))
    m = pat.search(src)
    if not m:
        print('事件 %d 未找到匹配' % i)
        continue
    # 校验 op/addr
    header = m.group(1)
    if ('0x%02X' % int(op, 16)) not in header or ('0x%04X' % addr) not in header:
        print('事件 %d 头部不匹配: %s' % (i, header[:60]))
        continue
    new_body = ','.join('0x%02X' % b for b in bytes.fromhex(hexdata))
    src = src[:m.start(3)] + new_body + src[m.end(3):]
    n_repl += 1

io.open(TBL, 'w', encoding='utf-8').write(src)
print('已替换 %d 个事件（导入阶段 0-12）' % n_repl)
