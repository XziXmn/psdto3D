/* cmyktiff2_cap.c - full IO capture: hook CreateFileA/ReadFile/WriteFile/
   DeviceIoControl/CloseHandle/GetFileSize/SetFilePointer through the exe IAT,
   log everything, forward to the real API. Behavior unchanged.
   Build: i686-gcc -O2 -shared -static-libgcc -o cmyktiff2_cap.dll
          cmyktiff2_cap.c cmyktiff2_emu.def -luser32 -lkernel32
*/
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#define RVA_CREATEFILE_A   0x1242BC
#define RVA_CREATEFILE_A2  0x1244AC
#define RVA_DEVICEIOCTL    0x12449C
#define RVA_READFILE       0x1242A8
#define RVA_READFILE2      0x12438C
#define RVA_WRITEFILE      0x124294
#define RVA_WRITEFILE2     0x124348
#define RVA_SETFILEPTR     0x12429C
#define RVA_SETFILEPTR2    0x12436C
#define RVA_GETFILESIZE    0x1242B4
#define RVA_GETFILESIZE2   0x12443C
#define RVA_CLOSEHANDLE1   0x1242C0
#define RVA_CLOSEHANDLE2   0x1244B8

static FILE *g_log;
static CRITICAL_SECTION g_cs;
static int g_seq;
static char g_logp[MAX_PATH];

static void lograw(const char *s, const unsigned char *d, DWORD n)
{
    DWORD i;
    DWORD lim = n > 512 ? 512 : n;
    fprintf(g_log, "%s[%lu]=", s, (unsigned long)n);
    for (i = 0; i < lim; i++) fprintf(g_log, "%02X", d[i]);
    if (n > lim) fprintf(g_log, "...(%lu more)", (unsigned long)(n - lim));
    fputc('\n', g_log);
}

static void note(const char *fmt, ...)
{
    va_list ap;
    char buf[2048];
    if (!g_logp[0]) {
        GetModuleFileNameA(NULL, g_logp, MAX_PATH);
        {
            char *s = strrchr(g_logp, '\\');
            if (s) s[1] = 0;
            lstrcatA(g_logp, "_capture.log");
        }
    }
    g_log = fopen(g_logp, "a");
    if (!g_log) return;
    fprintf(g_log, "#%d ", ++g_seq);
    va_start(ap, fmt);
    vsprintf(buf, fmt, ap);
    va_end(ap);
    fputs(buf, g_log);
    fputc('\n', g_log);
    fclose(g_log);
}

