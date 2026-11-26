# -*- coding: utf-8 -*-
"""Patch the call site itself: 0x50B17D `call [0x523278]` -> `call writepsd_shim`."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'RVA_WRITEPSD_CALL' in s:
    print('already patched')
    raise SystemExit(0)

s = s.replace('#define RVA_WRITEPSD_PTR    0x123278',
              '#define RVA_WRITEPSD_PTR    0x123278\r\n#define RVA_WRITEPSD_CALL   0x10B17D', 1)

ANCHOR = '    note("EMU GetProcAddress hooked (writepsd replace ready)");'
ADD = ANCHOR + r'''
    if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
        unsigned char *cs = (unsigned char *)((char *)base + RVA_WRITEPSD_CALL);
        DWORD oldp;
        if (cs[0] == 0xFF && cs[1] == 0x15) {          /* call [0x523278] */
            long rel = (long)((char *)writepsd_shim - (char *)(cs + 5));
            if (VirtualProtect(cs, 6, PAGE_EXECUTE_READWRITE, &oldp)) {
                cs[0] = 0xE8;
                *(long *)(cs + 1) = rel;
                cs[5] = 0x90;
                VirtualProtect(cs, 6, oldp, &oldp);
                FlushInstructionCache(GetCurrentProcess(), cs, 6);
                note("NATIVE writepsd call patched at %p -> %p (rel=%ld)", cs, (void *)writepsd_shim, rel);
            }
        } else {
            note("NATIVE writepsd call site unexpected: %02X %02X", cs[0], cs[1]);
        }
    }'''
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, ADD, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
