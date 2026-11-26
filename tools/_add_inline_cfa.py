# -*- coding: utf-8 -*-
"""内联 hook kernel32!CreateFileA：进程内所有模块的文件打开都经过我们（用于层数保护/归因）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'inline_cfa' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 内联 hook CreateFileA（覆盖所有模块） ================= */
static void *g_cfa_tramp;
static int g_inline_cfa_ok;
static int g_inline_cfa_seen;

static void inline_cfa_install(void)
{
    FARPROC orig = GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateFileA");
    unsigned char *p = (unsigned char *)orig;
    unsigned char *t;
    DWORD oldp;
    long rel;
    if (!orig || g_inline_cfa_ok) return;
    g_cfa_tramp = VirtualAlloc(0, 64, MEM_COMMIT | MEM_EXECUTE_READWRITE, PAGE_EXECUTE_READWRITE);
    if (!g_cfa_tramp) return;
    t = (unsigned char *)g_cfa_tramp;
    memcpy(t, p, 5);                                   /* 原前 5 字节（push ebp / mov ebp,esp 等） */
    t[5] = 0xE9;
    rel = (long)((p + 5) - (t + 10));
    *(long *)(t + 6) = rel;
    if (!VirtualProtect(p, 8, PAGE_EXECUTE_READWRITE, &oldp)) return;
    rel = (long)((unsigned char *)e_cfa_inline - (p + 5));
    p[0] = 0xE9;
    *(long *)(p + 1) = rel;
    VirtualProtect(p, 8, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), p, 8);
    g_inline_cfa_ok = 1;
    note("INLINE CFA: 已挂钩 kernel32!CreateFileA -> %p, tramp=%p", (void *)e_cfa_inline, g_cfa_tramp);
}

static HANDLE WINAPI e_cfa_inline(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                  DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE (WINAPI *real)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
    real = (HANDLE (WINAPI *)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE))g_cfa_tramp;
    if (name && g_inline_cfa_seen < 60) {
        int l = lstrlenA(name);
        if (l > 4 && lstrcmpiA(name + l - 4, ".psd") == 0) {
            g_inline_cfa_seen++;
            note("INLINE CFA: %s", name);
        }
    }
    if (name && GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
        int l = lstrlenA(name);
        if (l > 4 && lstrcmpiA(name + l - 4, ".psd") == 0 && psd_layers_guard(name)) {
            SetLastError(5);
            return INVALID_HANDLE_VALUE;
        }
    }
    return real(name, acc, share, sa, disp, flags, tmpl);
}
'''

ANCHOR = 'static HANDLE WINAPI e_cfa_guard(LPCSTR name'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_fix_cancel.txt") != INVALID_FILE_ATTRIBUTES) {'''
NEW = '''        if (GetFileAttributesA("_inline_cfa.txt") != INVALID_FILE_ATTRIBUTES)
            inline_cfa_install();
        if (GetFileAttributesA("_fix_cancel.txt") != INVALID_FILE_ATTRIBUTES) {'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
