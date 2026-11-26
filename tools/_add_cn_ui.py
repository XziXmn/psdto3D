# -*- coding: utf-8 -*-
"""Add a Chinese UI translation pass (menus + page-control tabs) to the emulator DLL."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cn_ui_apply' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 界面汉化（运行期替换菜单与页签） ================= */
typedef struct { int id; const wchar_t *cn; } CN_ITEM;
static const CN_ITEM g_cn_menu[] = {
    {3,  L"打开工程"},
    {4,  L"保存工程"},
    {5,  L"工程另存为"},
    {7,  L"导入 PSD"},
    {10, L"导入设置"},
    {12, L"预览 3D 动画"},
    {13, L"停止预览"},
    {14, L"红蓝眼镜预览"},
    {16, L"导出 TIFF"},
    {17, L"导出 PSD"},
    {18, L"导出 GIF"},
    {21, L"退出"},
    {23, L"开始画线"},
    {25, L"撤销"},
    {27, L"删除图层"},
    {28, L"全部删除"},
    {29, L"删除选中"},
    {31, L"全选"},
    {32, L"自由变换"},
    {33, L"剪切"},
    {34, L"复制"},
    {35, L"粘贴"},
    {37, L"放大"},
    {38, L"缩小"},
    {40, L"打开工作目录"},
    {42, L"帮助"},
    {44, L"关于"},
    {45, L"官网 www.3d99.com"},
    {46, L"清除注册信息"},
    {0, 0}
};
static const wchar_t *g_cn_top[4] = { L"文件", L"编辑", L"视图", L"帮助" };

static void cn_translate_menu(HWND hwnd)
{
    HMENU h = GetMenu(hwnd);
    int i, k, n;
    if (!h) return;
    n = GetMenuItemCount(h);
    for (i = 0; i < n && i < 4; i++) {
        HMENU sub = GetSubMenu(h, i);
        if (!sub) continue;
        ModifyMenuW(h, i, MF_BYPOSITION | MF_POPUP | MF_STRING, (UINT_PTR)sub, g_cn_top[i]);
        for (k = 0; g_cn_menu[k].id; k++) {
            int wpos = -1, j, cnt = GetMenuItemCount(sub);
            for (j = 0; j < cnt; j++) {
                if ((int)GetMenuItemID(sub, j) == g_cn_menu[k].id) { wpos = j; break; }
            }
            if (wpos < 0) continue;
            ModifyMenuW(sub, wpos, MF_BYPOSITION | MF_STRING, (UINT)g_cn_menu[k].id, g_cn_menu[k].cn);
        }
    }
    DrawMenuBar(hwnd);
}

static void cn_translate_tabs(HWND hwnd)
{
    struct { const char *cls; const wchar_t *cn; } tabs[] = {
        { "SetLayer",   L"图层设置" },
        { "Output Sets", L"输出设置" },
        { "3DSets",     L"3D 设置" },
        { "DrawLine",   L"画线" },
    };
    int i;
    for (i = 0; i < 4; i++) {
        HWND c = FindWindowExA(hwnd, NULL, tabs[i].cls, NULL);
        if (!c) continue;
        /* 页签标题由 TPageControl 拥有：把 TabSheet 的 Caption 改掉后通知父窗口重绘 */
        SetWindowTextW(c, tabs[i].cn);
        {
            HWND parent = GetParent(c);
            if (parent) {
                SendMessageW(parent, TCM_SETITEMW, 0, 0);   /* 触发重算，标题仍取子窗口文本 */
                InvalidateRect(parent, NULL, TRUE);
            }
        }
    }
}

static DWORD WINAPI cn_ui_thread(LPVOID p)
{
    int tries;
    (void)p;
    Sleep(1500);
    for (tries = 0; tries < 200; tries++) {
        HWND w = FindWindowA("TForm1", NULL);
        if (w) {
            cn_translate_menu(w);
            cn_translate_tabs(w);
            note("CN UI applied");
            /* 后续菜单会被程序重设（启用/禁用），交替重刷几次 */
            Sleep(3000);
            cn_translate_menu(w);
            return 0;
        }
        Sleep(200);
    }
    return 0;
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 启动线程（放在已有线程启动处）
OLD_START = 'CreateThread(NULL, 0, load_watch, NULL, 0, NULL);'
NEW_START = (OLD_START +
             '\r\n        if (GetFileAttributesA("_cn_ui.txt") != INVALID_FILE_ATTRIBUTES)'
             '\r\n            CreateThread(NULL, 0, cn_ui_thread, NULL, 0, NULL);')
if OLD_START in s:
    s = s.replace(OLD_START, NEW_START, 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
