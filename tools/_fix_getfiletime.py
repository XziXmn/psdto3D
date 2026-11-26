# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
bad = '''            tm = GetFileTime(src2, 0, 0) ? 0 : 0;
            {
                FILETIME ft;
                if (GetFileTime(src2, 0, 0, &ft)) tm = ft.dwLowDateTime;
            }'''
good = '''            {
                FILETIME ft;
                if (GetFileTime(src2, 0, 0, &ft)) tm = ft.dwLowDateTime;
            }'''
if bad in s:
    s = s.replace(bad, good, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed')
else:
    print('pattern not found')
