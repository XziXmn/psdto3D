# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'confirm_found' in s:
    print('already')
    raise SystemExit(0)

s = s.replace('static void localize_dialogs(void)\n{\n    int mi;',
              'static void localize_dialogs(void)\n{\n    int mi; int confirm_found = 0;', 1)
s = s.replace('            note("cn_dialogs: 已把 Confirm/continue? 改为中文");\n            break;',
              '            note("cn_dialogs: 已把 Confirm/continue? 改为中文");\n            confirm_found = 1;\n            break;', 1)
s = s.replace('    note("cn_dialogs: 没找到 Confirm/continue? 字符串");',
              '    if (!confirm_found) note("cn_dialogs: 没找到 Confirm/continue? 字符串");', 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('ok')
