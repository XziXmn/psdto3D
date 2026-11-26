# -*- coding: utf-8 -*-
"""把任务总结转成 GBK txt（记事本友好），并把 emoji/箭头换成纯文本。"""
import io
import re

SRC = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\任务总结_2026-11-25.md'
DST = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\任务总结_2026-11-25.txt'

t = io.open(SRC, encoding='utf-8').read()

repl = {
    '✅': '[完成]',
    '❌': '[失败]',
    '→': '->',
    '←': '<-',
    '｜': '|',
    '·': '-',
    '—': '--',
}
for k, v in repl.items():
    t = t.replace(k, v)

# markdown 标题降级为纯文本标记
t = re.sub(r'^#{1,6}\s*', '', t, flags=re.M)
t = t.replace('**', '')
t = t.replace('```', '')
t = re.sub(r'```[a-z]*\n', '', t)
# 表格保留，但把分隔行简化
t = re.sub(r'^\|[\s\-:|]+\|$', '', t, flags=re.M)

t = t.replace('\r\n', '\n').replace('\n', '\r\n')
io.open(DST, 'wb').write(t.encode('gbk', errors='replace'))
print('写出 %s (%d 字符)' % (DST, len(t)))
