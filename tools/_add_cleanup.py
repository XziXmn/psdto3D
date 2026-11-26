# -*- coding: utf-8 -*-
"""启动时清理：删旧的 ASCII 别名文件；_dongle.log 超过 4MB 就截断。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'startup_cleanup' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 启动清理：别名文件 + 过大的日志 ================= */
static void startup_cleanup(void)
{
    static int done;
    char log[MAX_PATH], pat[MAX_PATH], dir[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    if (done) return;
    done = 1;

    if (g_dir[0]) {
        wsprintfA(log, "%s_dongle.log", g_dir);
        h = CreateFileA(log, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
        if (h != INVALID_HANDLE_VALUE) {
            DWORD sz = GetFileSize(h, 0);
            CloseHandle(h);
            if (sz != INVALID_FILE_SIZE && sz > 4 * 1024 * 1024) {
                DeleteFileA(log);
                note("cleanup: _dongle.log 已超过 %lu 字节，清空重来", (unsigned long)sz);
            }
        }
    }

    if (psd_find_tempdir(dir)) {
        wsprintfA(pat, "%sok3d_ascii_*.*", dir);
        h = FindFirstFileA(pat, &fd);
        if (h != INVALID_HANDLE_VALUE) {
            int n = 0;
            do {
                char full[MAX_PATH];
                wsprintfA(full, "%s%s", dir, fd.cFileName);
                if (DeleteFileA(full)) n++;
            } while (FindNextFileA(h, &fd));
            FindClose(h);
            if (n) note("cleanup: 删掉 %d 个旧的别名文件", n);
        }
    }
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (cfg_on("psd_limit", 0, "_psd_limit.txt"))
            tabfix_try();'''
if OLD not in s:
    OLD = '''        if (cfg_on("layers_up", 1, "_layers_up.txt") ||'''
    NEW = '''        startup_cleanup();
        if (cfg_on("layers_up", 1, "_layers_up.txt") ||'''
    assert OLD in s, 'loop anchor'
    s = s.replace(OLD, NEW, 1)
else:
    s = s.replace(OLD, '        startup_cleanup();\n' + OLD, 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
