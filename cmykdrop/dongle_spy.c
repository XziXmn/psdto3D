/* 加密狗流量记录器：在 exe 的 IAT 里把 CreateFileA / DeviceIoControl /
 * ReadFile / WriteFile 换成自己的入口，把对 \\.\MyUSBKey 的每一次调用
 * 原样记下来（含命令码、入缓冲、出缓冲），供后续做回放。
 *
 * 必须在 DllMain 里安装：授权检查发生在 exe 启动阶段，晚于此就抓不到。
 * 只改 exe 的 IAT 槽（RVA 见下），不动 DLL 的 IAT，也不 inline hook。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#define RVA_CREATEFILE_A   0x1242BC
#define RVA_CREATEFILE_A2  0x1244AC
#define RVA_DEVICEIOCTL    0x12449C
#define RVA_READFILE       0x1242A8
#define RVA_READFILE2      0x12438C
#define RVA_WRITEFILE      0x124294
#define RVA_WRITEFILE2     0x124348

typedef HANDLE (WINAPI *PF_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                        DWORD, DWORD, HANDLE);
typedef BOOL (WINAPI *PF_DeviceIoControl)(HANDLE, DWORD, LPVOID, DWORD, LPVOID,
                                          DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_ReadFile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_WriteFile)(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);

static PF_CreateFileA    o_cfa;
static PF_DeviceIoControl o_dio;
static PF_ReadFile        o_rf;
static PF_WriteFile       o_wf;
static HANDLE             g_dev = INVALID_HANDLE_VALUE;
static char               g_log[MAX_PATH];
static volatile LONG      g_done;

static FILE *LF(void)
{
    char p[MAX_PATH], *s;
    if (!g_log[0]) {
        GetModuleFileNameA(NULL, p, MAX_PATH);
        s = strrchr(p, '\\');
        if (s) s[1] = 0;
        lstrcpyA(g_log, p);
        lstrcatA(g_log, "_dongle.log");
    }
    return fopen(g_log, "a");
}

static void loghex(FILE *f, const char *tag, const void *p, DWORD n)
{
    const unsigned char *b = (const unsigned char *)p;
    DWORD i;
    if (!p) { fprintf(f, " %s=NULL", tag); return; }
    fprintf(f, " %s[%u]=", tag, n);
    if (IsBadReadPtr(b, n ? n : 1)) { fprintf(f, "<unreadable>"); return; }
    for (i = 0; i < n && i < 512; i++) fprintf(f, "%02X", b[i]);
    if (n > 512) fprintf(f, "...");
}

static HANDLE WINAPI h_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                           DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE h = o_cfa ? o_cfa(name, acc, share, sa, disp, flags, tmpl) : INVALID_HANDLE_VALUE;
    if (name && (strstr(name, "USBKey") || strstr(name, "usbstor") || strstr(name, "hid#vid"))) {
        FILE *f = LF();
        g_dev = h;
        if (f) { fprintf(f, "OPEN %s acc=0x%X share=0x%X disp=%u -> %p\n",
                         name, acc, share, disp, h); fclose(f); }
    }
    return h;
}

static BOOL WINAPI h_dio(HANDLE h, DWORD code, LPVOID in, DWORD inlen, LPVOID out,
                         DWORD outlen, LPDWORD ret, LPOVERLAPPED ov)
{
    BOOL ok = o_dio ? o_dio(h, code, in, inlen, out, outlen, ret, ov) : FALSE;
    if (h == g_dev || (g_dev == INVALID_HANDLE_VALUE)) {
        FILE *f = LF();
        if (f) {
            fprintf(f, "IOCTL code=0x%08X inlen=%u outlen=%u ok=%d ret=%u",
                    code, inlen, outlen, ok, ret ? *ret : 0);
            loghex(f, "hdr", in, inlen < 96 ? inlen : 96);
            fputc('\n', f);
            /* 若像 SCSI_PASS_THROUGH(_DIRECT)，把 CDB 和数据缓冲也打出来 */
            if (in && inlen >= 40 && *(unsigned short *)in == 0x002C) {
                const unsigned char *p = (const unsigned char *)in;
                unsigned cdb_len = p[6], data_in = p[8];
                unsigned dtl = *(const unsigned *)&p[12];
                unsigned timeout = *(const unsigned *)&p[16];
                void *dbuf = *(void *const *)&p[20];
                fprintf(f, "  SCSI cdb[%u]=", cdb_len);
                {
                    unsigned i;
                    for (i = 0; i < cdb_len && 28 + i < inlen; i++) fprintf(f, "%02X", p[28 + i]);
                }
                fprintf(f, " dtl=%u dash=%u timeout=%u dbuf=%p",
                        dtl, data_in, timeout, dbuf);
                if (dbuf && dtl && !IsBadReadPtr(dbuf, dtl)) {
                    fprintf(f, " data=");
                    {
                        unsigned i;
                        for (i = 0; i < dtl && i < 1024; i++) fprintf(f, "%02X", ((unsigned char *)dbuf)[i]);
                    }
                }
                fputc('\n', f);
            }
            fclose(f);
        }
    }
    return ok;
}

static BOOL WINAPI h_rf(HANDLE h, LPVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL ok = o_rf ? o_rf(h, buf, n, got, ov) : FALSE;
    if (h == g_dev) {
        FILE *f = LF();
        if (f) { fprintf(f, "READ  want=%u ok=%d got=%u", n, ok, got ? *got : 0);
                 loghex(f, "buf", buf, got ? *got : 0); fputc('\n', f); fclose(f); }
    }
    return ok;
}

static BOOL WINAPI h_wf(HANDLE h, LPCVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL ok = o_wf ? o_wf(h, buf, n, got, ov) : FALSE;
    if (h == g_dev) {
        FILE *f = LF();
        if (f) { fprintf(f, "WRITE n=%u ok=%d got=%u", n, ok, got ? *got : 0);
                 loghex(f, "buf", buf, n); fputc('\n', f); fclose(f); }
    }
    return ok;
}

static void patch_slot(void *base, DWORD rva, void *repl, void **save)
{
    void **slot = (void **)((char *)base + rva);
    DWORD old;
    if (*save == NULL) *save = *slot;
    if (VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old)) {
        *slot = repl;
        VirtualProtect(slot, sizeof(void *), old, &old);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(void *));
    }
}

void dongle_spy_install(void)
{
    void *base;
    if (InterlockedExchange(&g_done, 1)) return;
    base = GetModuleHandleA(NULL);
    if (!base) return;
    patch_slot(base, RVA_CREATEFILE_A,  (void *)h_cfa, (void **)&o_cfa);
    patch_slot(base, RVA_CREATEFILE_A2, (void *)h_cfa, (void **)&o_cfa);
    patch_slot(base, RVA_DEVICEIOCTL,   (void *)h_dio, (void **)&o_dio);
    patch_slot(base, RVA_READFILE,      (void *)h_rf,  (void **)&o_rf);
    patch_slot(base, RVA_READFILE2,     (void *)h_rf,  (void **)&o_rf);
    patch_slot(base, RVA_WRITEFILE,     (void *)h_wf,  (void **)&o_wf);
    patch_slot(base, RVA_WRITEFILE2,    (void *)h_wf,  (void **)&o_wf);
    if (o_cfa && o_dio) {
        FILE *f = LF();
        if (f) { fprintf(f, "--- hooks installed (base=%p) ---\n", base); fclose(f); }
    }
}
