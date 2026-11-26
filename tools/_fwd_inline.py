# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'inline_cfa_install(void);' in s:
    print('already there')
    raise SystemExit(0)

OLD = 'static int writepsd_slot_hooked;'
NEW = '''static int writepsd_slot_hooked;
static void inline_cfa_install(void);
static HANDLE WINAPI e_cfa_inline(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
