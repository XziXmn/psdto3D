# -*- coding: utf-8 -*-
"""修字节序表达式里的运算符优先级错误：(d & 0xFF) << 24 —— 原来写成 d & 0xFF << 24。"""
import io
import re

P = r'\C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'.replace('\\C:', r'C:')
s = io.open(P, encoding='utf-8', errors='replace').read()

BAD = '((d&0xFF)<<24)|((d>>8&0xFF)<<16)|((d>>16&0xFF)<<8)|(d>>24&0xFF)'
GOOD = '(((d) & 0xFF) << 24) | (((d) >> 8 & 0xFF) << 16) | (((d) >> 16 & 0xFF) << 8) | ((d) >> 24 & 0xFF)'

# 统一替换两种书写（带空格/不带空格）
patterns = [
    r'\(d & 0xFF\) << 24 \| \(d >> 8 & 0xFF\) << 16 \| \(d >> 16 & 0xFF\) << 8 \| \(d >> 24 & 0xFF\)',
    r'\(d&0xFF\)<<24\|\(d>>8&0xFF\)<<16\|\(d>>16&0xFF\)<<8\|\(d>>24&0xFF\)',
]
n = 0
for pat in patterns:
    s, k = re.subn(pat, GOOD, s)
    n += k
io.open(P, 'w', encoding='utf-8').write(s)
print('replaced', n)
