# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
bad = '''    SetFilePointer(fh, 4, 0, FILE_CURRENT);
    { DWORD d = 0; ReadFile(fh, &d, 4, &got, 0);'''
good = '''    { DWORD d = 0; ReadFile(fh, &d, 4, &got, 0);'''
if bad in s:
    s = s.replace(bad, good, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed header offset')
else:
    print('pattern not found')
