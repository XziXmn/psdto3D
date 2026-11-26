# -*- coding: utf-8 -*-
"""把 cfg_on/cfg_val 的声明移到文件前部（第一个 #define 之前）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'static int cfg_on(const char *key, int def, const char *marker);' in s:
    print('already there')
    raise SystemExit(0)

anchor = 'static void log_preview_probe(void);'
assert anchor in s, 'anchor missing'
decl = anchor + '\nstatic int cfg_on(const char *key, int def, const char *marker);\nstatic int cfg_val(const char *key, int def);'
s = s.replace(anchor, decl, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
