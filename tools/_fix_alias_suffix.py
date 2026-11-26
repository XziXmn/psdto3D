# -*- coding: utf-8 -*-
"""保存框：把 ok3d_ascii_XXXXXXXX 前缀换成原始文件名，但**保留程序自己加的后缀和扩展名**
（例如 xxx_3D输出.psd）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'alias_keep_suffix' in s:
    print('already patched')
    raise SystemExit(0)

# 找到 e_gsfn 里那段替换逻辑，整体替换成"保留后缀"的版本
start = s.find('    if (file && maxfile && g_alias_src[0]) {')
end = s.find('    if (g_isave < g_nsave) {', start)
assert start > 0 and end > start, 'anchor missing'

NEW = r'''    if (file && maxfile && g_alias_src[0]) {   /* alias_keep_suffix */
        const char *bn = file, *q = file;
        while (*q) { if (*q == '\\' || *q == '/') bn = q + 1; q++; }
        if (strncmp(bn, "ok3d_ascii_", 11) == 0) {
            const char *rest = bn + 11;
            const char *src = g_alias_src, *q2 = g_alias_src, *b2 = g_alias_src;
            char nm[MAX_PATH];
            int i = 0;
            int k;
            for (k = 0; k < 8 && rest[k]; k++) ;          /* 跳过 8 位哈希 */
            rest += k;
            while (*q2) { if (*q2 == '\\' || *q2 == '/') b2 = q2 + 1; q2++; }
            for (q2 = b2; *q2 && *q2 != '.' && i < MAX_PATH - 32; q2++) nm[i++] = *q2;
            nm[i] = 0;
            if (*rest) lstrcatA(nm, rest);                /* 保留程序加的后缀/扩展名 */
            else lstrcatA(nm, ".tif");
            lstrcpynA(file, nm, maxfile);
            note("gsfn: 别名 -> %s（保留后缀 %s）", nm, rest);
        }
    }
'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
