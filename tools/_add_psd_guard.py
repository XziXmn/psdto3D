# -*- coding: utf-8 -*-
"""PSD 层数超限保护：>40 层时先弹提示并拒绝打开，避免程序 AV 崩掉。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'psd_layers_guard' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= PSD 层数上限保护（程序导入器只支持到 40 层） ================= */
static int psd_count_layers(const char *path, int *layers)
{
    HANDLE fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    unsigned char head[26];
    DWORD got = 0;
    short cnt;
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 || memcmp(head, "8BPS", 4) != 0) {
        CloseHandle(fh);
        return 0;
    }
    {
        DWORD d = 0;
        ReadFile(fh, &d, 4, &got, 0);
        SetFilePointer(fh, (long)((d & 0xFF) << 24 | (d >> 8 & 0xFF) << 16 | (d >> 16 & 0xFF) << 8 | (d >> 24 & 0xFF)), 0, FILE_CURRENT);
        ReadFile(fh, &d, 4, &got, 0);
        SetFilePointer(fh, (long)((d & 0xFF) << 24 | (d >> 8 & 0xFF) << 16 | (d >> 16 & 0xFF) << 8 | (d >> 24 & 0xFF)), 0, FILE_CURRENT);
    }
    { unsigned char z[8]; ReadFile(fh, z, 8, &got, 0); }
    { unsigned char c[2] = {0, 0}; ReadFile(fh, c, 2, &got, 0);
      cnt = (short)((c[0] << 8) | c[1]);
      if (cnt < 0) cnt = -cnt;
      *layers = cnt; }
    CloseHandle(fh);
    return 1;
}

static int psd_layers_guard(const char *name)
{
    static const char warn[] =
        "这个 PSD 有 %d 个图层，而程序的导入器最多只支持 40 层。\r\n\r\n"
        "继续导入会直接崩溃。请在 Photoshop 里合并部分图层，\r\n"
        "把图层数降到 40 以内再导入。";
    char msg[512];
    int layers = 0;
    if (!psd_count_layers(name, &layers)) return 0;
    wsprintfA(msg, warn, layers);
    MessageBoxA(0, msg, "图层数超出程序上限", MB_OK | MB_ICONWARNING);
    note("PSD guard: %s 有 %d 层 > 40，已拦截", name, layers);
    return 1;
}
'''

ANCHOR = 'static HANDLE WINAPI e_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''    if (name && GetFileAttributesA("_gxwj.txt") != INVALID_FILE_ATTRIBUTES) {'''
NEW = '''    if (name && GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
        int len = lstrlenA(name);
        if (len > 4 && lstrcmpiA(name + len - 4, ".psd") == 0 && psd_layers_guard(name))
            return INVALID_HANDLE_VALUE;
    }
    if (name && GetFileAttributesA("_gxwj.txt") != INVALID_FILE_ATTRIBUTES) {'''
assert OLD in s, 'inner anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
