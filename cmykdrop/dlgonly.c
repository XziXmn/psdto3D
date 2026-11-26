/* 只接管文件对话框的代理 DLL —— 复查用的"干净 A 组"底板。
 *
 * 为什么需要它：现有的 cmyktiff2_fake.dll 会同时钩 CreateFileA/DeviceIoControl、
 * 伪造 SetupAPI 设备、hook exe 的 0x109E44、并顶掉厂商 mergtotiff。
 * 只要加载它，"带狗跑一遍"测到的就是它自己，不是厂商行为。
 *
 * 这个 DLL 只做三件事：
 *   1) 把 GetOpenFileNameA / GetSaveFileNameA 换成按 _dlgopen.txt / _dlgsave.txt
 *      顺序应答的桩（其余全部尾跳转发给厂商 cmyktiff2_orig.dll）；
 *   2) 可选、严格的**只读**采样（SCAN=1 时开），用于观察图层记录表；
 *   3) 可选、**只转储**的 bmptotiff 探针（DUMP_BMPTOTIFF），用于量入参。
 *
 * 构建（i686）：
 *   i686-w64-mingw32-gcc -shared -O2 -o cmyktiff2.dll dlgonly.c dlgstub.c \
 *       -static -static-libgcc -Wl,--kill-at
 *   加 -DDUMP_BMPTOTIFF 得到 bmptotiff 参数转储版
 *   加 -DNO_BMPTOTIFF   得到 bmptotiff 短路版（证明视图文件是谁写的）
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>

#define RVA_DLG_SAVE 0x1249F0
#define RVA_DLG_OPEN 0x1249F4

#define RVA_REC_PTR 0x1230B4
#define RVA_REC_CNT 0x12315C
#define RVA_F0FC    0x1230FC
#define RVA_ARR_A   0x12309C
#define RVA_ARR_B   0x1230A0
#define RVA_AMP     0x12308C
#define RVA_OFF     0x123090
#define RVA_VIEW    0x123158
#define RVA_F203    0x123203
#define RVA_F204    0x123204
#define REC_SIZE    56
#define REC_GROUP   0x2C

typedef void *HMOD;

void count_get3(unsigned *a, unsigned *b, unsigned *c) __attribute__((weak));
void count_install(void) __attribute__((weak));
void vwdump_install(void) __attribute__((weak));
void vwd2_install(void) __attribute__((weak));

static char g_dir[MAX_PATH];
static HMOD g_orig;

/* ---- dlgstub.c 需要的外部符号 ---- */
void dlg_stub_start(const char *exe_dir, void *o, void *s);
BOOL WINAPI h_dlg_open(LPOPENFILENAMEA);
BOOL WINAPI h_dlg_save(LPOPENFILENAMEA);

static void note_to(const char *file, const char *fmt, va_list ap)
{
    char path[MAX_PATH], b[1024];
    FILE *f;
    if (!g_dir[0]) return;
    lstrcpyA(path, g_dir);
    lstrcatA(path, file);
    f = fopen(path, "a");
    if (!f) return;
    wvsprintfA(b, fmt, ap);
    fprintf(f, "%s\n", b);
    fclose(f);
}

void dlg_note(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    note_to("_dlgonly.txt", fmt, ap);
    va_end(ap);
}

void count_note(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    note_to("_dlgonly.txt", fmt, ap);
    va_end(ap);
}

