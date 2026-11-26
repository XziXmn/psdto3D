# -*- coding: utf-8 -*-
"""重建 replay_table.h：
- 事件 0-12：用记录版日志里的真狗 50 层会话数据（逐行生成，不做正则拼接）
- 事件 13-85：从现有（部分损坏的）文件里按行提取，未被动过的部分
"""
import io
import re

LOG = r'C:\Users\moo\Desktop\_dongle.log'
TBL = r'C:\Home\Workspace\UGit\psdto\cmykdrop\replay_table.h'

# 1) 日志事件
seq = []
pending = None
for line in open(LOG, encoding='gbk', errors='replace'):
    m = re.match(r'CAP dio op=([0-9A-F]{2}) addr=([0-9A-F]{4}) dtl=(\d+)', line)
    if m:
        pending = (m.group(1), m.group(2), int(m.group(3)))
        continue
    m = re.match(r'CAP pay op=([0-9A-F]{2}) addr=([0-9A-F]{4}) len=(\d+) data=([0-9A-F]*)', line)
    if m and pending and (m.group(1), m.group(2), int(m.group(3))) == pending:
        seq.append((pending[0], pending[1], pending[2], m.group(4)))
        pending = None

# 2) 现有文件里事件 13 起的完整行（逐行正则，单行内闭合）
keep_lines = []
for line in io.open(TBL, encoding='utf-8', errors='replace'):
    m = re.match(r'\s*\{/\*(\d+)\*/\s*(0x[0-9A-Fa-f]{2}),\s*(0x[0-9A-Fa-f]{4}),\s*(\d+),\s*\{((?:0x[0-9A-Fa-f]{2},?\s*)*)\}\},?\s*$', line)
    if m:
        idx = int(m.group(1))
        if idx >= 13:
            keep_lines.append((idx, line.rstrip('\r\n')))

keep_lines.sort()
print('从损坏文件中保住事件 13+ 共 %d 条' % len(keep_lines))

# 3) 生成新表
out = ['/* replay_table.h —— 事件 0-12 来自真狗 50 层会话（2026-11-25 记录版日志），',
       '   事件 13+ 保留自旧抓取（导出阶段）。由 _rebuild_replay.py 生成。 */',
       'static const struct replay_event g_replay[] = {']

for i, (op, addr, dtl, hexdata) in enumerate(seq):
    data = bytes.fromhex(hexdata)
    body = ','.join('0x%02X' % b for b in data)
    out.append('  {/*%d*/ 0x%s, 0x%s, %d, {%s}},' % (i, op, addr, dtl, body))

for idx, line in keep_lines:
    out.append(line)

out.append('};')
out.append('#define REPLAY_N %d' % (len(seq) + len(keep_lines)))
out.append('')

io.open(TBL, 'w', encoding='utf-8').write('\n'.join(out))
print('写出新表：日志 %d 条 + 保留 %d 条 = %d 条' % (len(seq), len(keep_lines), len(seq) + len(keep_lines)))
