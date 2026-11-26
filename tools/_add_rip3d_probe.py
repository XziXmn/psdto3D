# -*- coding: utf-8 -*-
"""给 rip3d.dll 的 CreateFileA 挂日志钩子，看 PSD 到底是谁打开的。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'RIP3D CFA' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static HANDLE WINAPI e_cfa_probe(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                 DWORD disp, DWORD flags, HANDLE tmpl)
{
    if (name) {
        int l = lstrlenA(name);
        if (l > 4 && lstrcmpiA(name + l - 4, ".psd") == 0)
            note("RIP3D CFA: %s", name);
    }
    return o_cfa(name, acc, share, sa, disp, flags, tmpl);
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        for (i = 0; names[i]; i++) {
            if (!seen[i]) {
                HMODULE m = GetModuleHandleA(names[i]);'''
NEW = '''        if (GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
            static int rip3d_hooked;
            HMODULE hr = GetModuleHandleA("rip3d.dll");
            if (hr && !rip3d_hooked) {
                PF_CreateFileA dummy2 = 0;
                rip3d_hooked = 1;
                patch_slot(hr, 0x15264, (void *)e_cfa_probe, (void **)&dummy2);
                note("RIP3D CFA hooked");
            }
        }
        for (i = 0; names[i]; i++) {
            if (!seen[i]) {
                HMODULE m = GetModuleHandleA(names[i]);'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
