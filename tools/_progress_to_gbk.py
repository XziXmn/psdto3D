# -*- coding: utf-8 -*-
"""项目进度 md -> GBK txt（记事本友好）"""
import io
import re

SRC = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\项目进度_2026-11-26.md'
DST = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\项目进度_2026-11-26.txt'

t = io.open(SRC, encoding='utf-8').read()

for k, v in {'✅': '[OK]', '❌': '[失败]', '⚠️': '[注意]', '→': '->', '←': '<-', '·': '-'}.items():
    t = t.replace(k, v)

t = re.sub(r'^#{1,6}\s*', '', t, flags=re.M)
t = t.replace('**', '')
t = t.replace('```', '')
t = t.replace('`', '')
t = re.sub(r'^\|[\s\-:|]+\|$', '', t, flags=re.M)
t = t.replace('\r\n', '\n').replace('\n', '\r\n')

io.open(DST, 'wb').write(t.encode('gbk', errors='replace'))
print('txt 写出 %d 字符' % len(t))
