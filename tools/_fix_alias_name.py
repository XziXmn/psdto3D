# -*- coding: utf-8 -*-
"""保存框里只要文件名以 ok3d_ascii_ 开头就换成原始文件名（按当前扩展名）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'alias_name_fix' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    if (file && maxfile && g_alias_dst[0] && lstrcmpiA(file, g_alias_dst) == 0) {'''
NEW = '''    if (file && maxfile && g_alias_src[0]) {   /* alias_name_fix */
        const char *bn = file, *p2 = file;
        while (*p2) { if (*p2 == '\\\\' || *p2 == '/') bn = p2 + 1; p2++; }
        if (lstrcmpiA(bn, "") != 0 && strncmp(bn, "ok3d_ascii_", 11) != 0) {
            /* 不是我们的别名，跳过 */
        }
    }
    if (file && maxfile && g_alias_dst[0] && lstrcmpiA(file, g_alias_dst) == 0) {'''
assert OLD in s
s = s.replace(OLD, NEW, 1)

# 追加：处理"仅文件名是别名、扩展名不同"的情况
OLD2 = '''        lstrcatA(nm, ".tif");
        lstrcpynA(file, nm, maxfile);
        note("gsfn: 别名 -> 原始名 %s", nm);
    }'''
NEW2 = '''        lstrcatA(nm, ".tif");
        lstrcpynA(file, nm, maxfile);
        note("gsfn: 别名 -> 原始名 %s", nm);
    } else if (file && maxfile && g_alias_src[0]) {
        const char *bn = file, *p3 = file, *ext = 0;
        char nm[MAX_PATH];
        int i = 0;
        while (*p3) { if (*p3 == '\\\\' || *p3 == '/') bn = p3 + 1; p3++; }
        if (strncmp(bn, "ok3d_ascii_", 11) == 0) {
            const char *src = g_alias_src, *q2 = g_alias_src, *b2 = g_alias_src;
            while (*q2) { if (*q2 == '\\\\' || *q2 == '/') b2 = q2 + 1; q2++; }
            for (q2 = b2; *q2 && i < MAX_PATH - 8; q2++) {
                if (*q2 == '.') break;
                nm[i++] = *q2;
            }
            { const char *d = bn; while (*d && *d != '.') d++; ext = d; }   /* 保留原扩展名 */
            nm[i] = 0;
            if (ext && *ext) lstrcatA(nm, ext);
            lstrcpynA(file, nm, maxfile);
            note("gsfn: 别名文件名 -> %s", nm);
        }
    }'''
assert OLD2 in s
s = s.replace(OLD2, NEW2, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
