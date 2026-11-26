# -*- coding: utf-8 -*-
"""修：给多段字面量补上开头的引号。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

old = '''    wsprintfA(msg,
        \\xD5'''
if old in s:
    s = s.replace('''    wsprintfA(msg,
        \\xD5''', '''    wsprintfA(msg,
        "\\xD5''', 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed opening quote')
else:
    i = s.find('wsprintfA(msg,')
    print('context:', repr(s[i:i + 120]))
