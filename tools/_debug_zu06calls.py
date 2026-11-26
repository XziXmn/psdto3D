# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'ZU06 CFA CALL' in s:
    print('already there')
    raise SystemExit(0)

OLD = '''static HANDLE WINAPI e_cfa_guard(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                 DWORD disp, DWORD flags, HANDLE tmpl)
{
    if (name) {'''
NEW = '''static int g_zu06_cfa_seen;

static HANDLE WINAPI e_cfa_guard(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                 DWORD disp, DWORD flags, HANDLE tmpl)
{
    if (g_zu06_cfa_seen < 40) {
        g_zu06_cfa_seen++;
        note("ZU06 CFA CALL: %s", name ? name : "(null)");
    }
    if (name) {'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