/* ============ 只读采样：谁会去写 +0x2C ============ */
static DWORD WINAPI scan_thread(LPVOID p)
{
    unsigned last_cnt = 0xFFFFFFFFu, last_ptr = 0, last_sig = 0xFFFFFFFFu;
    unsigned tick = 0, seq = 0;
    unsigned l1 = 0xFFFFFFFFu, l2 = 0xFFFFFFFFu, l3 = 0xFFFFFFFFu;
    unsigned lastH3 = 0xFFFFFFFFu, lastH4 = 0xFFFFFFFFu;
    (void)p;
    for (;;) {
        unsigned char *base = (unsigned char *)GetModuleHandleA(NULL);
        unsigned cnt, ptr;
        Sleep(300);
        tick++;
        if (!base) continue;
        {
            unsigned h3, h4, h5;
            if (count_get3) count_get3(&h3, &h4, &h5);
            if (h3 != lastH3 || h4 != lastH4) {
                char b[160];
                lastH3 = h3; lastH4 = h4;
                wsprintfA(b, "t=%u ANIM 55C9=%u 5E05=%u 6352=%u", tick * 3 / 10, h3, h4, h5);
                dlg_note("%s", b);
            }
        }
        cnt = *(unsigned short *)(base + RVA_REC_CNT);
        ptr = *(unsigned *)(base + RVA_REC_PTR);
        if (ptr > 0x10000u && ptr < 0x80000000u && cnt < 400 &&
            !IsBadReadPtr((void *)ptr, cnt * REC_SIZE)) {
            unsigned char *r = (unsigned char *)ptr;
            unsigned i, sig = 2166136261u;
            char buf[1200];
            int k = 0;
            for (i = 0; i < cnt && i < 40; i++)
                sig = (sig ^ r[i * REC_SIZE + REC_GROUP]) * 16777619u;
            if (cnt != last_cnt || ptr != last_ptr || sig != last_sig) {
                last_cnt = cnt; last_ptr = ptr; last_sig = sig;
                k = wsprintfA(buf, "t=%u cnt=%u ptr=%08X +2C[0..%u]=", tick * 3 / 10, cnt, ptr, i);
                for (unsigned j = 0; j < i && k < 400; j++)
                    k += wsprintfA(buf + k, "%02X", r[j * REC_SIZE + REC_GROUP]);
                dlg_note("%s", buf);
                if (seq < 40 && cnt <= 64) {          /* 整表落盘，事后逐字段对照 */
                    char path[MAX_PATH];
                    FILE *f;
                    wsprintfA(path, "%s_rec_%02u.bin", g_dir, seq++);
                    f = fopen(path, "wb");
                    if (f) {
                        fwrite(r, 1, cnt * REC_SIZE, f);
                        fclose(f);
                    }
                    k = wsprintfA(buf, "t=%u rec0=", tick * 3 / 10);
                    for (i = 0; i < REC_SIZE && k < 500; i++)
                        k += wsprintfA(buf + k, "%02X", r[i]);
                    dlg_note("%s", buf);
                }
            }
        } else if (cnt != last_cnt || ptr != last_ptr) {
            char buf[128];
            last_cnt = cnt; last_ptr = ptr; last_sig = 0xFFFFFFFFu;
            wsprintfA(buf, "t=%u cnt=%u ptr=%08X (不可读)", tick * 3 / 10, cnt, ptr);
            dlg_note("%s", buf);
        }
        {
            unsigned v1 = *(unsigned *)(base + RVA_F0FC);
            unsigned v2 = *(unsigned *)(base + RVA_ARR_A);
            unsigned v3 = *(unsigned *)(base + RVA_ARR_B);
            int amp = (int)*(unsigned *)(base + RVA_AMP);
            int off = (int)*(unsigned *)(base + RVA_OFF);
            unsigned view = *(unsigned *)(base + RVA_VIEW);
            unsigned p230 = *(unsigned *)(base + 0x123230);
            unsigned p234 = *(unsigned *)(base + 0x123234);
            unsigned p218 = *(unsigned *)(base + 0x123218);
            unsigned p1e4 = *(unsigned *)(base + 0x1231E4);
            unsigned p170 = *(unsigned *)(base + 0x123170);
            static unsigned l1 = 0xFFFFFFFFu, l2, l3, l4, l5, l6, l7, l8, l9, l10, l11;
            static int la = 0x7FFFFFFF, lo = 0x7FFFFFFF;
            if (v1 != l1 || v2 != l2 || v3 != l3 || amp != la || off != lo || view != l6 ||
                p230 != l7 || p234 != l8 || p218 != l9 || p1e4 != l10 || p170 != l11) {
                char buf[300];
                l1 = v1; l2 = v2; l3 = v3; la = amp; lo = off; l6 = view;
                l7 = p230; l8 = p234; l9 = p218; l10 = p1e4; l11 = p170;
                unsigned f203 = base[RVA_F203] & 0xFF;
                unsigned f204 = base[RVA_F204] & 0xFF;
                wsprintfA(buf, "t=%u f0fc=%u arrA=%08X arrB=%08X amp=%d off=%d view=%u f203=%u f204=%u "
                          "g230=%08X g234=%08X g218=%08X g1e4=%08X g170=%08X",
                          tick * 3 / 10, v1, v2, v3, amp, off, view, f203, f204,
                          p230, p234, p218, p1e4, p170);
                dlg_note("%s", buf);
            }
            (void)l4; (void)l5;
            /* dump 狗数据缓冲区 0x521008 起 0x120 字节（授权检查 0x4D2ADC 用的） */
            {
                static unsigned dumped;
                unsigned char *db = base + 0x121008;
                if (!dumped && !IsBadReadPtr(db, 0x120)) {
                    unsigned char nz = 0;
                    unsigned k;
                    for (k = 0; k < 0x120; k++) if (db[k]) { nz = 1; break; }
                    if (nz) {
                        char path[MAX_PATH];
                        FILE *f;
                        dumped = 1;
                        wsprintfA(path, "%s_dogbuf.bin", g_dir);
                        f = fopen(path, "wb");
                        if (f) { fwrite(db, 1, 0x120, f); fclose(f); }
                        dlg_note("DUMP 狗缓冲区 0x521008 x0x120 -> %s", path);
                    }
                }
            }
            /* 把 0x523230 / 0x523218 两个动态数组连同长度落盘，供无狗时复刻 */
            {
                static unsigned dumped230, dumped218;
                if (p230 && p230 != dumped230 && !IsBadReadPtr((void *)p230, 8)) {
                    unsigned len = ((unsigned *)p230)[-1];
                    if (len > 0 && len < 100000 && !IsBadReadPtr((void *)p230, len * 4)) {
                        char path[MAX_PATH];
                        FILE *f;
                        dumped230 = p230;
                        wsprintfA(path, "%s_g230_%u.bin", g_dir, len);
                        f = fopen(path, "wb");
                        if (f) { fwrite((void *)p230, 1, len * 4, f); fclose(f); }
                        dlg_note("DUMP g230 len=%u ptr=%08X -> %s", len, p230, path);
                        /* 再把每个指针指向的 72 字节结构拼成一块落盘 */
                        {
                            unsigned k;
                            unsigned char *blob = (unsigned char *)calloc(1, len * 72);
                            if (blob) {
                                for (k = 0; k < len && k < 512; k++) {
                                    unsigned q = ((unsigned *)p230)[k];
                                    if (q > 0x10000u && q < 0x80000000u &&
                                        !IsBadReadPtr((void *)q, 72))
                                        memcpy(blob + k * 72, (void *)q, 72);
                                }
                                wsprintfA(path, "%s_g230ent_%u.bin", g_dir, len);
                                f = fopen(path, "wb");
                                if (f) { fwrite(blob, 1, len * 72, f); fclose(f); }
                                dlg_note("DUMP g230 实体 len=%u x72 -> %s", len, path);
                                free(blob);
                            }
                        }
                    }
                }
                if (p218 && p218 != dumped218 && !IsBadReadPtr((void *)p218, 8)) {
                    unsigned len = ((unsigned *)p218)[-1];
                    if (len > 0 && len < 100000 && !IsBadReadPtr((void *)p218, len * 4)) {
                        char path[MAX_PATH];
                        FILE *f;
                        dumped218 = p218;
                        wsprintfA(path, "%s_g218_%u.bin", g_dir, len);
                        f = fopen(path, "wb");
                        if (f) { fwrite((void *)p218, 1, len * 4, f); fclose(f); }
                        dlg_note("DUMP g218 len=%u ptr=%08X -> %s", len, p218, path);
                    }
                }
            }
        }
    }
    return 0;
}

