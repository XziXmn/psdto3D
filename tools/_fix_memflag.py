# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
bad = 'MEM_COMMIT | MEM_EXECUTE_READWRITE, PAGE_EXECUTE_READWRITE'
good = 'MEM_COMMIT, PAGE_EXECUTE_READWRITE'
if bad in s:
    s = s.replace(bad, good, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed')
else:
    print('pattern not found')
