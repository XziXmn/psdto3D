# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
bad = 'lstrncmpA(lines[2], "39550", 5)'
good = 'strncmp(lines[2], "39550", 5)'
if bad in s:
    s = s.replace(bad, good, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed')
else:
    print('pattern not found; already fixed?')
