# -*- coding: utf-8 -*-
"""Rewrite the writepsd shim as a 10-arg cdecl wrapper that calls the real writer first,
then fills in the pixel data — i.e. the export becomes native from the app's viewpoint."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

start = s.find('int __cdecl writepsd_c(')
if start < 0:
    start = s.find('__attribute__((used)) int __cdecl writepsd_c(')
end = s.find('static void * WINAPI e_gpa(HMODULE mod, LPCSTR name)')
assert start > 0 and end > start, 'block not found'

NEW = r'''typedef int (__cdecl *PF_WRITEPSD)(const char *, const char *, int, int, int, int, int, int, int, int);
static PF_WRITEPSD o_writepsd;

int __cdecl writepsd_shim(const char *file, const char *dir,
                          int a3, int a4, int a5, int a6,
                          int layers, int w, int h, int spp)
{
    int r = 0;
    void **slot;
    (void)a3; (void)a4; (void)a5; (void)a6; (void)spp;

    slot = (void **)((char *)GetModuleHandleA(0) + 0x123278);
    if (!o_writepsd) o_writepsd = (PF_WRITEPSD)*slot;
    note("NATIVE writepsd: file=%s dir=%s layers=%d w=%d h=%d orig=%p", 
         file ? file : "(null)", dir ? dir : "(null)", layers, w, h, (void *)o_writepsd);

    if (o_writepsd && (void *)o_writepsd != (void *)writepsd_shim)
        r = o_writepsd(file, dir, a3, a4, a5, a6, layers, w, h, spp);

    if (file && dir && layers > 0 && layers <= 64 && w > 0 && h > 0)
        psd_assemble(file, dir, w, h, layers);

    return r;
}

'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('rewritten')
