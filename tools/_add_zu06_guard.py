# -*- coding: utf-8 -*-
"""把层数保护挂到 zu06.dll 的 CreateFileA 上（PSD 是它打开的，exe 的 IAT 看不到）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'e_cfa_guard' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static HANDLE WINAPI e_cfa_guard(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                 DWORD disp, DWORD flags, HANDLE tmpl)
{
    if (name) {
        int len = lstrlenA(name);
        if (len > 4 && lstrcmpiA(name + len - 4, ".psd") == 0 &&
            GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
            int layers = 0;
            if (psd_count_layers(name, &layers) && layers > 40) {
                char msg[512];
                wsprintfA(msg,
                    "这个 PSD 有 %d 个图层，而程序的导入器最多只支持 40 层。\r\n\r\n"
                    "继续导入会直接崩溃。请在 Photoshop 里合并部分图层，\r\n"
                    "把图层数降到 40 以内再导入。", layers);
                note("PSD guard: %s 有 %d 层 > 40，已拦截", name, layers);
                MessageBoxA(0, msg, "图层数超出程序上限", MB_OK | MB_ICONWARNING);
                SetLastError(5);
                return INVALID_HANDLE_VALUE;
            }
        }
    }
    return o_cfa(name, acc, share, sa, disp, flags, tmpl);
}
'''

ANCHOR = 'static void patch_zu06(HMODULE m)'
assert ANCHOR in s, 'patch_zu06 anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 在 patch_zu06 里加钩子（沿用已有的 _zu06_patch_iat 开关）
OLD = '    if (GetFileAttributesA("_zu06_patch_iat.txt") != INVALID_FILE_ATTRIBUTES) {'
NEW = '''    if (GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
        PF_CreateFileA dummy = 0;
        patch_slot((void *)m, 0x903D8, (void *)e_cfa_guard, (void **)&dummy);
        note("PSD guard: zu06 CreateFileA 已挂钩");
    }
    if (GetFileAttributesA("_zu06_patch_iat.txt") != INVALID_FILE_ATTRIBUTES) {'''
assert OLD in s, 'zu06 iat anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
