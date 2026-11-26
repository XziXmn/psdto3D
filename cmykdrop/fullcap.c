/* fullcap.c —— 只记录、不改行为的抓包 DLL
 *
 * 用途：插着真狗跑一次，把所有经过设备句柄的调用原样记下来，
 *       用来找出我们的仿真器漏掉了哪些底层请求。
 *
 * 导出 7 个 cmyktiff2 函数，全部转发到 cmyktiff2_real.dll。
 * 同时 IAT hook 住 kernel32 的 CreateFileA / DeviceIoControl /
 * ReadFile / WriteFile / CloseHandle，只记录参数，返回值原样透传。
 */
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>

#define LOGMAX 2000
static char g_dir[MAX_PATH];
static CRITICAL_SECTION g_cs;
static int g_cs_ok;
static HMODULE g_real;

static void lg(const char *fmt, ...)
{
    char buf[LOGMAX];
    char path[MAX_PATH];
    va_list ap;
    FILE *f;
    if (!g_cs_ok) return;
    va_start(ap, fmt);
    vsnprintf(buf, LOGMAX - 2, fmt, ap);
    va_end(ap);
    buf[LOGMAX - 2] = 0;
    EnterCriticalSection(&g_cs);
    lstrcpynA(path, g_dir, MAX_PATH - 20);
    lstrcatA(path, "_fullcap.log");
    f = fopen(path, "a");
    if (f) {
        fputs(buf, f);
        fputc('\n', f);
        fclose(f);
    }
    LeaveCriticalSection(&g_cs);
}

static void hexstr(const unsigned char *p, unsigned n, char *out, unsigned outsz)
{
    unsigned i, o = 0;
    if (!p) { lstrcpynA(out, "-", outsz); return; }
    for (i = 0; i < n && o + 3 < outsz; i++) {
        wsprintfA(out + o, "%02X", p[i]);
        o += 2;
    }
    out[o] = 0;
}

/* ---------------- hooks ---------------- */
typedef HANDLE (WINAPI *PF_CFA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef BOOL (WINAPI *PF_DIO)(HANDLE, DWORD, LPVOID, DWORD, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_RF)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_WF)(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_CH)(HANDLE);

static PF_CFA o_cfa;
static PF_DIO o_dio;
static PF_RF  o_rf;
static PF_WF  o_wf;
static PF_CH  o_ch;

static HANDLE g_dev[16];
static int g_ndev;

static int is_dev(HANDLE h)
{
    int i;
    for (i = 0; i < g_ndev; i++) if (g_dev[i] == h) return 1;
    return 0;
}

static void add_dev(HANDLE h)
{
    if (g_ndev < 16) g_dev[g_ndev++] = h;
}

static HANDLE WINAPI h_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                           DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE h = o_cfa(name, acc, share, sa, disp, flags, tmpl);
    int isdev = 0;
    if (name) {
        if (name[0] == '\\' && name[1] == '\\') isdev = 1;
        if (lstrlenA(name) > 3 && name[1] == ':' && name[2] == '\\') isdev = 0;
    }
    lg("CFA %s h=%p acc=%08lX share=%08lX disp=%lu flags=%08lX dev=%d",
       name ? name : "(null)", h, (unsigned long)acc, (unsigned long)share,
       (unsigned long)disp, (unsigned long)flags, isdev);
    if (h != INVALID_HANDLE_VALUE && isdev) add_dev(h);
    return h;
}

static BOOL WINAPI h_dio(HANDLE h, DWORD code, LPVOID in, DWORD insz,
                         LPVOID out, DWORD outsz, LPDWORD ret, LPOVERLAPPED ov)
{
    BOOL r = o_dio(h, code, in, insz, out, outsz, ret, ov);
    char hi[220], ho[220];
    if (is_dev(h) || (code & 0x8000)) {
        hexstr((unsigned char *)in, insz > 48 ? 48 : insz, hi, sizeof(hi));
        hexstr((unsigned char *)out, outsz > 48 ? 48 : outsz, ho, sizeof(ho));
        lg("DIO h=%p ioctl=%08lX in=%lu out=%lu ok=%d ret=%lu IN=%s OUT=%s",
           h, (unsigned long)code, (unsigned long)insz, (unsigned long)outsz,
           (int)r, (unsigned long)(ret ? *ret : 0), hi, ho);
    }
    return r;
}

static BOOL WINAPI h_rf(HANDLE h, LPVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL r = o_rf(h, buf, n, got, ov);
    if (is_dev(h)) {
        char hb[220];
        hexstr((unsigned char *)buf, (got && *got) ? (*got > 48 ? 48 : *got) : 0, hb, sizeof(hb));
        lg("RF  h=%p ask=%lu got=%lu ok=%d BUF=%s", h, (unsigned long)n,
           (unsigned long)(got ? *got : 0), (int)r, hb);
    }
    return r;
}

