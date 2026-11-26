#include <windows.h>
#include <stdio.h>
#include <stdarg.h>

static void __cdecl logline(const char *fmt, ...)
{
    FILE *f = fopen("_mergargs.txt", "a");
    if (!f) return;
    va_list ap;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}

__declspec(dllexport) int __stdcall mergtotiff(void *obj, long long a, long long b,
                                               long long c, long long d, int p2c,
                                               int p30, int p34, void *path, int p3c,
                                               int p40, int p44, int p48)
{
    logline("mergtotiff obj=%p a=%lld b=%lld c=%lld d=%lld", obj, a, b, c, d);
    logline("  p2c=%d p30=%d p34=%d path=%p p3c=%d p40=%d p44=%d p48=%d",
            p2c, p30, p34, path, p3c, p40, p44, p48);
    if (path && !IsBadReadPtr(path, 1)) {
        char buf[256]; int i = 0;
        const char *p = (const char *)path;
        while (i < 255 && !IsBadReadPtr(p + i, 1) && p[i]) { buf[i] = p[i]; i++; }
        buf[i] = 0;
        logline("  path as C string: '%s'", buf);
    }
    return 0;
}

__declspec(dllexport) int __stdcall savetiff00(void)  { logline("savetiff00 called");  return 0; }
__declspec(dllexport) int __stdcall bmptotiff(void)   { logline("bmptotiff called");   return 0; }
__declspec(dllexport) int __stdcall gettiffinfo(void) { logline("gettiffinfo called"); return 0; }
__declspec(dllexport) int __stdcall JpgToBmp(void)    { logline("JpgToBmp called");    return 0; }
__declspec(dllexport) int __stdcall rgbtocmykbmp(void){ logline("rgbtocmykbmp called");return 0; }
__declspec(dllexport) int __stdcall tifftobmp(void)   { logline("tifftobmp called");  return 0; }
