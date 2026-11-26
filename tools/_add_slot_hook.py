# -*- coding: utf-8 -*-
"""Patch the exe's writepsd pointer slot directly (RVA 0x123278) instead of GetProcAddress."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'RVA_WRITEPSD_PTR' in s:
    print('already patched')
    raise SystemExit(0)

s = s.replace('#define RVA_GETPROCADDR     0x124260',
              '#define RVA_WRITEPSD_PTR    0x123278\r\n#define RVA_GETPROCADDR     0x124260', 1)

# 在 load_watch 线程里持续把该槽位指向我们的实现
OLD = '''    for (;;) {
        for (i = 0; names[i]; i++) {'''
NEW = '''    for (;;) {
        if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
            HMODULE he = GetModuleHandleA(0);
            if (he) {
                void **slot = (void **)((char *)he + 0x123278);
                if ((void *)slot != (void *)writepsd_shim) {
                    DWORD oldp;
                    if (VirtualProtect(slot, 4, PAGE_READWRITE, &oldp)) {
                        if (writepsd_slot_hooked != (int)(unsigned long)*slot) {
                            writepsd_slot_hooked = (int)(unsigned long)*slot;
                            note("NATIVE writepsd slot -> shim (was %08lX)", (unsigned long)*slot);
                        }
                        *slot = (void *)writepsd_shim;
                        VirtualProtect(slot, 4, oldp, &oldp);
                    }
                }
            }
        }
        for (i = 0; names[i]; i++) {'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)

s = s.replace('static DWORD WINAPI load_watch(LPVOID p)',
              'static int writepsd_slot_hooked;\r\nstatic DWORD WINAPI load_watch(LPVOID p)', 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
