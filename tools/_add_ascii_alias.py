# -*- coding: utf-8 -*-
"""中文/非 ASCII 路径兼容：程序读不动多字节路径（实测会报 Invalid floating point operation）。
做法：在 ok3dtemp 里建一个 ASCII 别名的硬链接（失败则复制），把对话框返回的路径换成它。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'ascii_alias' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 非 ASCII 路径兼容 ================= */
static int has_non_ascii(const char *s)
{
    if (!s) return 0;
    for (; *s; s++) if ((unsigned char)*s >= 0x80) return 1;
    return 0;
}

static int ascii_alias(const char *src, char *out, int outsz)
{
    static int seq;
    char dir[MAX_PATH], name[64];
    const char *base = src, *q = src, *dot = 0;
    unsigned long hash = 2166136261UL;
    if (!has_non_ascii(src)) return 0;
    if (!psd_find_tempdir(dir)) {
        GetTempPathA(MAX_PATH, dir);
    }
    while (*q) { if (*q == '\\' || *q == '/') base = q + 1; q++; }
    for (q = base; *q; q++) {
        if (*q == '.') dot = q;
        hash = (hash ^ (unsigned char)*q) * 16777619UL;
    }
    lstrcpynA(name, "ok3d_ascii_", 40);
    wsprintfA(name + lstrlenA(name), "%08lX", hash);
    if (dot) lstrcatA(name, dot);
    lstrcpynA(out, dir, outsz - 64);
    lstrcatA(out, name);

    if (GetFileAttributesA(out) != INVALID_FILE_ATTRIBUTES) DeleteFileA(out);
    if (!CreateHardLinkA(out, src, 0)) {
        if (!CopyFileA(src, out, FALSE)) {
            note("ascii_alias: 建立别名失败 %s", src);
            return 0;
        }
        note("ascii_alias: 复制 -> %s", out);
    } else {
        note("ascii_alias: 硬链接 -> %s", out);
    }
    return 1;
}
'''

ANCHOR = 'static BOOL WINAPI e_gofna(void *p)'
if ANCHOR not in s:
    ANCHOR = 'static BOOL WINAPI e_gofna(LPVOID p)'
assert ANCHOR in s, 'gofna anchor'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 队列分支：填充 file 后做别名替换
OLD1 = '''        if (file && maxfile) lstrcpynA(file, g_opens[g_iopen], maxfile);'''
NEW1 = '''        if (file && maxfile) lstrcpynA(file, g_opens[g_iopen], maxfile);
        if (file && maxfile && ascii_alias(g_opens[g_iopen], file, (int)maxfile)) {
            note("ascii_alias: 队列路径换成 %s", file);
        }'''
assert OLD1 in s
s = s.replace(OLD1, NEW1, 1)

# 真实对话框分支：返回 TRUE 后再替换
OLD2 = '''        BOOL ok = ((BOOL (WINAPI *)(void *))o_gofna)(p);
        if (ok && file && psd_guard_dialog(file)) return FALSE;
        return ok;'''
NEW2 = '''        BOOL ok = ((BOOL (WINAPI *)(void *))o_gofna)(p);
        if (ok && file && psd_guard_dialog(file)) return FALSE;
        if (ok && file && maxfile && has_non_ascii(file)) {
            char alias[MAX_PATH];
            if (ascii_alias(file, alias, MAX_PATH))
                lstrcpynA(file, alias, maxfile);
        }
        return ok;'''
assert OLD2 in s
s = s.replace(OLD2, NEW2, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
