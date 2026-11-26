# -*- coding: utf-8 -*-
"""Log the string that zu06 keeps at its global buffer (base+0xB1D14)."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if '_zu06_pathlog' in s:
    print('already patched')
    raise SystemExit(0)

ANCHOR = '    if (GetFileAttributesA("_zu06_flag.txt") != INVALID_FILE_ATTRIBUTES) {'
ADD = r'''    if (GetFileAttributesA("_zu06_pathlog.txt") != INVALID_FILE_ATTRIBUTES) {
        static int logged;
        if (!logged) {
            const char *sp = (const char *)((char *)m + 0xB1D14);
            logged = 1;
            note("zu06 pathbuf @B1D14: '%s'", sp);
        }
    }
''' + ANCHOR
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, ADD, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
