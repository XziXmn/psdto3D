# -*- coding: utf-8 -*-
"""Gate the zu06 software breakpoints behind a marker file (they can wedge the export)."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if '_zu06_sbp.txt' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    sbp_arm(g_zu06_base + 0xA4504);   /* writepsd entry: log args + call count */
    sbp_arm(g_zu06_base + 0xA4800);   /* just before the first PSD stream write */
    sbp_arm(g_zu06_base + 0xA497D);   /* per-layer loop head */'''
NEW = '''    if (GetFileAttributesA("_zu06_sbp.txt") != INVALID_FILE_ATTRIBUTES) {
        sbp_arm(g_zu06_base + 0xA4504);   /* writepsd entry: log args + call count */
        sbp_arm(g_zu06_base + 0xA4800);   /* just before the first PSD stream write */
        sbp_arm(g_zu06_base + 0xA497D);   /* per-layer loop head */
    }'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