/* ============ 导出转发 ============ */
void *g_JpgToBmp, *g_bmptotiff, *g_gettiffinfo, *g_mergtotiff;
void *g_rgbtocmykbmp, *g_savetiff00, *g_tifftobmp;

__attribute__((noinline)) void fwd_init(void)
{
    static int done;
    if (done) return;
    done = 1;
    if (!g_orig) g_orig = (HMOD)LoadLibraryA("cmyktiff2_orig.dll");
    if (!g_orig) return;
    g_JpgToBmp     = GetProcAddress((HMODULE)g_orig, "JpgToBmp");
    g_bmptotiff    = GetProcAddress((HMODULE)g_orig, "bmptotiff");
    g_gettiffinfo  = GetProcAddress((HMODULE)g_orig, "gettiffinfo");
    g_mergtotiff   = GetProcAddress((HMODULE)g_orig, "mergtotiff");
    g_rgbtocmykbmp = GetProcAddress((HMODULE)g_orig, "rgbtocmykbmp");
    g_savetiff00   = GetProcAddress((HMODULE)g_orig, "savetiff00");
    g_tifftobmp    = GetProcAddress((HMODULE)g_orig, "tifftobmp");
}

/* ---- bmptotiff 参数转储（-DDUMP_BMPTOTIFF）：stdcall / 6 个栈参 / 第 6 个是 AnsiString ---- */
typedef int (__stdcall *PF_BMP)(void *, unsigned, unsigned, unsigned, unsigned, void *);

