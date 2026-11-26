# -*- coding: utf-8 -*-
"""Add GetProcAddress IAT hooks (both slots) so writepsd can be replaced."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'RVA_GETPROCADDR' in s:
    print('already patched')
    raise SystemExit(0)

s = s.replace('#define RVA_SETUP_DESTROY   0x124A54',
              '#define RVA_SETUP_DESTROY   0x124A54\r\n#define RVA_GETPROCADDR     0x124260\r\n#define RVA_GETPROCADDR2    0x124418', 1)

s = s.replace('static PF_CreateFileA     o_cfa;',
              'static PF_CreateFileA     o_cfa;\r\nstatic void * (WINAPI *o_gpa)(HMODULE, LPCSTR);', 1)

ANCHOR = '    patch_slot(base, RVA_SETUP_DESTROY,   (void *)e_sddil,  (void **)&o_sddil);'
ADD = ANCHOR + '\r\n    patch_slot(base, RVA_GETPROCADDR,  (void *)e_gpa, (void **)&o_gpa);' \
             + '\r\n    patch_slot(base, RVA_GETPROCADDR2, (void *)e_gpa, (void **)&o_gpa);' \
             + '\r\n    note("EMU GetProcAddress hooked (writepsd replace ready)");'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, ADD, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
