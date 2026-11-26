/*
 * cmyktiff2.dll replacement — implements mergtotiff, forwards the rest.
 *
 * Why: without the hardware dongle the vendor's mergtotiff reads its per-view
 * pixel buffers from an in-memory object that only the licensed path fills, so it
 * aborts (Invalid floating point -> division by zero -> short read). The per-view
 * files it needs are already on disk (bmptotiff wrote C:\ok3dtemp\vwdNNN.gjs,
 * each a plain uncompressed CMYK TIFF), and the four page parameters arrive as
 * arguments, so the interlace can simply be done here.
 *
 * Packaging: keep the vendor DLL as cmyktiff2_orig.dll and load it lazily; every
 * export except mergtotiff is forwarded with a naked jump so the unknown calling
 * conventions stay intact.
 *
 * Build (32-bit): i686-w64-mingw32-gcc -shared -O2 -o cmyktiff2.dll cmykdrop.c
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

typedef void *HMOD;

HMOD g_orig;
void *g_bmptotiff; void *g_savetiff00, *g_gettiffinfo; void *g_JpgToBmp;
void *g_rgbtocmykbmp; void *g_tifftobmp;

static void logf_(const char *fmt, ...);
static void __cdecl logf_(const char *fmt, ...)
{
    FILE *f = fopen("_cmykdrop.txt", "a");
    if (!f) return;
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f);
    fclose(f);
}

__attribute__((noinline)) void drop_init(void)
{
    static int done = 0;
    if (done) return;
    done = 1;
    g_orig = (HMOD)LoadLibraryA("cmyktiff2_orig.dll");
    if (g_orig) {
        g_bmptotiff    = GetProcAddress((HMODULE)g_orig, "bmptotiff");
        g_savetiff00   = GetProcAddress((HMODULE)g_orig, "savetiff00");
        g_gettiffinfo  = GetProcAddress((HMODULE)g_orig, "gettiffinfo");
        g_JpgToBmp     = GetProcAddress((HMODULE)g_orig, "JpgToBmp");
        g_rgbtocmykbmp = GetProcAddress((HMODULE)g_orig, "rgbtocmykbmp");
        g_tifftobmp    = GetProcAddress((HMODULE)g_orig, "tifftobmp");
    }
    logf_("drop_init: orig=%p bmptotiff=%p", g_orig, g_bmptotiff);
}

void dongle_spy_install(void);

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)inst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) dongle_spy_install();
    return TRUE;
}

/* ---- forwarders: init first, then tail-jump with the stack untouched ---- */
__declspec(dllexport) __declspec(naked) void bmptotiff(void)
{ __asm__ __volatile__("pushal\n\tcall _drop_init\n\tpopal\n\tjmp *_g_bmptotiff"); }
__declspec(dllexport) __declspec(naked) void savetiff00(void)
{ __asm__ __volatile__("pushal\n\tcall _drop_init\n\tpopal\n\tjmp *_g_savetiff00"); }
__declspec(dllexport) __declspec(naked) void gettiffinfo(void)
{ __asm__ __volatile__("pushal\n\tcall _drop_init\n\tpopal\n\tjmp *_g_gettiffinfo"); }
__declspec(dllexport) __declspec(naked) void JpgToBmp(void)
{ __asm__ __volatile__("pushal\n\tcall _drop_init\n\tpopal\n\tjmp *_g_JpgToBmp"); }
__declspec(dllexport) __declspec(naked) void rgbtocmykbmp(void)
{ __asm__ __volatile__("pushal\n\tcall _drop_init\n\tpopal\n\tjmp *_g_rgbtocmykbmp"); }
__declspec(dllexport) __declspec(naked) void tifftobmp(void)
{ __asm__ __volatile__("pushal\n\tcall _drop_init\n\tpopal\n\tjmp *_g_tifftobmp"); }

/* ---------------- helpers ---------------- */

static unsigned char *read_file(const char *path, DWORD *out_size)
{
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    DWORD size = GetFileSize(h, 0), got = 0;
    unsigned char *buf = (unsigned char *)malloc(size ? size : 1);
    if (!buf) { CloseHandle(h); return 0; }
    if (!ReadFile(h, buf, size, &got, 0) || got != size) {
        free(buf); CloseHandle(h); return 0;
    }
    CloseHandle(h);
    *out_size = size;
    return buf;
}

