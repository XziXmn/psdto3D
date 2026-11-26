# -*- coding: utf-8 -*-
"""Add status-bar panel translation and a second tab-translation attempt."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cn_status_pass' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static void cn_status_pass(HWND w)
{
    static const wchar_t *panels[] = {
        L"官网 3d99.com", L"原始信息", L"尺寸(厘米)", L"分辨率", L"颜色", L"层数", L"请先导入 PSD 文件"
    };
    HWND sb = FindWindowExA(w, NULL, "TStatusBar", NULL);
    int n, i;
    if (!sb) return;
    n = (int)SendMessageA(sb, 0x0400 + 6, 0, 0);      /* SB_GETPARTS */
    for (i = 0; i < n && i < 7; i++) {
        SendMessageW(sb, 0x0401, (WPARAM)i, (LPARAM)panels[i]);   /* SB_SETTEXTW */
    }
}

static void cn_tabs_pass(HWND w)
{
    static const struct { const wchar_t *en; const wchar_t *cn; } tabs[] = {
        { L"SetLayer", L"图层设置" }, { L"Output Sets", L"输出设置" },
        { L"3DSets", L"3D 设置" }, { L"DrawLine", L"画线" },
    };
    HWND pc = NULL;
    int guard;
    for (guard = 0; guard < 8; guard++) {
        int n, i, k;
        pc = FindWindowExA(w, pc, "TPageControl", NULL);
        if (!pc) break;
        n = (int)SendMessageA(pc, 0x1304, 0, 0);
        for (i = 0; i < n; i++) {
            wchar_t buf[128];
            buf[0] = 0;
            /* TCM_GETITEMW: 直接传 TCITEMW 指针 */
            struct { UINT mask; int iImage; LPWSTR pszText; int cch; int iImage2; LPARAM lParam; } it;
            it.mask = 0x1; it.iImage = 0; it.pszText = buf; it.cch = 128; it.iImage2 = 0; it.lParam = 0;
            if (SendMessageW(pc, 0x1300 + 60, i, (LPARAM)&it)) {
                for (k = 0; k < 4; k++) {
                    if (lstrcmpiW(buf, tabs[k].en) == 0) {
                        struct { UINT mask; int iImage; LPWSTR pszText; int cch; int iImage2; LPARAM lParam; } st;
                        st.mask = 0x1; st.iImage = 0; st.pszText = (LPWSTR)tabs[k].cn; st.cch = 0; st.iImage2 = 0; st.lParam = 0;
                        SendMessageW(pc, 0x1300 + 61, i, (LPARAM)&st);
                        break;
                    }
                }
            }
        }
        InvalidateRect(pc, NULL, TRUE);
    }
}
'''

ANCHOR = 'static DWORD WINAPI cn_ui_thread(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''            cn_child_pass(w);
            note("CN UI round %d", round);'''
NEW = '''            cn_child_pass(w);
            cn_status_pass(w);
            cn_tabs_pass(w);
            note("CN UI round %d", round);'''
assert OLD in s, 'inner anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
