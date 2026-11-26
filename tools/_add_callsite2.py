# -*- coding: utf-8 -*-
"""Do the writepsd call-site patch inside load_watch (a thread that actually runs)."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'writepsd_callsite_done' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''        if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
            HMODULE he = GetModuleHandleA(0);'''
NEW = '''        if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
            static int writepsd_callsite_done;
            HMODULE he = GetModuleHandleA(0);
            if (!writepsd_callsite_done && he) {
                unsigned char *cs = (unsigned char *)((char *)he + 0x10B17D);
                DWORD oldp2;
                if (cs[0] == 0xFF && cs[1] == 0x15 &&
                    VirtualProtect(cs, 6, PAGE_EXECUTE_READWRITE, &oldp2)) {
                    long rel = (long)((char *)writepsd_shim - (char *)(cs + 5));
                    cs[0] = 0xE8;
                    *(long *)(cs + 1) = rel;
                    cs[5] = 0x90;
                    VirtualProtect(cs, 6, oldp2, &oldp2);
                    FlushInstructionCache(GetCurrentProcess(), cs, 6);
                    note("NATIVE callsite patched %p -> %p rel=%ld", cs, (void *)writepsd_shim, rel);
                } else {
                    note("NATIVE callsite bytes: %02X %02X", cs[0], cs[1]);
                }
                writepsd_callsite_done = 1;
            }'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