static int write_file(const char *path, const void *data, DWORD size)
{
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, 0,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    DWORD wrote = 0;
    if (h == INVALID_HANDLE_VALUE) return -1;
    if (!WriteFile(h, data, size, &wrote, 0)) { CloseHandle(h); return -1; }
    CloseHandle(h);
    return wrote == size ? 0 : -1;
}

/* Delphi AnsiString: [refcount][len][chars...] */
static const char *delphi_str(void *p, char *buf, int cap)
{
    if (!p || IsBadReadPtr(p, 12)) return 0;
    int len = *(const int *)((const char *)p + 4);
    const char *s = (const char *)p + 8;
    if (len < 0 || len >= cap || IsBadReadPtr(s, len + 1)) return 0;
    memcpy(buf, s, len);
    buf[len] = 0;
    return buf;
}

/* little-endian TIFF little-endian helpers */
static void put16(unsigned char *p, unsigned v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); }
static void put32(unsigned char *p, unsigned v) { p[0]=(unsigned char)v; p[1]=(unsigned char)(v>>8); p[2]=(unsigned char)(v>>16); p[3]=(unsigned char)(v>>24); }

#define OFF_W   0x16
#define OFF_H   0x22
#define OFF_BPS 0x2E
#define OFF_SPP 0x5E
#define OFF_RPS 0x6A
#define OFF_CNT 0x76
#define OFF_XR  0x82
#define OFF_YR  0x8E
#define HDR_LEN 334

static int tag_read(const unsigned char *h, unsigned off, unsigned *tag, unsigned *val)
{
    *tag = (unsigned)h[off] | ((unsigned)h[off + 1] << 8);
    *val = (unsigned)h[off + 8] | ((unsigned)h[off + 9] << 8) |
           ((unsigned)h[off + 10] << 16) | ((unsigned)h[off + 11] << 24);
    return 0;
}

/* ---------------- the merge ---------------- */