static BOOL WINAPI h_wf(HANDLE h, LPCVOID buf, DWORD n, LPDWORD wrote, LPOVERLAPPED ov)
{
    BOOL r = o_wf(h, buf, n, wrote, ov);
    if (is_dev(h)) {
        char hb[220];
        hexstr((const unsigned char *)buf, n > 48 ? 48 : n, hb, sizeof(hb));
        lg("WF  h=%p n=%lu ok=%d BUF=%s", h, (unsigned long)n, (int)r, hb);
    }
    return r;
}

static BOOL WINAPI h_ch(HANDLE h)
{
    BOOL r = o_ch(h);
    if (is_dev(h)) lg("CLS h=%p ok=%d", h, (int)r);
    return r;
}

/* ---------------- IAT 安装 ---------------- */
static void patch_iat(HMODULE mod, const char *dllname, const char *fn,
                      void *newfn, void **orig)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)mod;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    nt = (IMAGE_NT_HEADERS *)((char *)mod + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;
    imp = (IMAGE_IMPORT_DESCRIPTOR *)((char *)mod +
          nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    if (!imp || !nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress) return;

    for (; imp->Name; imp++) {
        IMAGE_THUNK_DATA *thunk, *nameThunk;
        const char *dn = (const char *)mod + imp->Name;
        if (lstrcmpiA(dn, dllname) != 0) continue;
        thunk = (IMAGE_THUNK_DATA *)((char *)mod + imp->FirstThunk);
        nameThunk = (IMAGE_THUNK_DATA *)((char *)mod + imp->OriginalFirstThunk);
        for (;; thunk++, nameThunk++) {
            void **slot;
            const char *fnname = 0;
            DWORD old;
            LPVOID addr = (LPVOID)(SIZE_T)thunk->u1.Function;
            if (!addr) break;
            if (nameThunk && nameThunk->u1.AddressOfData)
                fnname = (const char *)mod + nameThunk->u1.AddressOfData + 2;
            if (!fnname) continue;
            if (lstrcmpiA(fnname, fn) != 0) continue;
            slot = (void **)&thunk->u1.Function;
            if (!*orig) *orig = addr;
            if (VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old)) {
                *slot = newfn;
                VirtualProtect(slot, sizeof(void *), old, &old);
                lg("IAT %s!%s patched in %s", dllname, fn, dn);
            }
            return;
        }
    }
}

static void install_all(void)
{
    static const char *names[] = {
        0, "zu06.dll", "rip3d.dll", "cmyktiff2_real.dll", "cmyktiff2.dll",
        "ok3d.dll", "ok3d1.dll", "ok3d4.dll", "zu6.dll", "3d.dll", "8602.dll",
        "cmyk.dll", "cmyktiff.dll", "exe3d.dll", "save3d.dll", "dspr.dll", 0
    };
    int i;
    HMODULE list[32];
    int n = 0;
    list[n++] = GetModuleHandleA(NULL);
    for (i = 0; names[i]; i++) {
        HMODULE h = GetModuleHandleA(names[i]);
        if (h && n < 32) list[n++] = h;
    }
    for (i = 0; i < n; i++) {
        char mod[MAX_PATH];
        GetModuleFileNameA(list[i], mod, MAX_PATH);
        patch_iat(list[i], "kernel32.dll", "CreateFileA", (void *)h_cfa, (void **)&o_cfa);
        patch_iat(list[i], "kernel32.dll", "DeviceIoControl", (void *)h_dio, (void **)&o_dio);
        patch_iat(list[i], "kernel32.dll", "ReadFile", (void *)h_rf, (void **)&o_rf);
        patch_iat(list[i], "kernel32.dll", "WriteFile", (void *)h_wf, (void **)&o_wf);
        patch_iat(list[i], "kernel32.dll", "CloseHandle", (void *)h_ch, (void **)&o_ch);
    }
    if (!o_cfa) o_cfa = (PF_CFA)GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateFileA");
    if (!o_dio) o_dio = (PF_DIO)GetProcAddress(GetModuleHandleA("kernel32.dll"), "DeviceIoControl");
    if (!o_rf) o_rf = (PF_RF)GetProcAddress(GetModuleHandleA("kernel32.dll"), "ReadFile");
    if (!o_wf) o_wf = (PF_WF)GetProcAddress(GetModuleHandleA("kernel32.dll"), "WriteFile");
    if (!o_ch) o_ch = (PF_CH)GetProcAddress(GetModuleHandleA("kernel32.dll"), "CloseHandle");
}

static DWORD WINAPI starter(LPVOID p)
{
    int i;
    (void)p;
    for (i = 0; i < 40; i++) {
        Sleep(250);
        install_all();
    }
    lg("starter done");
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE hi, DWORD reason, LPVOID res)
{
    (void)hi; (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        char *p;
        GetModuleFileNameA(hi, g_dir, MAX_PATH);
        p = g_dir;
        while (*p) p++;
        while (p > g_dir && *p != '\\') p--;
        if (p > g_dir) p[1] = 0;
        InitializeCriticalSection(&g_cs);
        g_cs_ok = 1;
        DisableThreadLibraryCalls(hi);
        lg("=== fullcap start dir=%s", g_dir);
        CloseHandle(CreateThread(0, 0, starter, 0, 0, 0));
    }
    return TRUE;
}
