# -*- coding: utf-8 -*-
"""加 ini 开关 log=0/1（默认 1）。log=0 时完全不写 _dongle.log。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cfg_log_on' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''static void note(const char *fmt, ...)
{
    FILE *f = LF();'''
NEW = '''static int cfg_log_on(void)
{
    static int v = -1;
    if (v < 0) v = cfg_val("log", 1);
    return v;
}

static void note(const char *fmt, ...)
{
    FILE *f;
    if (!cfg_log_on()) return;
    f = LF();'''
assert OLD in s
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
