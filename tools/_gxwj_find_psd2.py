# -*- coding: utf-8 -*-
"""重写工程 PSD 的定位逻辑：
1) 原样路径存在 → 用
2) 工程目录 + 同名 → 用
3) 把名字规范化（去掉 " -1"、" (2)"、"_3" 这类尾巴）后，在目录里找规范化后相同的 .psd
4) 目录里只有一个 .psd → 用
旧的"一路砍数字"写法会把 1114 -1 砍成空串，这里改成明确的规则。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'norm_stem' in s:
    print('already patched')
    raise SystemExit(0)

# 在 gxwj_find_psd 之前插入规范化函数
OLD_SIG = 'static int gxwj_find_psd(const char *prjdir, const char *orig, char *out)'
NORM = r'''
/* 把文件名主干规范化：1114 -1 / 1114(2) / 1114_3 / 1114  ->  1114 */
static void norm_stem(const char *name, char *out)
{
    char tmp[MAX_PATH];
    int len;
    const char *dot = 0, *q;
    lstrcpynA(tmp, name, MAX_PATH);
    for (q = tmp; *q; q++) if (*q == '.') dot = q;
    if (dot) tmp[(int)(dot - tmp)] = 0;
    len = lstrlenA(tmp);
    /* 去掉结尾的 (18) 这种括号尾巴 */
    if (len > 0 && tmp[len - 1] == ')') {
        int i;
        for (i = len - 2; i >= 0; i--) if (tmp[i] == '(') { len = i; break; }
        while (len > 0 && tmp[len - 1] == ' ') len--;
        tmp[len] = 0;
    }
    /* 去掉结尾的  -1 / -1 / _3 这种尾巴 */
    for (;;) {
        int cut = len;
        while (cut > 0 && tmp[cut - 1] >= '0' && tmp[cut - 1] <= '9') cut--;
        if (cut > 0 && cut < len &&
            (tmp[cut - 1] == ' ' || tmp[cut - 1] == '-' || tmp[cut - 1] == '_')) {
            cut--;
            while (cut > 0 && tmp[cut - 1] == ' ') cut--;
            len = cut;
            tmp[len] = 0;
            continue;
        }
        break;
    }
    while (len > 0 && (tmp[len - 1] == ' ' || tmp[len - 1] == '-' || tmp[len - 1] == '_')) tmp[--len] = 0;
    lstrcpynA(out, tmp, MAX_PATH);
}
'''
assert OLD_SIG in s
s = s.replace(OLD_SIG, NORM + '\n' + OLD_SIG, 1)

# 用新逻辑替换 gxwj_find_psd 整体
start = s.find('static int gxwj_find_psd(const char *prjdir, const char *orig, char *out)')
end = s.find('\n}\n', s.find('return 0;', start)) + 3
assert start > 0 and end > start

NEW_FN = r'''static int gxwj_find_psd(const char *prjdir, const char *orig, char *out)
{
    char cand[MAX_PATH], stem[MAX_PATH], want[MAX_PATH];
    const char *b = orig, *q = orig;
    WIN32_FIND_DATAA fd;
    HANDLE hs;
    int n = 0;
    char only[MAX_PATH];

    while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
    norm_stem(b, want);                              /* 目标主干 */

    /* 1) 原样同名 */
    wsprintfA(cand, "%s%s", prjdir, b);
    if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) { lstrcpynA(out, cand, MAX_PATH); return 1; }

    /* 2) 规范化后同名 */
    wsprintfA(cand, "%s*.psd", prjdir);
    hs = FindFirstFileA(cand, &fd);
    if (hs != INVALID_HANDLE_VALUE) {
        do {
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            n++;
            wsprintfA(only, "%s%s", prjdir, fd.cFileName);
            norm_stem(fd.cFileName, stem);
            if (!lstrcmpiA(stem, want)) {
                FindClose(hs);
                lstrcpynA(out, only, MAX_PATH);
                return 1;
            }
        } while (FindNextFileA(hs, &fd));
        FindClose(hs);
    }
    /* 3) 目录里只有一个 .psd */
    if (n == 1) { lstrcpynA(out, only, MAX_PATH); return 1; }
    return 0;
}
'''
s = s[:start] + NEW_FN + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
