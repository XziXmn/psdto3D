#include <windows.h>
#include <stdio.h>
#include <stdarg.h>

static void __cdecl logline(const char *fmt, ...)
{
    FILE *f = fopen("_mergargs.txt", "a");
    if (!f) return;
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f); fclose(f);
}

static void dump_delphi_str(const char *tag, void *p)
{
    if (!p || IsBadReadPtr(p, 12)) { logline("  %s=%p (bad ptr)", tag, p); return; }
    int len = *(const int *)((const char *)p + 4);
    const char *s = (const char *)p + 8;
    if (len < 0 || len > 500 || IsBadReadPtr(s, len + 1)) {
        logline("  %s=%p len=%d (not a delphi string)", tag, p, len); return;
    }
    char buf[520]; int i;
    for (i = 0; i < len && i < 519; i++) buf[i] = s[i];
    buf[i] = 0;
    logline("  %s='%s'", tag, buf);
}

/* 只记录：从 esp 上抓 12 个 dword，看调用方到底压了什么 */
__declspec(dllexport) int __stdcall bmptotiff(void)
{
    const unsigned *sp;
    __asm__ volatile ("movl %%esp, %0" : "=r"(sp));
    logline("bmptotiff: ret=%p  args:", (void *)sp[0]);
    int i;
    for (i = 1; i <= 12; i++) logline("   [esp+%2d] = 0x%08X (%d)", i*4, sp[i], (int)sp[i]);
    for (i = 1; i <= 12; i++) {
        char tag[32]; wsprintfA(tag, "arg%d", i);
        dump_delphi_str(tag, (void *)sp[i]);
    }
    return 0;
}

__declspec(dllexport) int __stdcall mergtotiff(void *obj, long long a, long long b,
                                               long long c, long long d, int p2c,
                                               int p30, int p34, void *path, int p3c,
                                               int p40, int p44, int p48)
{
    logline("mergtotiff obj=%p dpi=%lld lpi=%lld w=%lld h=%lld flags=%d,%d,%d,%d,%d,%d,%d",
            obj, a, b, c, d, p2c, p30, p34, p3c, p40, p44, p48);
    dump_delphi_str("path", path);
    return 0;
}

__declspec(dllexport) int __stdcall savetiff00(void)  { return 0; }
__declspec(dllexport) int __stdcall gettiffinfo(void) { return 0; }
__declspec(dllexport) int __stdcall JpgToBmp(void)    { return 0; }
__declspec(dllexport) int __stdcall rgbtocmykbmp(void){ return 0; }
__declspec(dllexport) int __stdcall tifftobmp(void)   { return 0; }
