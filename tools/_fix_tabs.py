# -*- coding: utf-8 -*-
"""Fix tab translation: match TTabSheet windows by their caption text."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

start = s.find('static void cn_translate_tabs(HWND hwnd)')
end = s.find('static DWORD WINAPI cn_ui_thread(LPVOID p)')
assert start > 0 and end > start, 'block not found'

NEW = r'''static void cn_translate_tabs(HWND hwnd)
{
    static const struct { const wchar_t *en; const wchar_t *cn; } tabs[] = {
        { L"SetLayer",    L"图层设置" },
        { L"Output Sets", L"输出设置" },
        { L"3DSets",      L"3D 设置" },
        { L"DrawLine",    L"画线" },
    };
    HWND c = NULL;
    int i, k;
    for (i = 0; i < 200; i++) {
        wchar_t buf[128];
        c = FindWindowExA(hwnd, c, "TTabSheet", NULL);
        if (!c) break;
        buf[0] = 0;
        GetWindowTextW(c, buf, 128);
        for (k = 0; k < 4; k++) {
            if (lstrcmpiW(buf, tabs[k].en) == 0) {
                SetWindowTextW(c, tabs[k].cn);
                {
                    HWND parent = GetParent(c);
                    if (parent) InvalidateRect(parent, NULL, TRUE);
                }
                break;
            }
        }
    }
}

'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
