# -*- coding: utf-8 -*-
"""Native Chinese: set the app's language flag and invoke its own re-apply routine."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cn_native_apply' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 原生中文：调用程序自己的语言应用例程 ================= */
typedef void (__attribute__((regparm(3))) *PF_APPLYLANG)(void *self);

static int cn_native_apply(HWND form)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned char *flag;
    PF_APPLYLANG fn;
    DWORD oldp;
    if (!he || !form) return 0;
    flag = (unsigned char *)((char *)he + 0x1230C9);      /* DAT_005230c9 */
    fn = (PF_APPLYLANG)((char *)he + 0x10CCF8);           /* FUN_0050ccf8 */
    if (!VirtualProtect(flag, 1, PAGE_READWRITE, &oldp)) return 0;
    if (*flag != 1) {
        note("CN native: flag %d -> 1, 调用 0050CCF8", *flag);
        *flag = 1;
        VirtualProtect(flag, 1, oldp, &oldp);
        fn((void *)form);
        return 1;
    }
    VirtualProtect(flag, 1, oldp, &oldp);
    return 0;
}
'''

ANCHOR = 'static DWORD WINAPI cn_ui_thread(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        HWND w = FindWindowA("TForm1", NULL);
        if (w) {
            HMENU h = GetMenu(w);'''
NEW = '''        HWND w = FindWindowA("TForm1", NULL);
        if (w) {
            HMENU h;
            if (GetFileAttributesA("_cn_native.txt") != INVALID_FILE_ATTRIBUTES)
                cn_native_apply(w);
            h = GetMenu(w);'''
assert OLD in s, 'inner anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
