# -*- coding: utf-8 -*-
"""重建 replay_table.h：
   事件 0-42  = 真狗 50 层导入会话（含 zu06 的 003A/002A/000A 通道）
   事件 43+   = 旧表里的导出阶段事件（原 13-85）
"""
import io
import re

LOG = r'C:\Users\moo\Desktop\_dongle.log'
TBL = r'C:\Home\Workspace\UGit\psdto\cmykdrop\replay_table.h'

# 1) 新日志的完整事件
seq = []
pending = None
for line in io.open(LOG, encoding='gbk', errors='replace'):
    m = re.match(r'CAP dio op=([0-9A-F]{2}) addr=([0-9A-F]{4}) dtl=(\d+)', line)
    if m:
        pending = (m.group(1), m.group(2), int(m.group(3)))
        continue
    m = re.match(r'CAP pay op=([0-9A-F]{2}) addr=([0-9A-F]{4}) len=(\d+) data=([0-9A-F]*)', line)
    if m and pending and (m.group(1), m.group(2), int(m.group(3))) == pending:
        seq.append((pending[0], pending[1], pending[2], m.group(4)))
        pending = None

# 2) 旧表里 13 起的事件行
keep = []
for line in io.open(TBL, encoding='utf-8', errors='replace'):
    m = re.match(r'\s*\{/\*(\d+)\*/\s*(0x[0-9A-Fa-f]{2}),\s*(0x[0-9A-Fa-f]{4}),\s*(\d+),\s*\{((?:0x[0-9A-Fa-f]{2},?\s*)*)\}\},?\s*$', line)
    if m and int(m.group(1)) >= 13:
        keep.append((int(m.group(1)), m.group(2), m.group(3), int(m.group(4)), m.group(5)))
keep.sort()
print('新会话 %d 条 + 旧导出 %d 条' % (len(seq), len(keep)))

out = ['/* replay_table.h - 事件 0-42：真狗 50 层导入会话（含 zu06 通道）',
       '   事件 43+：导出阶段（旧抓取）。由 tools/_rebuild_replay2.py 生成。 */',
       '',
       'typedef struct { unsigned char op; unsigned short addr; unsigned short len; unsigned char data[1024]; } RP_EVT;',
       '',
       'static const RP_EVT g_rp[] = {']

n = 0
for (op, addr, dtl, hexdata) in seq:
    body = ','.join('0x%02X' % b for b in bytes.fromhex(hexdata))
    out.append('  {/*%d*/ 0x%s, 0x%s, %d, {%s}},' % (n, op, addr, dtl, body))
    n += 1

for (idx, top, taddr, tdtl, body) in keep:
    body = re.sub(r'\s+', '', body).rstrip(',')
    out.append('  {/*%d*/ %s, %s, %d, {%s}},' % (n, top, taddr, tdtl, body))
    n += 1

out.append('};')
out.append('')
out.append('#define RP_N %d' % n)
out.append('')

io.open(TBL, 'w', encoding='utf-8').write('\n'.join(out))
print('写出 %d 条事件' % n)
