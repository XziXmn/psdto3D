# -*- coding: utf-8 -*-
"""修 I/O 103 隐患：
1) 转换结果做缓存（源文件未变就复用），避免程序二次打开时我们把它正在读的文件重写；
2) 目标目录不可写时退到 %TEMP%。
"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'gxwj_cached_src' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    /* 写转换结果 */
    wsprintfA(out, "%s_gxwj_conv.tw3d2", g_dir);'''
NEW = '''    /* 写转换结果：源文件没变就复用上次的产物，避免程序二次打开时文件被重写 */
    {
        static char gxwj_cached_src[MAX_PATH];
        static unsigned long gxwj_cached_size, gxwj_cached_time;
        HANDLE src2 = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
        unsigned long sz = 0xFFFFFFFF, tm = 0;
        if (src2 != INVALID_HANDLE_VALUE) {
            sz = GetFileSize(src2, 0);
            tm = GetFileTime(src2, 0, 0) ? 0 : 0;
            {
                FILETIME ft;
                if (GetFileTime(src2, 0, 0, &ft)) tm = ft.dwLowDateTime;
            }
            CloseHandle(src2);
        }
        if (!lstrcmpiA(gxwj_cached_src, src) && sz == gxwj_cached_size &&
            tm == gxwj_cached_time) {
            wsprintfA(out, "%s_gxwj_conv.tw3d2", g_dir);
            if (GetFileAttributesA(out) != INVALID_FILE_ATTRIBUTES) {
                note("GXWJ: 复用上次转换结果 %s", out);
                VirtualFree(buf, 0, MEM_RELEASE);
                return 1;
            }
        }
        gxwj_cached_size = sz;
        gxwj_cached_time = tm;
        lstrcpynA(gxwj_cached_src, src, MAX_PATH);
    }
    wsprintfA(out, "%s_gxwj_conv.tw3d2", g_dir);'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)

# 写失败时退到 %TEMP%
OLD2 = '''    of = CreateFileA(out, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, 0, 0);
    if (of == INVALID_HANDLE_VALUE) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }'''
NEW2 = '''    of = CreateFileA(out, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, 0, 0);
    if (of == INVALID_HANDLE_VALUE) {
        char tmp[MAX_PATH];
        GetTempPathA(MAX_PATH, tmp);
        lstrcatA(tmp, "ok3d_gxwj_conv.tw3d2");
        of = CreateFileA(tmp, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, 0, 0);
        if (of != INVALID_HANDLE_VALUE) lstrcpynA(out, tmp, MAX_PATH);
    }
    if (of == INVALID_HANDLE_VALUE) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }'''
assert OLD2 in s, 'anchor2 missing'
s = s.replace(OLD2, NEW2, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
