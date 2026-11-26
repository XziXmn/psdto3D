# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
old = '            note("cn_dialogs: \u5df2\u628a Confirm/continue? \u6539\u4e3a\u4e2d\u6587");\n            return;'
new = '            note("cn_dialogs: \u5df2\u628a Confirm/continue? \u6539\u4e3a\u4e2d\u6587");\n            break;'
if old in s:
    s = s.replace(old, new, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed: return -> break')
else:
    print('pattern not found')
