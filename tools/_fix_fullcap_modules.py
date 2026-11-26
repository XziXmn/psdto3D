# -*- coding: utf-8 -*-
"""去掉 tlhelp32 依赖，改用固定模块列表枚举 IAT。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\fullcap.c'
s = io.open(P, encoding='utf-8').read()
s = s.replace('#include <tlhelp32.h>\n', '')

start = s.find('static void install_all(void)')
end = s.find('static DWORD WINAPI starter', start)
assert start > 0 and end > start

NEW = r'''static void install_all(void)
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

'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('rewritten install_all')
