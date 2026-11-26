# -*- coding: utf-8 -*-
"""让程序直接打开 99 工程的 .gxwj：在 CreateFileA 里透明转换成 .tw3d2 再交给它。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'gxwj_convert' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 99 工程(.gxwj) 透明转换 ================= */
static int gxwj_read_psd(const char *path, int *w, int *h, int *layers)
{
    HANDLE fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    unsigned char head[26];
    DWORD got = 0;
    unsigned n;
    short cnt;
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 ||
        memcmp(head, "8BPS", 4) != 0) { CloseHandle(fh); return 0; }
    *h = (head[14] << 24) | (head[15] << 16) | (head[16] << 8) | head[17];
    *w = (head[18] << 24) | (head[19] << 16) | (head[20] << 8) | head[21];
    SetFilePointer(fh, 4, 0, FILE_CURRENT);
    { DWORD d = 0; ReadFile(fh, &d, 4, &got, 0); n = ((d&0xFF)<<24)|((d>>8&0xFF)<<16)|((d>>16&0xFF)<<8)|(d>>24&0xFF); }
    SetFilePointer(fh, n, 0, FILE_CURRENT);
    { DWORD d = 0; ReadFile(fh, &d, 4, &got, 0); n = ((d&0xFF)<<24)|((d>>8&0xFF)<<16)|((d>>16&0xFF)<<8)|(d>>24&0xFF); }
    SetFilePointer(fh, n, 0, FILE_CURRENT);
    { unsigned char z[8]; ReadFile(fh, z, 8, &got, 0); }
    { unsigned char c[2] = {0,0}; ReadFile(fh, c, 2, &got, 0);
      cnt = (short)((c[0] << 8) | c[1]); if (cnt < 0) cnt = -cnt; *layers = cnt; }
    CloseHandle(fh);
    return 1;
}

static int gxwj_convert(const char *src, char *out, int outsz)
{
    HANDLE fh = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    DWORD size, got = 0;
    char *buf, *lines[4096];
    int nl = 0, i, w = 0, h = 0, layers = 0;
    char psdpath[MAX_PATH];
    HANDLE of;
    if (fh == INVALID_HANDLE_VALUE) return 0;
    size = GetFileSize(fh, 0);
    if (size == 0 || size > 8 * 1024 * 1024) { CloseHandle(fh); return 0; }
    buf = (char *)VirtualAlloc(0, size + 1, MEM_COMMIT, PAGE_READWRITE);
    if (!buf) { CloseHandle(fh); return 0; }
    ReadFile(fh, buf, size, &got, 0);
    CloseHandle(fh);
    buf[got] = 0;

    /* 切行 */
    lines[nl++] = buf;
    for (i = 0; i < (int)got && nl < 4095; i++) {
        if (buf[i] == '\r' && i + 1 < (int)got && buf[i + 1] == '\n') {
            buf[i] = 0; buf[i + 1] = 0;
            lines[nl++] = buf + i + 2;
            i++;
        }
    }
    if (nl < 7) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
    if (lstrcmpA(lines[2], "39550 0 0 0") != 0 && lstrncmpA(lines[2], "39550", 5) != 0) {
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;                     /* 不是 99 工程 */
    }

    /* PSD 路径：先按原样找，找不到就在 gxwj 同目录找同名 .psd */
    lstrcpynA(psdpath, lines[0], MAX_PATH);
    if (GetFileAttributesA(psdpath) == INVALID_FILE_ATTRIBUTES) {
        char base[MAX_PATH], cand[MAX_PATH];
        const char *q = src, *b = src;
        int k;
        while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
        lstrcpynA(base, src, (int)(b - src) + 1);
        lstrcpynA(cand, base, MAX_PATH);
        lstrcatA(cand, lines[0]);
        {
            const char *r = cand, *last = cand;
            while (*r) { if (*r == '\\' || *r == '/') last = r + 1; r++; }
            lstrcpynA(base + lstrlenA(base), last, MAX_PATH - lstrlenA(base));
        }
        if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) {
            lstrcpynA(psdpath, cand, MAX_PATH);
        }
    }
    if (!gxwj_read_psd(psdpath, &w, &h, &layers)) {
        note("GXWJ: 读不到 PSD 头 (%s)，放弃转换", psdpath);
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;
    }

    /* 写转换结果 */
    wsprintfA(out, "%s_gxwj_conv.tw3d2", g_dir);
    of = CreateFileA(out, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, 0, 0);
    if (of == INVALID_HANDLE_VALUE) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }

    #define WLINE(p) WriteFile(of, (p), lstrlenA(p), &got, 0); WriteFile(of, "\r\n", 2, &got, 0)
    WLINE(psdpath);                       /* 0 路径 */
    WLINE(lines[1]);                      /* 1 参数 */
    { char t[128]; wsprintfA(t, "99100 %d %d %d", layers, w, h); WLINE(t); }
    WLINE(lines[3]);                      /* 3 banner1 */
    WLINE(lines[4]);                      /* 4 banner2 */
    WLINE("Author: ");                    /* 5 作者 */
    { char t[64]; SYSTEMTIME st;
      GetLocalTime(&st);
      wsprintfA(t, "%d/%d/%d %d:%02d:%02d", st.wYear, st.wMonth, st.wDay,
                st.wHour, st.wMinute, st.wSecond);
      WLINE(t); }                         /* 6 保存时间 */
    for (i = 6; i < nl; i++) {            /* 7+ DPI 行及其后 */
        if (i == nl - 1 && lines[i][0] == 0) break;
        WLINE(lines[i]);
    }
    #undef WLINE
    CloseHandle(of);
    VirtualFree(buf, 0, MEM_RELEASE);
    note("GXWJ: %s -> %s (层=%d %dx%d)", src, out, layers, w, h);
    return 1;
}
'''

ANCHOR = 'static HANDLE WINAPI e_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,'
assert ANCHOR in s, 'cfa anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 在 e_cfa 的设备分支之前插入 gxwj 拦截
OLD = '''    if (is_dongle_path(name)) {'''
NEW = '''    if (name && GetFileAttributesA("_gxwj.txt") != INVALID_FILE_ATTRIBUTES) {
        int len = lstrlenA(name);
        if (len > 5 && lstrcmpiA(name + len - 5, ".gxwj") == 0) {
            char conv[MAX_PATH];
            if (gxwj_convert(name, conv, MAX_PATH))
                return o_cfa(conv, acc, share, sa, disp, flags, tmpl);
        }
    }
    if (is_dongle_path(name)) {'''
assert OLD in s, 'inner anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
