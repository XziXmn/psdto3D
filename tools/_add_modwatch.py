# -*- coding: utf-8 -*-
"""Insert a module-load watcher into dongle_emu.c (idempotent)."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

if 'load_watch' in s:
    print('already patched')
    raise SystemExit(0)

NEW_FUNC = r'''static DWORD WINAPI load_watch(LPVOID p)
{
    static const char *names[] = {"ok3d.dll","ok3d1.dll","ok3d4.dll","zu6.dll","zu06.dll","zu61.dll",
                                  "my32.dll","dspr.dll","save3d.dll","8602.dll","rip3d.dll","cmyktiff2_real.dll", NULL};
    unsigned char seen[16]; int i;
    (void)p;
    memset(seen, 0, sizeof(seen));
    for (;;) {
        for (i = 0; names[i]; i++) {
            if (!seen[i]) {
                HMODULE m = GetModuleHandleA(names[i]);
                if (m) {
                    if (GetFileAttributesA("_modload.txt") != INVALID_FILE_ATTRIBUTES)
                        note("MODLOAD %s base=%08lX", names[i], (unsigned long)m);
                    seen[i] = 1;
                }
            }
        }
        Sleep(120);
    }
    return 0;
}

static DWORD WINAPI mod_watch(LPVOID p)'''

s = s.replace('static DWORD WINAPI mod_watch(LPVOID p)', NEW_FUNC, 1)
s = s.replace('CreateThread(NULL, 0, zu06_watch, NULL, 0, NULL);',
              'CreateThread(NULL, 0, zu06_watch, NULL, 0, NULL);\r\n        CreateThread(NULL, 0, load_watch, NULL, 0, NULL);', 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
