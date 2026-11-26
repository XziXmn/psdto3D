# -*- coding: utf-8 -*-
"""Make psd_assemble robust: derive the view count from the files when the caller's value
does not match, and clamp to what is actually available."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'psd_count_views' in s:
    print('already patched')
    raise SystemExit(0)

# 1) 加一个"数一遍中间文件"的函数
HELPER = r'''
static int psd_count_views(const char *dir)
{
    int i, n = 0;
    for (i = 1; i <= 64; i++) {
        char p1[MAX_PATH], p2[MAX_PATH];
        wsprintfA(p1, "%svwd%03d.gjs", dir, i);
        wsprintfA(p2, "%svwdt%03d.gjs", dir, i);
        if (GetFileAttributesA(p1) == INVALID_FILE_ATTRIBUTES) break;
        if (GetFileAttributesA(p2) == INVALID_FILE_ATTRIBUTES) break;
        n = i;
    }
    return n;
}
'''
s = s.replace('static int psd_assemble(const char *out_path, const char *dir, int w, int h, int views)',
              HELPER + '\nstatic int psd_assemble(const char *out_path, const char *dir, int w, int h, int views)', 1)

# 2) 入口处校正 views
OLD = '''    if (views <= 0 || views > 64) return 0;
    for (i = 0; i < views; i++) {'''
NEW = '''    {
        int avail = psd_count_views(dir);
        if (avail <= 0) {
            note("PSD build: 目录里没有 vwd*.gjs，放弃 (dir=%s)", dir ? dir : "(null)");
            return 0;
        }
        if (views != avail) {
            note("PSD build: 传入层数=%d，实际中间文件=%d → 以实际为准", views, avail);
            views = avail;
        }
    }
    if (views <= 0 || views > 64) return 0;
    for (i = 0; i < views; i++) {'''
assert OLD in s, 'assemble anchor missing'
s = s.replace(OLD, NEW, 1)

# 3) 调用点也不再用"图层数"做强校验
OLD2 = '''    if (g_native_file[0] && g_native_dir[0] && layers > 0 && layers <= 64 && w > 0 && h > 0)'''
NEW2 = '''    if (g_native_file[0] && g_native_dir[0] && w > 0 && h > 0)'''
if OLD2 in s:
    s = s.replace(OLD2, NEW2, 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
