# -*- coding: utf-8 -*-
"""99 工程(.gxwj)转换时，PSD 找不到就多试几种：
1) 工程同目录 + 原文件名；
2) 工程同目录里唯一的一个 .psd；
3) 去掉 " -1"/" -2"/" (2)" 这类后缀再找；
4) 同目录里名字前缀匹配的那个 .psd。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'gxwj_find_psd' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* 在工程目录里尽量把 PSD 找出来 */
static int gxwj_find_psd(const char *prjdir, const char *orig, char *out)
{
    char cand[MAX_PATH], base[MAX_PATH];
    const char *b = orig, *q = orig, *dot = 0;
    WIN32_FIND_DATAA fd;
    HANDLE hs;
    int n = 0;
    char only[MAX_PATH];

    while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
    lstrcpynA(base, b, MAX_PATH);
    for (q = base; *q; q++) if (*q == '.') dot = q;

    /* 1) 原名 */
    wsprintfA(cand, "%s%s", prjdir, base);
    if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) { lstrcpynA(out, cand, MAX_PATH); return 1; }

    /* 3) 去掉 " -1" / "-1" / " (2)" 之类的尾巴再试 */
    {
        char stem[MAX_PATH];
        int len;
        lstrcpynA(stem, base, MAX_PATH);
        if (dot) stem[(int)(dot - base)] = 0;
        len = lstrlenA(stem);
        while (len > 0 && (stem[len - 1] == ' ' || stem[len - 1] == '-' ||
                           (stem[len - 1] >= '0' && stem[len - 1] <= '9') ||
                           stem[len - 1] == ')' || stem[len - 1] == '(')) {
            if (stem[len - 1] == ' ') { len--; continue; }
            if (stem[len - 1] >= '0' && stem[len - 1] <= '9') { len--; continue; }
            if (stem[len - 1] == '-' || stem[len - 1] == '(' || stem[len - 1] == ')') { len--; continue; }
            break;
        }
        stem[len] = 0;
        if (len > 0) {
            wsprintfA(cand, "%s%s.psd", prjdir, stem);
            if (GetFileAttributesA(cand) != INVALID_FILE_ALTERNATE_STREAM) {
                if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) { lstrcpynA(out, cand, MAX_PATH); return 1; }
            }
            /* 4) 前缀匹配 */
            wsprintfA(cand, "%s%s*.psd", prjdir, stem);
            hs = FindFirstFileA(cand, &fd);
            if (hs != INVALID_HANDLE_VALUE) {
                int m = 0;
                char hit[MAX_PATH];
                do {
                    if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
                    m++;
                    wsprintfA(hit, "%s%s", prjdir, fd.cFileName);
                } while (FindNextFileA(hs, &fd));
                FindClose(hs);
                if (m == 1) { lstrcpynA(out, hit, MAX_PATH); return 1; }
            }
        }
    }

    /* 2) 目录里唯一的 .psd */
    wsprintfA(cand, "%s*.psd", prjdir);
    hs = FindFirstFileA(cand, &fd);
    if (hs != INVALID_HANDLE_VALUE) {
        do {
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            n++;
            wsprintfA(only, "%s%s", prjdir, fd.cFileName);
        } while (FindNextFileA(hs, &fd));
        FindClose(hs);
        if (n == 1) { lstrcpynA(out, only, MAX_PATH); return 1; }
    }
    return 0;
}
'''

ANCHOR = 'static int gxwj_convert(const char *src, char *out, int outsz)'
assert ANCHOR in s, 'anchor'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 替换原有的 PSD 定位逻辑（原样找 + 同目录同名）
OLD_START = s.find('    /* PSD 路径：先按原样找，找不到就在 gxwj 同目录找同名 .psd */')
OLD_END = s.find('    if (!gxwj_read_psd(psdpath, &w, &h, &layers)) {', OLD_START)
assert OLD_START > 0 and OLD_END > OLD_START, 'psdpath block'
NEW = '''    /* PSD 路径：原样 → 同目录多种猜测（gxwj_find_psd） */
    lstrcpynA(psdpath, lines[0], MAX_PATH);
    if (GetFileAttributesA(psdpath) == INVALID_FILE_ATTRIBUTES) {
        char pdir[MAX_PATH], hit[MAX_PATH];
        const char *q0 = src, *b0 = src;
        while (*q0) { if (*q0 == '\\\\' || *q0 == '/') b0 = q0 + 1; q0++; }
        lstrcpynA(pdir, src, (int)(b0 - src) + 1);
        if (gxwj_find_psd(pdir, lines[0], hit)) {
            note("GXWJ: PSD 自动定位 %s -> %s", lines[0], hit);
            lstrcpynA(psdpath, hit, MAX_PATH);
        }
    }
'''
s = s[:OLD_START] + NEW + s[OLD_END:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
