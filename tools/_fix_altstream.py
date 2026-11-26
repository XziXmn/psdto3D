# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
bad = '''            if (GetFileAttributesA(cand) != INVALID_FILE_ALTERNATE_STREAM) {
                if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) { lstrcpynA(out, cand, MAX_PATH); return 1; }
            }'''
good = '''            if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) { lstrcpynA(out, cand, MAX_PATH); return 1; }'''
if bad in s:
    s = s.replace(bad, good, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fixed')
else:
    print('pattern not found')
