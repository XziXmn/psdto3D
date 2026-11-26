# -*- coding: utf-8 -*-
"""Replace the naked-asm trampoline with a regparm(3) C function (Delphi register ABI)."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

start = s.find('__attribute__((naked)) static void writepsd_shim(void)')
end = s.find('static void * WINAPI e_gpa(HMODULE mod, LPCSTR name)')
assert start > 0 and end > start, 'block not found'

NEW = r'''__attribute__((regparm(3))) int writepsd_shim(const char *file, const char *dir, void *p3,
                                        int a4, int a5, int a6, int a7,
                                        int layers, int w, int h, int spp, int a12, int a13)
{
    return writepsd_c(file, dir, p3, a4, a5, a6, a7, layers, w, h, spp, a12, a13);
}

'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('ok')