static void dump_one(const char *tag, unsigned v)
{
    char b[400];
    int k;
    char asc[80];
    unsigned i;

    k = wsprintfA(b, "  %s=%08X", tag, v);
    /* C 字符串？ */
    if (v > 0x10000u && v < 0x80000000u && !IsBadReadPtr((void *)v, 1)) {
        const char *c = (const char *)v;
        for (i = 0; i < 60 && !IsBadReadPtr(c + i, 1) && c[i]; i++) asc[i] = c[i];
        asc[i] = 0;
        if (i >= 3 && i < 60) k += wsprintfA(b + k, "  str=\"%s\"", asc);
        /* Delphi AnsiString（长度在 +4，字符在 +8） */
        if (!IsBadReadPtr((void *)v, 12)) {
            int len = *(const int *)(c + 4);
            if (len > 0 && len < 60 && !IsBadReadPtr(c + 8, len + 1)) {
                char d[80];
                for (i = 0; i < (unsigned)len; i++) d[i] = c[8 + i];
                d[len] = 0;
                k += wsprintfA(b + k, "  ansi=\"%s\"", d);
            }
            /* 前 16 字节 hex，便于认结构体 */
            k += wsprintfA(b + k, "  hex=");
            for (i = 0; i < 16 && k < 360; i++)
                k += wsprintfA(b + k, "%02X", (unsigned char)c[i]);
        }
    }
    dlg_note("%s", b);
}

int __stdcall bmp_probe(void *a1, unsigned a2, unsigned a3, unsigned a4, unsigned a5, void *a6);
int __stdcall bmp_probe(void *a1, unsigned a2, unsigned a3, unsigned a4, unsigned a5, void *a6)
{
    void *real;
    unsigned char *base = (unsigned char *)GetModuleHandleA(NULL);
    unsigned view = *(unsigned *)(base + 0x123158);
    int amp   = (int)*(unsigned *)(base + 0x12308C);
    int offb  = (int)*(unsigned *)(base + 0x123090);
    unsigned n = *(unsigned short *)(base + 0x12315C);
    unsigned tA = *(unsigned *)(base + 0x12309C);
    unsigned tB = *(unsigned *)(base + 0x1230A0);
    char buf[240];

    fwd_init();
    real = g_bmptotiff;
    wsprintfA(buf, "bmptotiff view=%u amp=%d base=%d n=%u tblA=%08X tblB=%08X",
              view, amp, offb, n, tA, tB);
    dlg_note("%s", buf);
    dump_one("a1", (unsigned)(unsigned long)a1);
    dump_one("a2", a2);
    dump_one("a3", a3);
    dump_one("a4", a4);
    dump_one("a5", a5);
    dump_one("a6", (unsigned)(unsigned long)a6);
    /* 把 a1 当对象：逐字段列出，凡是指向可读内存的都报出该区域大小，
     * 好认出"那张 68MB 的整幅位图"藏在哪个字段里。 */
    {
        unsigned p = (unsigned)(unsigned long)a1;
        char buf[240];
        unsigned i;
        if (p > 0x10000u && p < 0x80000000u && !IsBadReadPtr((void *)p, 512)) {
            const unsigned *q = (const unsigned *)p;
            /* 第一层：64 个字段原样打出来（偏移 + 值 + 是否可读 + 区域大小） */
            for (i = 0; i < 64; i += 4) {
                unsigned a = q[i], b = q[i + 1], c = q[i + 2], d = q[i + 3];
                wsprintfA(buf, "A1[%02u..]: %08X %08X %08X %08X", i, a, b, c, d);
                dlg_note("%s", buf);
            }
            /* 第二层：只看像堆指针的字段，把被指向块的前 8 个 dword 打出来 */
            for (i = 0; i < 64; i++) {
                unsigned v = q[i];
                int k;
                if (v <= 0x10000u || v >= 0x80000000u) continue;
                if (IsBadReadPtr((void *)v, 32)) continue;
                if (v >= 0x400000u && v < 0x520000u) continue;      /* 跳过 exe 自身 */
                k = wsprintfA(buf, "  A1[%02u]=%08X ->", i, v);
                for (int j = 0; j < 8; j++)
                    k += wsprintfA(buf + k, " %08X", *(const unsigned *)(v + j * 4));
                dlg_note("%s", buf);
            }
        }
    }
    if (!real) return 0;
    return ((PF_BMP)real)(a1, a2, a3, a4, a5, a6);
}

