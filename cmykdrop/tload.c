#include <windows.h>
#include <stdio.h>
int main(void){
    HMODULE h = LoadLibraryA("cmyktiff2.dll");
    printf("LoadLibrary -> %p (err %lu)\n", (void*)h, GetLastError());
    if (!h) return 1;
    const char *n[] = {"mergtotiff","bmptotiff","savetiff00","gettiffinfo","JpgToBmp","rgbtocmykbmp","tifftobmp"};
    for (int i=0;i<7;i++) printf("  %-14s = %p\n", n[i], (void*)GetProcAddress(h,n[i]));
    return 0;
}
