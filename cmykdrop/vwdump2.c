/* 安全版 vw 写盘观测：只 hook 指定的两个模块，且延迟到主窗口出现后。
 *
 * 上一版教训：在 DllMain 里给所有模块打 IAT hook，把 exe 启动搞坏了
 * （main window did not appear）。这版：
 *   1) 只处理 cmyktiff1.dll / ok3d.dll 两个模块
 *   2) 由后台线程等主窗口出现后才挂
 *   3) 只替换 IAT 槽，不碰 kernel32 代码、不碰 exe
 *
 * 环境变量 VWD2=1 启用。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* Toolhelp 声明（mingw32 头不全） */
typedef struct { DWORD dwSize, th32ModuleID, th32ProcessID, GlblcntUsage,
                 ProccntUsage; BYTE *modBaseAddr; DWORD modBaseSize;
                 HMODULE hModule; char szModule[256]; char szExePath[260]; } MODENTRY;
HANDLE WINAPI CreateToolhelp32Snapshot(DWORD, DWORD);
BOOL WINAPI Module32First(HANDLE, MODENTRY *);
BOOL WINAPI Module32Next(HANDLE, MODENTRY *);
typedef HANDLE (WINAPI *PF_CFA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef BOOL   (WINAPI *PF_WF)(HANDLE, LPCVOID, DWORD, LPDWORD);

static PF_CFA  s_cfa;
static PF_WF   s_wf;
static FILE   *g_f;
static HANDLE  g_h[256];
static char    g_n[256][192];
static int     g_nh;
static volatile int g_on;
static CRITICAL_SECTION g_cs;
static DWORD   g_seq;

static int is_view(const char *p)
{
    const char *s;
    if (!p) return 0;
    s = strrchr(p, '\\');
    s = s ? s + 1 : p;
    return (s[0] == 'v' && s[1] == 'w');
}

static HANDLE WINAPI h_cfa(LPCSTR name, DWORD access, DWORD share,
                           LPSECURITY_ATTRIBUTES sa, DWORD disp,
                           DWORD flags, HANDLE tmpl)
{
    HANDLE h = s_cfa(name, access, share, sa, disp, flags, tmpl);
    if (g_on && is_view(name) && h != INVALID_HANDLE_VALUE && g_nh < 256) {
        g_h[g_nh] = h;
        strncpy(g_n[g_nh], name, 191);
        g_n[g_nh][191] = 0;
        g_nh++;
        EnterCriticalSection(&g_cs);
        fprintf(g_f, "OPEN %s -> %p\n", name, h);
        fflush(g_f);
        LeaveCriticalSection(&g_cs);
    }
    return h;
}

static BOOL WINAPI h_wf(HANDLE h, LPCVOID buf, DWORD n, LPDWORD wrote)
{
    BOOL r = s_wf(h, buf, n, wrote);
    if (g_on) {
        int i;
        for (i = 0; i < g_nh; i++) {
            if (g_h[i] == h) {
                const unsigned char *p = (const unsigned char *)buf;
                unsigned k, lim = n < 64 ? n : 64;
                EnterCriticalSection(&g_cs);
                fprintf(g_f, "WRITE %s seq=%lu n=%lu head=", g_n[i],
                        (unsigned long)++g_seq, (unsigned long)n);
                for (k = 0; k < lim; k++) fprintf(g_f, "%02X", p[k]);
                fprintf(g_f, "\n");
                fflush(g_f);
                LeaveCriticalSection(&g_cs);
                break;
            }
        }
    }
    return r;
}

static int patch_iat_of(HMODULE mod, const char *want_mod)
{
    PIMAGE_DOS_HEADER dos;
    PIMAGE_NT_HEADERS nt;
    PIMAGE_IMPORT_DESCRIPTOR imp;
    int npatched = 0;
    if (!mod) return 0;
    dos = (PIMAGE_DOS_HEADER)mod;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (PIMAGE_NT_HEADERS)((char *)mod + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;
    imp = (PIMAGE_IMPORT_DESCRIPTOR)((char *)mod +
          nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    if (!imp) return 0;
    for (; imp->Name; imp++) {
        PIMAGE_THUNK_DATA thunk, iat;
        thunk = (PIMAGE_THUNK_DATA)((char *)mod + imp->OriginalFirstThunk);
        iat   = (PIMAGE_THUNK_DATA)((char *)mod + imp->FirstThunk);
        if (!thunk) thunk = iat;
        for (; thunk->u1.AddressOfData; thunk++, iat++) {
            PIMAGE_IMPORT_BY_NAME nb;
            DWORD old;
            if (thunk->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;
            nb = (PIMAGE_IMPORT_BY_NAME)((char *)mod + thunk->u1.AddressOfData);
            if (!strcmp((char *)nb->Name, "CreateFileA")) {
                if (VirtualProtect(&iat->u1.Function, 4, PAGE_READWRITE, &old)) {
                    iat->u1.Function = (ULONG_PTR)h_cfa;
                    VirtualProtect(&iat->u1.Function, 4, old, &old);
                    npatched++;
                }
            } else if (!strcmp((char *)nb->Name, "WriteFile")) {
                if (VirtualProtect(&iat->u1.Function, 4, PAGE_READWRITE, &old)) {
                    iat->u1.Function = (ULONG_PTR)h_wf;
                    VirtualProtect(&iat->u1.Function, 4, old, &old);
                    npatched++;
                }
            }
        }
    }
    if (npatched) {
        fprintf(g_f, "patched %s (%d 槽)\n", want_mod, npatched);
        fflush(g_f);
    }
    return npatched;
}

static DWORD WINAPI install_thread(LPVOID p)
{
    int tries;
    (void)p;
    /* 等主窗口出现，避免干扰 exe 启动 */
    for (tries = 0; tries < 600; tries++) {
        if (FindWindowA("TForm1", NULL)) break;
        Sleep(100);
    }
    Sleep(200);
    g_on = 1;
    /* 反复挂：预览期间可能动态加载新模块 */
    {
        int round;
        for (round = 0; round < 400; round++) {
            HMODULE mods[512];
            DWORD need = 0;
            HANDLE snap = CreateToolhelp32Snapshot(0x8 | 0x2, GetCurrentProcessId());
            MODENTRY me;
            if (snap != INVALID_HANDLE_VALUE) {
                me.dwSize = sizeof(me);
                if (Module32First(snap, &me)) {
                    do {
                        patch_iat_of((HMODULE)me.modBaseAddr, me.szModule);
                    } while (Module32Next(snap, &me));
                }
                CloseHandle(snap);
            }
            (void)mods; (void)need;
            Sleep(250);
        }
    }
    fprintf(g_f, "安装线程结束\n");
    fflush(g_f);
    return 0;
}

void vwd2_install(void)
{
    char env[8], path[MAX_PATH];
    HMODULE k32;
    HANDLE th;
    if (!GetEnvironmentVariableA("VWD2", env, sizeof(env))) return;
    GetModuleFileNameA(NULL, path, MAX_PATH);
    { char *s = strrchr(path, 92); if (s) s[1] = 0; }
    strcat(path, "_vwd2.log");
    g_f = fopen(path, "w");
    if (!g_f) return;
    InitializeCriticalSection(&g_cs);
    k32 = GetModuleHandleA("kernel32.dll");
    s_cfa = (PF_CFA)GetProcAddress(k32, "CreateFileA");
    s_wf  = (PF_WF)GetProcAddress(k32, "WriteFile");
    fprintf(g_f, "VWD2 就绪 cfa=%p wf=%p（等主窗口）\n", (void *)s_cfa, (void *)s_wf);
    fflush(g_f);
    th = CreateThread(0, 0, install_thread, 0, 0, 0);
    if (th) CloseHandle(th);
}