__declspec(dllexport) int __stdcall mergtotiff(void *obj, long long dpi_x,
                                               long long lpi_x, long long w_x,
                                               long long h_x, int f1, int f2,
                                               int f3, void *path_p, int f4,
                                               int f5, int f6, int f7)
{
    char path[512]; path[0] = 0;
    {
        unsigned raw[13];
        raw[0]=(unsigned)(size_t)obj; raw[1]=(unsigned)dpi_x; raw[2]=(unsigned)(dpi_x>>32);
        raw[3]=(unsigned)lpi_x; raw[4]=(unsigned)(lpi_x>>32);
        raw[5]=(unsigned)w_x; raw[6]=(unsigned)(w_x>>32);
        raw[7]=(unsigned)h_x; raw[8]=(unsigned)(h_x>>32);
        raw[9]=(unsigned)f1; raw[10]=(unsigned)f2; raw[11]=(unsigned)f3;
        raw[12]=(unsigned)(size_t)path_p;
        int i;
        for (i = 0; i < 13; i++) {
            char ds[256], hex[100];
            const char *ok = delphi_str((void *)(size_t)raw[i], ds, sizeof(ds));
            int j;
            if (!IsBadReadPtr((void *)(size_t)raw[i], 20)) {
                const unsigned char *q = (const unsigned char *)(size_t)raw[i];
                for (j = 0; j < 16; j++) wsprintfA(hex + j * 3, "%02X ", q[j]);
                hex[48] = 0;
            } else lstrcpyA(hex, "<unmapped>");
            logf_("arg%-2d = %08X  ansi=%s  hex=%s", i, raw[i], ok ? ok : "-", hex);
        }
    }
    /* 输出路径实测是第 11 个参数（+0x30），普通 ANSI C 字符串 */
    {
        const char *pc = (const char *)(size_t)f2;
        int i = 0;
        path[0] = 0;
        if (pc && !IsBadReadPtr(pc, 1)) {
            while (i < 500 && !IsBadReadPtr(pc + i, 1) && pc[i]) { path[i] = pc[i]; i++; }
            path[i] = 0;
        }
        if (i < 4 || !strstr(path, ".")) {
            logf_("mergtotiff: bad output path (f2=%08X len=%d)", (unsigned)f2, i);
            return -2;
        }
        logf_("mergtotiff: out='%s'", path);
    }
    double dpi = (double)dpi_x / 10000.0, lpi = (double)lpi_x / 10000.0;
    double win = (double)w_x / 10000.0, hin = (double)h_x / 10000.0;
    if (win <= 0 || hin <= 0) {
        /* 无狗时这两个参数是 0；纸尺寸在 psdto3d104.inf 第二行（厘米） */
        char exe[MAX_PATH], inf[MAX_PATH];
        GetModuleFileNameA(NULL, exe, MAX_PATH);
        char *bs = strrchr(exe, '\\');
        if (bs) { *bs = 0; wsprintfA(inf, "%s\\psdto3d104.inf", exe); }
        else lstrcpyA(inf, "psdto3d104.inf");
        DWORD isz = 0;
        unsigned char *ib = read_file(inf, &isz);
        if (ib) {
            char *txt = (char *)ib, *line = txt, *p2 = 0;
            int ln = 0;
            while (*line && ln < 4) {
                char *e = strchr(line, '\n');
                if (e) *e = 0;
                if (++ln == 2) { p2 = line; break; }
                if (!e) break;
                line = e + 1;
            }
            double f[8] = {0};
            int got = p2 ? sscanf(p2, "%lf %lf %lf %lf %lf %lf %lf", &f[0], &f[1], &f[2],
                                  &f[3], &f[4], &f[5], &f[6]) : 0;
            if (got >= 5 && f[3] > 0.01 && f[4] > 0.01) {
                win = f[3] / 2.54; hin = f[4] / 2.54;
                logf_("mergtotiff: geometry from inf: %.4f x %.4f cm", f[3], f[4]);
            }
            free(ib);
        }
    }
    logf_("mergtotiff -> '%s' dpi=%.4f lpi=%.4f w=%.4f h=%.4f", path, dpi, lpi, win, hin);
    if (dpi <= 0 || lpi <= 0 || win <= 0 || hin <= 0) {
        logf_("mergtotiff: bad geometry, aborting");
        return -3;
    }

    /* 找出逐视图文件 vwd001.gjs ... 数出 N */
    char dir[MAX_PATH], first[MAX_PATH];
    lstrcpyA(dir, path);
    char *slash = strrchr(dir, '\\');
    if (slash) *slash = 0; else lstrcpyA(dir, ".");

    int n_views = 0, i;
    char names[64][MAX_PATH];
    {
        /* 逐视图文件可能和输出目录不同：依次试 输出目录 / C:\ok3dtemp / exe 目录\ok3dtemp */
        char cand[3][MAX_PATH];
        int nc = 0, ci;
        wsprintfA(cand[nc++], "%s", dir);
        lstrcpyA(cand[nc++], "C:\\ok3dtemp");
        {
            char exe[MAX_PATH]; GetModuleFileNameA(NULL, exe, MAX_PATH);
            char *bs2 = strrchr(exe, '\\');
            if (bs2) { *bs2 = 0; wsprintfA(cand[nc++], "%s\\ok3dtemp", exe); }
        }
        for (ci = 0; ci < nc; ci++) {
            int cnt = 0;
            for (i = 1; i <= 64; i++) {
                wsprintfA(first, "%s\\vwd%03d.gjs", cand[ci], i);
                HANDLE h = CreateFileA(first, GENERIC_READ, FILE_SHARE_READ, 0,
                                       OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
                if (h == INVALID_HANDLE_VALUE) break;
                CloseHandle(h);
                cnt++;
            }
            logf_("mergtotiff: dir '%s' has %d view(s)", cand[ci], cnt);
            if (cnt > n_views) {
                n_views = cnt;
                for (i = 0; i < cnt; i++)
                    wsprintfA(names[i], "%s\\vwd%03d.gjs", cand[ci], i + 1);
            }
        }
    }
    if (n_views < 2) {
        logf_("mergtotiff: only %d view file(s) in %s", n_views, dir);
        return -4;
    }

    /* 读第一个看尺寸 */
    DWORD sz = 0;
    unsigned char *v0 = read_file(names[0], &sz);
    if (!v0) { logf_("mergtotiff: cannot read %s", names[0]); return -5; }
    unsigned vw = 0, vh = 0, spp = 0, bps_off = 0;
    unsigned tag, val;
    tag_read(v0, OFF_W, &tag, &vw);
    tag_read(v0, OFF_H, &tag, &vh);
    tag_read(v0, OFF_SPP, &tag, &spp);
    tag_read(v0, OFF_BPS, &tag, &bps_off);
    {   /* 两种厂商头里 W/H 字段顺序不同，用 RowsPerStrip(0x0116) 定高度最稳 */
        unsigned hw = vw, hh = vh;              /* 头部按位置读到的两个数 */
        unsigned cnt = (unsigned)v0[8] | ((unsigned)v0[9] << 8);
        unsigned rows = 0, i2;
        for (i2 = 0; i2 < cnt && i2 < 32; i2++) {
            unsigned o2 = 0x0A + i2 * 12;
            unsigned t2 = (unsigned)v0[o2] | ((unsigned)v0[o2 + 1] << 8);
            unsigned v2 = (unsigned)v0[o2 + 8] | ((unsigned)v0[o2 + 9] << 8) |
                          ((unsigned)v0[o2 + 10] << 16) | ((unsigned)v0[o2 + 11] << 24);
            if (t2 == 0x0116) { rows = v2; break; }
        }
        if (rows > 1 && (unsigned long long)(sz - HDR_LEN) % ((unsigned long long)rows * 4) == 0) {
            vh = rows;
            vw = (unsigned)((unsigned long long)(sz - HDR_LEN) / ((unsigned long long)rows * 4));
        } else {
            /* 兜底：哪个方向更像"宽 < 高"就用哪个（印刷稿一般竖版） */
            if (hw > hh) { unsigned t = hw; hw = hh; hh = t; }
            vw = hw; vh = hh;
            logf_("mergtotiff: no RowsPerStrip, fallback %ux%u", vw, vh);
        }
        logf_("mergtotiff: header %ux%u (RowsPerStrip=%u) -> using %ux%u", hw, hh, rows, vw, vh);
    }
    logf_("mergtotiff: %d views, first %ux%u spp=%u file=%u", n_views, vw, vh, spp, sz);
    free(v0);
    if (vw < 2 || vh < 2 || spp != 4) { logf_("mergtotiff: unexpected view format"); return -6; }

    /* 输出尺寸 */
    long n_lent = (long)(win * lpi + 0.5);
    long P      = (long)(dpi / lpi + 0.5);
    long ow     = n_lent * P;
    long oh     = (long)(hin * dpi + 0.5);
    logf_("mergtotiff: lenticules=%ld P=%ld out=%ldx%ld", n_lent, P, ow, oh);
    if (ow < 2 || oh < 2 || ow > 100000 || oh > 100000) { logf_("mergtotiff: bad out size"); return -7; }

    unsigned char *out = (unsigned char *)calloc((size_t)ow * oh * 4, 1);
    if (!out) { logf_("mergtotiff: out of memory"); return -8; }

    int k;
    for (k = 0; k < n_views; k++) {
        unsigned char *v = read_file(names[k], &sz);
        if (!v) { logf_("mergtotiff: read fail %s", names[k]); continue; }
        unsigned w2, h2;
        tag_read(v, OFF_W, &tag, &w2);
        tag_read(v, OFF_H, &tag, &h2);
        if (!((w2 == vw && h2 == vh) || (w2 == vh && h2 == vw))) { free(v); continue; }
        const unsigned char *px = v + HDR_LEN;
        long y, x;
        for (y = 0; y < oh; y++) {
            unsigned sy = (unsigned)(((double)y + 0.5) * vh / oh);   /* 像素中心映射，实测与厂商逐像素一致 */
            if (sy >= vh) sy = vh - 1;
            unsigned char *orow = out + ((size_t)y * ow) * 4;
            const unsigned char *srow = px + ((size_t)sy * vw) * 4;
            for (x = 0; x < ow; x++) {
                long q = x % P;
                long vidx = (long)((double)q * n_views / P);
                if (vidx >= n_views) vidx = n_views - 1;
                long want = n_views - 1 - vidx;      /* 视图顺序是反的 */
                if (want != k) continue;
                long sx = (long)(((2.0 * x + 1.0) * vw) / (2.0 * ow));   /* 像素中心 */
                if (sx >= (long)vw) sx = vw - 1;
                unsigned char *d = orow + (size_t)x * 4;
                const unsigned char *s = srow + (size_t)sx * 4;
                d[0] = (unsigned char)(255 - s[0]);
                d[1] = (unsigned char)(255 - s[1]);
                d[2] = (unsigned char)(255 - s[2]);
                d[3] = (unsigned char)(255 - s[3]);
            }
        }
        free(v);
    }

    /* ---- 写 TIFF：与厂商相同的小端头 ---- */
    unsigned char hdr[HDR_LEN];
    memset(hdr, 0, sizeof(hdr));
    hdr[0] = 'I'; hdr[1] = 'I'; put16(hdr + 2, 42); put32(hdr + 4, 8);
    put16(hdr + 8, 17);
    /* 0x00FE garbage slot, 与厂商一致（值 0，阅读器忽略） */
    put16(hdr + 0x0A, 0x00FE); put16(hdr + 0x0C, 4); put32(hdr + 0x0E, 1); put32(hdr + 0x12, 0);
    put16(hdr + 0x16, 0x0100); put16(hdr + 0x18, 4); put32(hdr + 0x1A, 1); put32(hdr + 0x1E, ow);
    put16(hdr + 0x22, 0x0101); put16(hdr + 0x24, 4); put32(hdr + 0x26, 1); put32(hdr + 0x2A, oh);
    put16(hdr + 0x2E, 0x0102); put16(hdr + 0x30, 3); put32(hdr + 0x32, 4); put32(hdr + 0x36, 0xDA);
    put16(hdr + 0x3A, 0x0103); put16(hdr + 0x3C, 3); put32(hdr + 0x3E, 1); put32(hdr + 0x42, 1);
    put16(hdr + 0x46, 0x0106); put16(hdr + 0x48, 3); put32(hdr + 0x4A, 1); put32(hdr + 0x4E, 5);
    put16(hdr + 0x52, 0x0111); put16(hdr + 0x54, 4); put32(hdr + 0x56, 1); put32(hdr + 0x5A, HDR_LEN);
    put16(hdr + 0x5E, 0x0115); put16(hdr + 0x60, 3); put32(hdr + 0x62, 1); put32(hdr + 0x66, 4);
    put16(hdr + 0x6A, 0x0116); put16(hdr + 0x6C, 4); put32(hdr + 0x6E, 1); put32(hdr + 0x72, oh);
    put16(hdr + 0x76, 0x0117); put16(hdr + 0x78, 4); put32(hdr + 0x7A, 1);
    put32(hdr + 0x7E, (unsigned)ow * (unsigned)oh * 4);
    put16(hdr + 0x82, 0x011A); put16(hdr + 0x84, 5); put32(hdr + 0x86, 1); put32(hdr + 0x8A, 0xE2);
    put16(hdr + 0x8E, 0x011B); put16(hdr + 0x90, 5); put32(hdr + 0x92, 1); put32(hdr + 0x96, 0xEA);
    put16(hdr + 0x9A, 0x011C); put16(hdr + 0x9C, 3); put32(hdr + 0x9E, 1); put32(hdr + 0xA2, 1);
    put16(hdr + 0xA6, 0x0128); put16(hdr + 0xA8, 3); put32(hdr + 0xAA, 1); put32(hdr + 0xAE, 2);
    put16(hdr + 0xB2, 0x0131); put16(hdr + 0xB4, 2); put32(hdr + 0xB6, 60); put32(hdr + 0xBA, 0xF2);
    put16(hdr + 0xBE, 0x0132); put16(hdr + 0xC0, 2); put32(hdr + 0xC2, 20); put32(hdr + 0xC6, 0x12E);
    put16(hdr + 0xCA, 0x013B); put16(hdr + 0xCC, 2); put32(hdr + 0xCE, 12); put32(hdr + 0xD2, 0x142);
    /* BitsPerSample 8,8,8,8 */
    put16(hdr + 0xDA, 8); put16(hdr + 0xDC, 8); put16(hdr + 0xDE, 8); put16(hdr + 0xE0, 8);
    /* resolutions = dpi * 10000 / 10000 */
    {
        unsigned r = (unsigned)(dpi * 10000.0 + 0.5);
        put32(hdr + 0xE2, r); put32(hdr + 0xE6, 10000);
        put32(hdr + 0xEA, r); put32(hdr + 0xEE, 10000);
    }
    memcpy(hdr + 0xF2, "ok3d.com email:sales@ok3d.com hongmin guo +86-755-36843399", 59);
    hdr[0xF2 + 59] = 0;
    {
        SYSTEMTIME st; GetLocalTime(&st);
        wsprintfA((char *)hdr + 0x12E, "%04d/%02d/%02d %02d:%02d:%02d",
                  st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    }
    memcpy(hdr + 0x142, "www.ok3d.com", 12);

    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) { logf_("mergtotiff: cannot create '%s'", path); free(out); return -9; }
    DWORD wrote = 0;
    WriteFile(h, hdr, HDR_LEN, &wrote, 0);
    WriteFile(h, out, (DWORD)((size_t)ow * oh * 4), &wrote, 0);
    CloseHandle(h);
    free(out);
    logf_("mergtotiff: wrote %ldx%ld to '%s'", ow, oh, path);
    return 0;
}
