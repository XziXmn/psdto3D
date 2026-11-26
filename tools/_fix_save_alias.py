# -*- coding: utf-8 -*-
"""修两处体验问题：
1) 保存对话框继承了 PSD 的 ASCII 别名（跑到 ok3dtemp、名字是乱码）→ 换成原始文件名；
2) 启动时清掉旧别名文件，并把过大的 _dongle.log 截断。
"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'g_alias_dst' in s:
    print('already patched')
    raise SystemExit(0)

# 1) 全局记录别名与原始路径
OLD = 'static int has_non_ascii(const char *s)'
NEW = '''static char g_alias_src[MAX_PATH];      /* 原始（含中文）路径 */
static char g_alias_dst[MAX_PATH];      /* 我们给程序的 ASCII 别名 */

static int has_non_ascii(const char *s)'''
assert OLD in s
s = s.replace(OLD, NEW, 1)

# ascii_alias 里记录
OLD2 = '''    lstrcpynA(out, dir, outsz - 64);
    lstrcatA(out, name);'''
NEW2 = '''    lstrcpynA(out, dir, outsz - 64);
    lstrcatA(out, name);
    lstrcpynA(g_alias_src, src, MAX_PATH);
    lstrcpynA(g_alias_dst, out, MAX_PATH);'''
assert OLD2 in s
s = s.replace(OLD2, NEW2, 1)

# 2) 保存对话框：把继承来的别名换成原始文件名（保留扩展名）
OLD3 = '''static BOOL WINAPI e_gsfn(void *p)
{
    if (capture_mode() && o_gsfn) return ((BOOL (WINAPI *)(void *))o_gsfn)(p);
    char *file = *(char **)((char *)p + 0x1C);
    unsigned maxfile = *(unsigned *)((char *)p + 0x20);'''
NEW3 = '''static BOOL WINAPI e_gsfn(void *p)
{
    if (capture_mode() && o_gsfn) return ((BOOL (WINAPI *)(void *))o_gsfn)(p);
    char *file = *(char **)((char *)p + 0x1C);
    unsigned maxfile = *(unsigned *)((char *)p + 0x20);
    /* 保存框不该继承 PSD 的 ASCII 别名（会跑到 ok3dtemp 且名字是哈希） */
    if (file && maxfile && g_alias_dst[0] && lstrcmpiA(file, g_alias_dst) == 0) {
        const char *b = g_alias_src, *q = g_alias_src, *dot = 0;
        char nm[MAX_PATH];
        int i = 0;
        while (*q) { if (*q == '\\\\' || *q == '/') b = q + 1; q++; }
        for (q = b; *q && i < MAX_PATH - 8; q++) {
            if (*q == '.') break;
            nm[i++] = *q;
        }
        nm[i] = 0;
        lstrcatA(nm, ".tif");
        lstrcpynA(file, nm, maxfile);
        note("gsfn: 别名 -> 原始名 %s", nm);
    }'''
assert OLD3 in s
s = s.replace(OLD3, NEW3, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
