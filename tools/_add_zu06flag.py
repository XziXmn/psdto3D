# -*- coding: utf-8 -*-
"""Insert an experimental switch that flips zu06's DAT_004ab0a0 flag."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if '_zu06_flag.txt' in s:
    print('already patched')
    raise SystemExit(0)

ANCHOR = '    sbp_arm(g_zu06_base + 0xA497D);   /* per-layer loop head */'
ADD = ANCHOR + r'''
    if (GetFileAttributesA("_zu06_flag.txt") != INVALID_FILE_ATTRIBUTES) {
        int *flag = (int *)((char *)m + 0xAB0A0);   /* DAT_004ab0a0 */
        DWORD oldp;
        if (VirtualProtect(flag, 4, PAGE_READWRITE, &oldp)) {
            note("zu06 flag 4AB0A0: %d -> 1", *flag);
            *flag = 1;
            VirtualProtect(flag, 4, oldp, &oldp);
        }
    }'''
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, ADD, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
