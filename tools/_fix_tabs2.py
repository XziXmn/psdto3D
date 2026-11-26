# -*- coding: utf-8 -*-
"""Translate page-control tab labels via TCM_GETITEMW/TCM_SETITEMW."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

start = s.find('static void cn_translate_tabs(HWND hwnd)')
end = s.find('static DWORD WINAPI cn_ui_thread(LPVOID p)')
assert start > 0 and end > start, 'block not found'

NEW = r'''typedef struct {
    UINT mask;
    int  iImage;
    LPWSTR pszText;
    int  cchTextMax;
    int  iImage2;
    LPARAM lParam;
} CN_TCITEMW;

static void cn_translate_tabs(HWND hwnd)
{
    static const struct { const wchar_t *en; const wchar_t *cn; } tabs[] = {
        { L"SetLayer",    L"图层设置" },
        { L"Output Sets", L"输出设置" },
        { L"3DSets",      L"3D 设置" },
        { L"DrawLine",    L"画线" },
    };
    HWND pc = NULL;
    int guard;
    for (guard = 0; guard < 8; guard++) {
        int n, i, k;
        pc = FindWindowExA(hwnd, pc, "TPageControl", NULL);
        if (!pc) break;
        n = (int)SendMessageA(pc, 0x1300 + 4, 0, 0);          /* TCM_GETITEMCOUNT */
        for (i = 0; i < n; i++) {
            wchar_t buf[128];
            CN_TCITEMW it;
            buf[0] = 0;
            memset(&it, 0, sizeof(it));
            it.mask = 0x1;                                     /* TCIF_TEXT */
            it.pszText = buf;
            it.cchTextMax = 128;
            if (SendMessageW(pc, 0x1300 + 60, i, (LPARAM)&it)) {  /* TCM_GETITEMW */
                for (k = 0; k < 4; k++) {
                    if (lstrcmpiW(buf, tabs[k].en) == 0) {
                        CN_TCITEMW set;
                        memset(&set, 0, sizeof(set));
                        set.mask = 0x1;
                        set.pszText = (LPWSTR)tabs[k].cn;
                        SendMessageW(pc, 0x1300 + 61, i, (LPARAM)&set);  /* TCM_SETITEMW */
                        break;
                    }
                }
            }
        }
        InvalidateRect(pc, NULL, TRUE);
    }
}

'''
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
