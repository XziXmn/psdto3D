# -*- coding: utf-8 -*-
"""修正 zu06 的 CreateFileA IAT 偏移：0xB421C / 0xB43F8（原来用的是 0x903D8，错的）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if '0xB421C' in s:
    print('already fixed')
    raise SystemExit(0)

OLD = '''        patch_slot((void *)m, 0x903D8, (void *)e_cfa_guard, (void **)&dummy);'''
NEW = '''        patch_slot((void *)m, 0xB421C, (void *)e_cfa_guard, (void **)&dummy);
        patch_slot((void *)m, 0xB43F8, (void *)e_cfa_guard, (void **)&dummy);'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
