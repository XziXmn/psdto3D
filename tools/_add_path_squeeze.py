# -*- coding: utf-8 -*-
"""路径规范化：把连续的 \\ 合并成单个（避免生成带双反斜杠的工程路径）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'path_squeeze' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* 把 a\\b\\\\c 这类重复分隔符压成一个 */
static void path_squeeze(const char *in, char *out, int outsz)
{
    int i = 0;
    int last_sep = 0;
    if (!in || !out || outsz <= 1) return;
    while (*in && i < outsz - 1) {
        if (*in == '\\' || *in == '/') {
            if (!last_sep) { out[i++] = '\\'; last_sep = 1; }
        } else {
            out[i++] = *in;
            last_sep = 0;
        }
        in++;
    }
    out[i] = 0;
}
'''

ANCHOR = 'static int gxwj_convert(const char *src, char *out, int outsz)'
assert ANCHOR in s
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 在写 psdpath 前做规范化
OLD = '''    #define WLINE(p) WriteFile(of, (p), lstrlenA(p), &got, 0); WriteFile(of, "\\r\\n", 2, &got, 0)
    WLINE(psdpath);                       /* 0 路径 */'''
NEW = '''    { char squeezed[MAX_PATH]; path_squeeze(psdpath, squeezed, MAX_PATH); lstrcpynA(psdpath, squeezed, MAX_PATH); }
    #define WLINE(p) WriteFile(of, (p), lstrlenA(p), &got, 0); WriteFile(of, "\\r\\n", 2, &got, 0)
    WLINE(psdpath);                       /* 0 路径 */'''
assert OLD in s
s = s.replace(OLD, NEW, 1)

# gxwj_convert 入口也规范化 src（用于计算目录）
OLD2 = '''    HANDLE fh = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    DWORD size, got = 0;'''
NEW2 = '''    HANDLE fh;
    DWORD size, got = 0;'''
assert OLD2 in s
s = s.replace(OLD2, NEW2, 1)
OLD3 = '''    if (fh == INVALID_HANDLE_VALUE) return 0;
    size = GetFileSize(fh, 0);
    if (size == 0 || size > 8 * 1024 * 1024) { CloseHandle(fh); return 0; }'''
NEW3 = '''    { char sq[MAX_PATH]; path_squeeze(src, sq, MAX_PATH); lstrcpynA((char *)src, sq, MAX_PATH); }
    fh = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) return 0;
    size = GetFileSize(fh, 0);
    if (size == 0 || size > 8 * 1024 * 1024) { CloseHandle(fh); return 0; }'''
assert OLD3 in s
s = s.replace(OLD3, NEW3, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
