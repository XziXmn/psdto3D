# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'static void log_preview_probe(void);' in s:
    print('already there')
    raise SystemExit(0)
OLD = 'static int g_zu06_patched;'
NEW = 'static int g_zu06_patched;\r\nstatic void log_preview_probe(void);'
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