/* ---- 7 个导出 ---- */
__declspec(dllexport) __declspec(naked) void bmptotiff(void)
{
#ifdef DUMP_BMPTOTIFF
    __asm__ __volatile__("jmp _bmp_probe");
#elif defined(NO_BMPTOTIFF)
    __asm__ __volatile__("xorl %eax, %eax\n\tret");
#else
    __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_bmptotiff");
#endif
}
__declspec(dllexport) __declspec(naked) void mergtotiff(void)
{ __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_mergtotiff"); }
__declspec(dllexport) __declspec(naked) void savetiff00(void)
{ __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_savetiff00"); }
__declspec(dllexport) __declspec(naked) void gettiffinfo(void)
{ __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_gettiffinfo"); }
__declspec(dllexport) __declspec(naked) void JpgToBmp(void)
{ __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_JpgToBmp"); }
__declspec(dllexport) __declspec(naked) void rgbtocmykbmp(void)
{ __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_rgbtocmykbmp"); }
__declspec(dllexport) __declspec(naked) void tifftobmp(void)
{ __asm__ __volatile__("pushal\n\tcall _fwd_init\n\tpopal\n\tjmp *_g_tifftobmp"); }

/* ============ 安装 ============ */
static void patch_slot(void *base, DWORD rva, void *repl)
{
    void **slot = (void **)((char *)base + rva);
    DWORD old;
    if (VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old)) {
        *slot = repl;
        VirtualProtect(slot, sizeof(void *), old, &old);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(void *));
    }
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    void *base;
    char *s;
    (void)inst; (void)reserved;
    if (reason != DLL_PROCESS_ATTACH) return TRUE;

    GetModuleFileNameA(NULL, g_dir, MAX_PATH);
    s = strrchr(g_dir, '\\');
    if (s) s[1] = 0;
    else g_dir[0] = 0;

    g_orig = (HMOD)LoadLibraryA("cmyktiff2_orig.dll");
    base = GetModuleHandleA(NULL);
    if (!base) return TRUE;

    dlg_stub_start(g_dir,
                   (void *)GetProcAddress(LoadLibraryA("comdlg32.dll"), "GetOpenFileNameA"),
                   (void *)GetProcAddress(GetModuleHandleA("comdlg32.dll"), "GetSaveFileNameA"));
    patch_slot(base, RVA_DLG_OPEN, (void *)h_dlg_open);
    patch_slot(base, RVA_DLG_SAVE, (void *)h_dlg_save);
    dlg_note("dlgonly install: orig=%p base=%p dir=%s", g_orig, base, g_dir);
    if (count_install) count_install();
    if (vwdump_install) vwdump_install();
    if (vwd2_install) vwd2_install();
    {
        char env[8];
        if (GetEnvironmentVariableA("SCAN", env, sizeof(env))) {
            HANDLE th = CreateThread(0, 0, scan_thread, 0, 0, 0);
            if (th) CloseHandle(th);
        }
    }
    return TRUE;
}
