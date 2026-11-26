/* 观测 vw*.bmp 的写盘内容：IAT hook 方式（安全，不改 kernel32 代码）。
 *
 * 为什么：gx 切片带狗/无狗逐字节全同，渲染函数、入口全局、off 写入也都一致，
 * 但 vw*.bmp 有对称差异（vw6 全同，两侧 4.5~10.4）。
 * 唯一剩下的位置是 cmyktiff1.dll / ok3d.dll 把像素写到磁盘这一步。
 *
 * 做法：遍历所有已加载模块的导入表，把 CreateFileA / WriteFile 的槽
 * 替换成我们的函数；命中 vw*.bmp 句柄时 dump 缓冲区。
 *
 * 环境变量 VWDUMP=1 启用。日志写在 exe 同目录 _vwdump.log。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* 用 Toolhelp 枚举模块，避免依赖 psapi */
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
static HANDLE  g_handles[128];
static char    g_names[128][160];
static int     g_nh;
static int     g_on;
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
    if (g_on && is_view(name) && h != INVALID_HANDLE_VALUE && g_nh < 128) {
        g_handles[g_nh] = h;
        strncpy(g_names[g_nh], name, 159);
        g_names[g_nh][159] = 0;
        g_nh++;
        fprintf(g_f, "OPEN %s -> %p\n", name, h);
        fflush(g_f);
    }
    return h;
}

static BOOL WINAPI h_wf(HANDLE h, LPCVOID buf, DWORD n, LPDWORD wrote)
{
    BOOL r = s_wf(h, buf, n, wrote);
    if (g_on) {
        int i;
        for (i = 0; i < g_nh; i++) {
            if (g_handles[i] == h) {
                const unsigned char *p = (const unsigned char *)buf;
                unsigned k, lim = n < 64 ? n : 64;
                fprintf(g_f, "WRITE %s seq=%lu n=%lu head=", g_names[i],
                        (unsigned long)++g_seq, (unsigned long)n);
                for (k = 0; k < lim; k++) fprintf(g_f, "%02X", p[k]);
                fprintf(g_f, "\n");
                fflush(g_f);
                break;
            }
        }
    }
    return r;
}

/* 遍历一个模块的导入表，替换匹配的函数指针 */
static void patch_module_iat(HMODULE mod, PF_CFA fake_cfa, PF_WF fake_wf)
{
    PIMAGE_DOS_HEADER dos;
    PIMAGE_NT_HEADERS nt;
    PIMAGE_IMPORT_DESCRIPTOR imp;
    if (!mod) return;
    dos = (PIMAGE_DOS_HEADER)mod;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    nt = (PIMAGE_NT_HEADERS)((char *)mod + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;
    imp = (PIMAGE_IMPORT_DESCRIPTOR)((char *)mod +
          nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    if (!imp) return;
    for (; imp->Name; imp++) {
        PIMAGE_THUNK_DATA thunk;
        PIMAGE_THUNK_DATA iat;
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
                    iat->u1.Function = (ULONG_PTR)fake_cfa;
                    VirtualProtect(&iat->u1.Function, 4, old, &old);
                    fprintf(g_f, "  patch CreateFileA in %s\n", (char *)mod);
                }
            } else if (!strcmp((char *)nb->Name, "WriteFile")) {
                if (VirtualProtect(&iat->u1.Function, 4, PAGE_READWRITE, &old)) {
                    iat->u1.Function = (ULONG_PTR)fake_wf;
                    VirtualProtect(&iat->u1.Function, 4, old, &old);
                    fprintf(g_f, "  patch WriteFile in %s\n", (char *)mod);
                }
            }
        }
    }
    fflush(g_f);
}

void vwdump_install(void)
{
    char env[16], path[MAX_PATH];
    HMODULE k32;
    HMODULE mods[256];
    DWORD need = 0, i, n;
    if (!GetEnvironmentVariableA("VWDUMP", env, sizeof(env))) return;
    GetModuleFileNameA(NULL, path, MAX_PATH);
    { char *s = strrchr(path, 92); if (s) s[1] = 0; }
    strcat(path, "_vwdump.log");
    g_f = fopen(path, "w");
    if (!g_f) return;
    g_on = 1;
    k32 = GetModuleHandleA("kernel32.dll");
    s_cfa = (PF_CFA)GetProcAddress(k32, "CreateFileA");
    s_wf  = (PF_WF)GetProcAddress(k32, "WriteFile");
    fprintf(g_f, "VWDUMP 安装 cfa=%p wf=%p\n", (void *)s_cfa, (void *)s_wf);
    fflush(g_f);

    {
        HANDLE snap = CreateToolhelp32Snapshot(0x00000008 | 0x00000002, GetCurrentProcessId());
        MODENTRY me;
        n = 0;
        if (snap != INVALID_HANDLE_VALUE) {
            me.dwSize = sizeof(me);
            if (Module32First(snap, &me)) {
                do {
                    patch_module_iat((HMODULE)me.modBaseAddr, h_cfa, h_wf);
                    n++;
                } while (Module32Next(snap, &me));
            }
            CloseHandle(snap);
        }
        if (!n) patch_module_iat(GetModuleHandleA(NULL), h_cfa, h_wf);
    }
    fprintf(g_f, "VWDUMP 已挂钩 %lu 个模块\n", (unsigned long)n);
    fflush(g_f);
}
