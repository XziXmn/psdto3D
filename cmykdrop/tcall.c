#include <windows.h>
#include <stdio.h>
typedef int (__stdcall *fn_t)(void*, long long, long long, long long, long long,
                              int, const char*, int, int, int, int, int, int);
int main(int argc, char **argv)
{
    HMODULE h = LoadLibraryA("cmyktiff2.dll");
    if (!h) { printf("load fail %lu\n", GetLastError()); return 1; }
    fn_t f = (fn_t)GetProcAddress(h, "mergtotiff");
    if (!f) { printf("no sym\n"); return 1; }
    const char *out = argc > 1 ? argv[1] : "out_harness.tif";
    long long w = argc > 2 ? _atoi64(argv[2]) : 39370;
    long long hh = argc > 3 ? _atoi64(argv[3]) : 47244;
    printf("call dpi=3120000 lpi=240000 w=%lld h=%lld -> %s\n", w, hh, out);
    int r = f(NULL, 3120000, 240000, w, hh, 0, out, 0, 0, 0, 0, 0, 0);
    printf("return %d\n", r);
    return r;
}
