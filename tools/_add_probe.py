# -*- coding: utf-8 -*-
"""Add a probe breakpoint at the writepsd call site (0x50B17D) to see if it is reached."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if '_native_probe.txt' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''        if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
            static int writepsd_callsite_done;'''
NEW = '''        if (GetFileAttributesA("_native_probe.txt") != INVALID_FILE_ATTRIBUTES) {
            static int probe_done;
            if (!probe_done) {
                probe_done = 1;
                sbp_arm(0x0050B17D);            /* writepsd 调用点 */
                note("PROBE armed at 0050B17D");
            }
        }
        if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
            static int writepsd_callsite_done;'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
