/* 观测钩子：在 CreateFileA 打开 vw*.bmp 时，抓"是谁写的"。
 *
 * 为什么需要它：gx 切片两边逐字节全同，但 vw*.bmp 有对称差异。
 * 这说明差异发生在 gx→bmp 合成那一步。合成在 zu6.dll / cmyktiff1.dll 里，
 * 但它们不 import my32.dll，所以必须靠运行时调用栈定位真正的调用点。
 *
 * 不修改任何代码字节：只 hook 一次 kernel32!CreateFileA 的 IAT/入口（或用
 * detour），命中时用 RtlCaptureStackBackTrace 抓栈并写日志。
 *
 * 环境变量 VWLOG=1 才启用。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static FILE *g_f;
static char g_dir[MAX_PATH];
typedef HANDLE (WINAPI *PF_CFA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static PF_CFA g_cfa;
static char g_tramp[64];
static int g_on;

void vwlog_note(const char *fmt, ...);
void vwlog_note(const char *fmt, ...)
{
    va_list ap;
    if (!g_f) return;
    va_start(ap, fmt);
    vfprintf(g_f, fmt, ap);
    va_end(ap);
    fputc('\n', g_f);
    fflush(g_f);
}

/* 判断是不是 vw*.bmp / vwt*.gjs */
static int is_view(const char *p)
{
    const char *s;
    if (!p) return 0;
    s = strrchr(p, '\\');
    s = s ? s + 1 : p;
    if (s[0] != 'v' || s[1] != 'w') return 0;
    return 1;
}

static HANDLE WINAPI hook_cfa(LPCSTR name, DWORD access, DWORD share,
                              LPSECURITY_ATTRIBUTES sa, DWORD disp,
                              DWORD flags, HANDLE tmpl)
{
    HANDLE h = g_cfa(name, access, share, sa, disp, flags, tmpl);
    if (g_on && is_view(name) && access != 0) {
        void *frames[24];
        USHORT n = RtlCaptureStackBackTrace(0, 24, frames, NULL);
        int i;
        vwlog_note("CFA %s access=%08lX disp=%lu frames=%u", name,
                   (unsigned long)access, (unsigned long)disp, n);
        for (i = 0; i < n && i < 14; i++)
            vwlog_note("    #%d %p", i, frames[i]);
    }
    return h;
}

void vwlog_install(void)
{
    char env[8];
    HMODULE k32;
    if (!GetEnvironmentVariableA("VWLOG", env, sizeof(env))) return;
    GetModuleFileNameA(NULL, g_dir, MAX_PATH);
    { char *s = strrchr(g_dir, 92); if (s) s[1] = 0; }
    strcat(g_dir, "_vwlog.txt");
    g_f = fopen(g_dir, "w");
    if (!g_f) return;
    g_on = 1;
    k32 = GetModuleHandleA("kernel32.dll");
    g_cfa = (PF_CFA)GetProcAddress(k32, "CreateFileA");
    vwlog_note("VWLOG 安装 CreateFileA=%p", (void *)g_cfa);

    /* 用 inline patch 替换 kernel32!CreateFileA 的入口（6 字节） */
    {
        DWORD old;
        unsigned char *p = (unsigned char *)g_cfa;
        unsigned char *t = (unsigned char *)g_tramp;
        if (VirtualProtect(p, 8, PAGE_EXECUTE_READWRITE, &old)) {
            t[0] = 0x68;                       /* push imm32 (返回地址占位) */
            *(unsigned *)(t + 1) = 0;
            t[5] = 0xE9;
            *(int *)(t + 6) = (int)(p + 5 - (t + 10));
            /* 实际做法：入口改成 jmp hook_cfa，hook 里再直接调原函数体 */
        }
        VirtualProtect(p, 8, old, &old);
    }
    vwlog_note("（本版仅记录安装信息；真正拦截走 detour 需 MinHook）");
}
