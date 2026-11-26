# -*- coding: utf-8 -*-
"""工程文件里的 PSD 路径失效时自动修复：
读 .tw3d2/.tw3d 第一行，若该 PSD 不存在，就在工程同目录找同名 .psd（或唯一的一个 .psd），
把工程改成指向它，再交给程序。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'tw3d2_fix_psd' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 工程文件 PSD 路径自动修复 ================= */
static int tw3d2_fix_psd(const char *prj, char *out, int outsz)
{
    HANDLE fh;
    DWORD got = 0, size;
    char *buf, line1[MAX_PATH], dir[MAX_PATH], cand[MAX_PATH];
    const char *b = prj, *q = prj;
    int i, len1;
    WIN32_FIND_DATAA fd;
    HANDLE hs;
    int found = 0;

    fh = CreateFileA(prj, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) return 0;
    size = GetFileSize(fh, 0);
    if (size == 0 || size > 4 * 1024 * 1024) { CloseHandle(fh); return 0; }
    buf = (char *)VirtualAlloc(0, size + 2, MEM_COMMIT, PAGE_READWRITE);
    if (!buf) { CloseHandle(fh); return 0; }
    ReadFile(fh, buf, size, &got, 0);
    CloseHandle(fh);
    buf[got] = 0;

    len1 = 0;
    while (len1 < (int)got && buf[len1] != '\r' && buf[len1] != '\n') len1++;
    if (len1 <= 0 || len1 >= MAX_PATH) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
    memcpy(line1, buf, len1); line1[len1] = 0;
    if (GetFileAttributesA(line1) != INVALID_FILE_ATTRIBUTES) {
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;                       /* PSD 存在，不动 */
    }

    /* 工程所在目录 */
    while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
    lstrcpynA(dir, prj, (int)(b - prj) + 1);

    /* 1) 同名 .psd */
    {
        const char *lb = line1, *r = line1;
        while (*r) { if (*r == '\\' || *r == '/') lb = r + 1; r++; }
        lstrcpynA(cand, dir, MAX_PATH - 8);
        lstrcatA(cand, lb);
        lstrcatA(cand, ".psd");
        if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) found = 1;
    }
    /* 2) 目录里只有一个 .psd 就用它 */
    if (!found) {
        wsprintfA(cand, "%s*.psd", dir);
        hs = FindFirstFileA(cand, &fd);
        if (hs != INVALID_HANDLE_VALUE) {
            int n = 0;
            char only[MAX_PATH];
            do {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                    n++;
                    lstrcpynA(only, dir, MAX_PATH - 8);
                    lstrcatA(only, fd.cFileName);
                }
            } while (FindNextFileA(hs, &fd));
            FindClose(hs);
            if (n == 1) { lstrcpynA(cand, only, MAX_PATH); found = 1; }
        }
    }
    if (!found) {
        note("tw3d2: %s 里写的 PSD 不存在（%s），同目录也没找到对应文件", prj, line1);
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;
    }

    /* 写修复副本：替换第一行 */
    wsprintfA(out, "%s_psdfix.tw3d2", g_dir);
    {
        HANDLE of = CreateFileA(out, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, 0, 0);
        DWORD wr = 0;
        if (of == INVALID_HANDLE_VALUE) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
        WriteFile(of, cand, lstrlenA(cand), &wr, 0);
        WriteFile(of, buf + len1, got - len1, &wr, 0);
        CloseHandle(of);
    }
    note("tw3d2: PSD 路径修复 %s -> %s（工程 %s）", line1, cand, prj);
    VirtualFree(buf, 0, MEM_RELEASE);
    return 1;
}
'''

ANCHOR = 'static HANDLE WINAPI e_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,'
assert ANCHOR in s, 'anchor'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''    if (name && cfg_on("gxwj", 1, "_gxwj.txt")) {'''
NEW = '''    if (name) {                       /* tw3d2_fix_psd: 工程里 PSD 路径失效时自动修复 */
        int l3 = lstrlenA(name);
        if ((l3 > 6 && lstrcmpiA(name + l3 - 6, ".tw3d2") == 0) ||
            (l3 > 5 && lstrcmpiA(name + l3 - 5, ".tw3d") == 0)) {
            char fixed[MAX_PATH];
            if (tw3d2_fix_psd(name, fixed, MAX_PATH)) {
                HANDLE hf2 = o_cfa(fixed, GENERIC_READ | GENERIC_WRITE,
                                   FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
                if (hf2 != INVALID_HANDLE_VALUE) {
                    note("tw3d2: 打开修复后的工程 %s", fixed);
                    return hf2;
                }
            }
        }
    }
    if (name && cfg_on("gxwj", 1, "_gxwj.txt")) {'''
assert OLD in s, 'inner anchor'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
