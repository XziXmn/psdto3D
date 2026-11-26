# -*- coding: utf-8 -*-
"""修正表头定义：用 dongle_emu.c 实际引用的 RP_EVT / g_rp / RP_N。"""
import io
import re

TBL = r'C:\Home\Workspace\UGit\psdto\cmykdrop\replay_table.h'
s = io.open(TBL, encoding='utf-8').read()

HEADER = '''/* replay_table.h - 事件 0-12 来自真狗 50 层会话（2026-11-25 记录版日志），
   事件 13+ 保留自旧抓取（导出阶段）。由 _rebuild_replay.py 生成。 */

typedef struct { unsigned char op; unsigned short addr; unsigned short len; unsigned char data[1024]; } RP_EVT;

static const RP_EVT g_rp[] = {
'''

# 去掉我自己加的错误头
start = s.find('static const struct replay_event g_replay[] = {')
end = s.find('{/*0*/')
assert start > 0 and end > start
s = HEADER + s[end:]

# 尾部：去掉 g_replay/REPLAY_N，换成 RP_N
s = s.replace('#define REPLAY_N %d' % (s.count('{/*') if False else 86), '')
s = re.sub(r'#define REPLAY_N \d+', '#define RP_N %d' % (s.count('{/*') + 0), s)

# 数一下事件数
n = len(re.findall(r'\{/\*\d+\*/', s))
s = re.sub(r'#define RP_N \d+', '#define RP_N %d' % n, s)
s = s.rstrip() + '\n'
io.open(TBL, 'w', encoding='utf-8').write(s)
print('表头已修正，事件数 %d' % n)
