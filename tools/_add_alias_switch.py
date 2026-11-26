# -*- coding: utf-8 -*-
"""加 ini 开关 ascii_alias=1/0（默认 1）：关闭后不做 ASCII 别名替换，便于定位/兼容。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cfg_alias_on' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''static int ascii_alias(const char *src, char *out, int outsz)
{'''
NEW = '''static int ascii_alias(const char *src, char *out, int outsz)
{
    if (!cfg_val("ascii_alias", 1)) return 0;'''
assert OLD in s
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