typedef HANDLE (WINAPI *PF_CFA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef BOOL  (WINAPI *PF_RF)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL  (WINAPI *PF_WF)(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL  (WINAPI *PF_DIO)(HANDLE, DWORD, LPVOID, DWORD, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL  (WINAPI *PF_CH)(HANDLE);
typedef DWORD (WINAPI *PF_GFS)(HANDLE, LPDWORD);
typedef DWORD (WINAPI *PF_SFP)(HANDLE, LONG, PLONG, DWORD);

static PF_CFA  o_cfa;
static PF_RF   o_rf;
static PF_WF   o_wf;
static PF_DIO  o_dio;
static PF_CH   o_ch;
static PF_GFS  o_gfs;
static PF_SFP  o_sfp;

static HANDLE WINAPI e_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                           DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE h = o_cfa(name, acc, share, sa, disp, flags, tmpl);
    note("OPEN \"%s\" acc=%08X -> %p", name ? name : "(null)", acc, h);
    return h;
}

static BOOL WINAPI e_rf(HANDLE h, LPVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL ok = o_rf(h, buf, n, got, ov);
    EnterCriticalSection(&g_cs);
    g_log = fopen(g_logp, "a");
    if (g_log) {
        fprintf(g_log, "#%d RF h=%p n=%lu ok=%d got=%lu\n", ++g_seq, h, (unsigned long)n, ok, got ? *got : 0);
        if (ok && got && *got) lograw("RFDATA", (const unsigned char *)buf, *got);
        fclose(g_log);
        g_log = NULL;
    }
    LeaveCriticalSection(&g_cs);
    return ok;
}

static BOOL WINAPI e_wf(HANDLE h, LPCVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL ok = o_wf(h, buf, n, got, ov);
    EnterCriticalSection(&g_cs);
    g_log = fopen(g_logp, "a");
    if (g_log) {
        fprintf(g_log, "#%d WF h=%p n=%lu ok=%d got=%lu\n", ++g_seq, h, (unsigned long)n, ok, got ? *got : 0);
        if (n) lograw("WFDATA", (const unsigned char *)buf, n);
        fclose(g_log);
        g_log = NULL;
    }
    LeaveCriticalSection(&g_cs);
    return ok;
}

static BOOL WINAPI e_dio(HANDLE h, DWORD code, LPVOID in, DWORD inlen, LPVOID out, DWORD outlen,
                         LPDWORD ret, LPOVERLAPPED ov)
{
    unsigned char *sptp = (unsigned char *)in;
    unsigned char sptop = 0;
    unsigned sptaddr = 0, sptdtl = 0;
    void *sptbuf = NULL;
    int is_spt = 0;
    if (in && inlen >= 0x2C && *(unsigned short *)in == 0x002C) {
        sptop = sptp[28];
        sptaddr = sptp[30] | (sptp[31] << 8);
        sptdtl = *(unsigned *)&sptp[12];
        sptbuf = *(void **)&sptp[20];
        if (sptbuf && sptdtl && sptdtl < 0x100000) is_spt = 1;
    }
    if (is_spt && sptop == 0xDD) {
        EnterCriticalSection(&g_cs);
        g_log = fopen(g_logp, "a");
        if (g_log) {
            fprintf(g_log, "#%d SPTWR addr=%04X len=%lu\n", ++g_seq, sptaddr, (unsigned long)sptdtl);
            lograw("SPTWRDATA", (const unsigned char *)sptbuf, sptdtl > 4096 ? 4096 : sptdtl);
            fclose(g_log);
            g_log = NULL;
        }
        LeaveCriticalSection(&g_cs);
    }
    BOOL ok = o_dio(h, code, in, inlen, out, outlen, ret, ov);
    EnterCriticalSection(&g_cs);
    g_log = fopen(g_logp, "a");
    if (g_log) {
        fprintf(g_log, "#%d DIO h=%p code=%08X inlen=%lu outlen=%lu ok=%d ret=%lu\n",
                ++g_seq, h, code, (unsigned long)inlen, (unsigned long)outlen, ok,
                ret ? *ret : 0);
        if (in && inlen) lograw("IN", (const unsigned char *)in, inlen);
        if (ok && out && outlen) lograw("OUT", (const unsigned char *)out, outlen);
        if (is_spt && sptop == 0xD1 && sptbuf && sptdtl) {
            unsigned lim = sptdtl < 4096 ? sptdtl : 4096;
            fprintf(g_log, "#%d SPTRE addr=%04X len=%lu\n", ++g_seq, sptaddr, (unsigned long)sptdtl);
            lograw("SPTREDATA", (const unsigned char *)sptbuf, lim);
        }
        fclose(g_log);
        g_log = NULL;
    }
    LeaveCriticalSection(&g_cs);
    return ok;
}

static BOOL WINAPI e_ch(HANDLE h)
{
    BOOL ok = o_ch(h);
    note("CLOSE h=%p ok=%d", h, ok);
    return ok;
}

static DWORD WINAPI e_gfs(HANDLE h, LPDWORD hi)
{
    DWORD r = o_gfs(h, hi);
    note("GETFILESIZE h=%p -> %lu hi=%ld", h, (unsigned long)r, hi ? *hi : -1);
    return r;
}

static DWORD WINAPI e_sfp(HANDLE h, LONG lo, PLONG hi, DWORD method)
{
    DWORD r = o_sfp(h, lo, hi, method);
    note("SETFILEPTR h=%p lo=%ld method=%lu -> %lu", h, lo, (unsigned long)method, (unsigned long)r);
    return r;
}

static void patch_slot(void *base, DWORD rva, void *repl, void **save)
{
    void **slot = (void **)((char *)base + rva);
    DWORD old;
    VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old);
    *save = *slot;
    *slot = repl;
    FlushInstructionCache(GetCurrentProcess(), slot, 4);
    VirtualProtect(slot, 4, old, &old);
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved)
{
    void *base;
    if (reason != DLL_PROCESS_ATTACH) return TRUE;
    InitializeCriticalSection(&g_cs);
    GetModuleFileNameA(NULL, g_logp, MAX_PATH);
    {
        char *s = strrchr(g_logp, '\\');
        if (s) s[1] = 0;
        lstrcatA(g_logp, "_capture.log");
    }
    base = GetModuleHandleA(NULL);
    if (!base) return TRUE;
    patch_slot(base, RVA_CREATEFILE_A,  (void *)e_cfa, (void **)&o_cfa);
    patch_slot(base, RVA_CREATEFILE_A2, (void *)e_cfa, (void **)&o_cfa);
    patch_slot(base, RVA_READFILE,      (void *)e_rf,  (void **)&o_rf);
    patch_slot(base, RVA_READFILE2,     (void *)e_rf,  (void **)&o_rf);
    patch_slot(base, RVA_WRITEFILE,     (void *)e_wf,  (void **)&o_wf);
    patch_slot(base, RVA_WRITEFILE2,    (void *)e_wf,  (void **)&o_wf);
    patch_slot(base, RVA_DEVICEIOCTL,   (void *)e_dio, (void **)&o_dio);
    patch_slot(base, RVA_CLOSEHANDLE1,  (void *)e_ch,  (void **)&o_ch);
    patch_slot(base, RVA_CLOSEHANDLE2,  (void *)e_ch,  (void **)&o_ch);
    patch_slot(base, RVA_GETFILESIZE,   (void *)e_gfs, (void **)&o_gfs);
    patch_slot(base, RVA_GETFILESIZE2,  (void *)e_gfs, (void **)&o_gfs);
    patch_slot(base, RVA_SETFILEPTR,    (void *)e_sfp, (void **)&o_sfp);
    patch_slot(base, RVA_SETFILEPTR2,   (void *)e_sfp, (void **)&o_sfp);
    note("--- capture installed base=%p ---", base);
    return TRUE;
}
