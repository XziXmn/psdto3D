# -*- coding: utf-8 -*-
"""别名策略改成"只缩短目录、保留原文件名"：
实测原版对中文文件名没问题，真正扛不住的是**过长的路径**。
所以只在路径过长时把文件硬链接到 C:\\ok3dtemp\\<原文件名>，名字保持原样，
标题栏和对话框里就不会再出现 ok3d_ascii_xxxx 这种乱码名。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'alias_short_dir' in s:
    print('already patched')
    raise SystemExit(0)

start = s.find('static int ascii_alias(const char *src, char *out, int outsz)')
end = s.find('\n}\n', s.find('return 1;', start)) + 3
assert start > 0 and end > start, 'anchor'

NEW = r'''static int ascii_alias(const char *src, char *out, int outsz)   /* alias_short_dir */
{
    char dir[MAX_PATH], name[MAX_PATH];
    const char *base = src, *q = src;
    int len;
    if (!cfg_val("ascii_alias", 1)) return 0;
    if (!src) return 0;
    len = lstrlenA(src);
    if (len <= 96) return 0;                     /* 短路径不用动 */
    if (!psd_find_tempdir(dir)) GetTempPathA(MAX_PATH, dir);
    while (*q) { if (*q == '\\' || *q == '/') base = q + 1; q++; }
    lstrcpynA(name, base, MAX_PATH);
    if (lstrlenA(name) > 80) {                   /* 名字本身太长才退化成哈希名 */
        unsigned long hash = 2166136261UL;
        const char *dot = 0, *r;
        for (r = base; *r; r++) { if (*r == '.') dot = r; hash = (hash ^ (unsigned char)*r) * 16777619UL; }
        wsprintfA(name, "ok3d_%08lX%s", hash, dot ? dot : "");
    }
    lstrcpynA(out, dir, outsz - MAX_PATH / 2);
    lstrcatA(out, name);
    if (!lstrcmpiA(out, src)) return 0;
    DeleteFileA(out);
    if (!CreateHardLinkA(out, src, 0)) {
        if (!CopyFileA(src, out, FALSE)) {
            note("alias: 建立短路径失败 %s", src);
            return 0;
        }
        note("alias: 复制 -> %s", out);
    } else {
        note("alias: 硬链接 -> %s（原名 %d 字符路径太长）", out, len);
    }
    lstrcpynA(g_alias_src, src, MAX_PATH);
    lstrcpynA(g_alias_dst, out, MAX_PATH);
    return 1;
}
'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
