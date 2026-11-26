# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

START = '            void *fr[8];'
END = '            note("GATE[%s] open %s", who, name);'
i = s.find(START)
j = s.find(END)
if i < 0 or j < 0:
    raise SystemExit('anchor missing %d %d' % (i, j))

NEW = r'''            void *ret = __builtin_return_address(0);
            const char *b = "?";
            char path[MAX_PATH];
            HMODULE hm = NULL;
            if (GetModuleHandleExA(0x6, (LPCSTR)ret, &hm) && hm &&
                GetModuleFileNameA(hm, path, MAX_PATH)) {
                const char *q = path;
                b = path;
                while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
            }
            note("GATE[%s+%X] open %s", b, (unsigned)((char *)ret - (char *)hm), name);'''

s = s[:i] + NEW + s[j + len(END):]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
