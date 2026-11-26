# -*- coding: utf-8 -*-
"""Replace the translation pass with caption-based mapping (menus + all child windows)."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

start = s.find('/* ================= 界面汉化（运行期替换菜单与页签） ================= */')
end = s.find('static DWORD WINAPI load_watch(LPVOID p)')
assert start > 0 and end > start, 'block not found'

NEW = r'''/* ================= 界面汉化（运行期按文本替换） ================= */
typedef struct { const wchar_t *en; const wchar_t *cn; } CN_PAIR;
static const CN_PAIR g_cn[] = {
    /* 顶层菜单 */
    { L"File", L"文件" }, { L"Edit", L"编辑" }, { L"View", L"视图" }, { L"Help", L"帮助" },
    /* 文件 */
    { L"Open project", L"打开工程" },
    { L"Save project", L"保存工程" },
    { L"Save as project", L"工程另存为" },
    { L"Import *.psd", L"导入 PSD" },
    { L"Import settings", L"导入设置" },
    { L"Preview 3D animation", L"预览 3D 动画" },
    { L"Stop preview", L"停止预览" },
    { L"Red/Blue Glasses preview", L"红蓝眼镜预览" },
    { L"Export *.tiff", L"导出 TIFF" },
    { L"Export PSD", L"导出 PSD" },
    { L"Export Gif", L"导出 GIF" },
    { L"Quit", L"退出" },
    /* 编辑 */
    { L"Begin draw line", L"开始画线" },
    { L"Undo", L"撤销" },
    { L"Delete Layer", L"删除图层" },
    { L"Delete All", L"全部删除" },
    { L"Delete Select", L"删除选中" },
    { L"Select All", L"全选" },
    { L"Free Transition", L"自由变换" },
    { L"Cut", L"剪切" }, { L"Copy", L"复制" }, { L"Pastup", L"粘贴" },
    /* 视图 / 帮助 */
    { L"Zoom In", L"放大" }, { L"Zoom Out", L"缩小" },
    { L"Show work folder", L"打开工作目录" },
    { L"About", L"关于" },
    { L"Clear Registered information", L"清除注册信息" },
    /* 页签与面板 */
    { L"SetLayer", L"图层设置" },
    { L"Output Sets", L"输出设置" },
    { L"3DSets", L"3D 设置" },
    { L"DrawLine", L"画线" },
    { L"Layer View", L"图层视图" },
    { L"All", L"全部" }, { L"One", L"单个" },
    { L"Layer", L"图层" }, { L"Group", L"组" }, { L"Offset", L"偏移" },
    { L"LPI", L"线数" }, { L"Angles", L"角度数" },
    { L"Layer D", L"层深" }, { L"Depth", L"深度" },
    { L"Original Info", L"原始信息" },
    { L"Size (cm)", L"尺寸(厘米)" },
    { L"DPI", L"分辨率" }, { L"Color", L"颜色" }, { L"Layers", L"层数" },
    { L"Please import *.psd.", L"请先导入 PSD 文件" },
    { 0, 0 }
};

static const wchar_t *cn_lookup(const wchar_t *en)
{
    int i;
    wchar_t buf[160];
    int n = 0;
    while (en[n] && n < 159) { buf[n] = en[n]; n++; }
    buf[n] = 0;
    /* 去掉 & 与快捷键后缀 \tCtrl+X */
    {
        int a = 0, b;
        for (b = 0; buf[b]; b++) if (buf[b] != L'&') buf[a++] = buf[b];
        buf[a] = 0;
        for (b = 0; buf[b]; b++) if (buf[b] == L'\t') { buf[b] = 0; break; }
        while (a > 0 && (buf[a - 1] == L' ' || buf[a - 1] == L'.')) buf[--a] = 0;
    }
    for (i = 0; g_cn[i].en; i++)
        if (lstrcmpiW(buf, g_cn[i].en) == 0) return g_cn[i].cn;
    return 0;
}

static void cn_menu_pass(HMENU h, int depth)
{
    int n, i;
    if (!h || depth > 3) return;
    n = GetMenuItemCount(h);
    for (i = 0; i < n; i++) {
        wchar_t buf[160];
        HMENU sub = GetSubMenu(h, i);
        buf[0] = 0;
        GetMenuStringW(h, i, buf, 160, MF_BYPOSITION);
        if (sub) {
            const wchar_t *cn = cn_lookup(buf);
            if (cn) ModifyMenuW(h, i, MF_BYPOSITION | MF_POPUP | MF_STRING, (UINT_PTR)sub, cn);
            cn_menu_pass(sub, depth + 1);
        } else {
            int id = GetMenuItemID(h, i);
            const wchar_t *cn = cn_lookup(buf);
            if (cn && id > 0) ModifyMenuW(h, i, MF_BYPOSITION | MF_STRING, (UINT)id, cn);
        }
    }
}

static void cn_child_pass(HWND w)
{
    wchar_t buf[200];
    HWND c = NULL;
    buf[0] = 0;
    GetWindowTextW(w, buf, 200);
    if (buf[0]) {
        const wchar_t *cn = cn_lookup(buf);
        if (cn) SetWindowTextW(w, cn);
    }
    for (;;) {
        c = FindWindowExA(w, c, NULL, NULL);
        if (!c) break;
        cn_child_pass(c);
    }
}

static DWORD WINAPI cn_ui_thread(LPVOID p)
{
    int round;
    (void)p;
    for (round = 0; round < 6; round++) {
        HWND w = FindWindowA("TForm1", NULL);
        if (w) {
            HMENU h = GetMenu(w);
            cn_menu_pass(h, 0);
            DrawMenuBar(w);
            cn_child_pass(w);
            note("CN UI round %d", round);
        }
        Sleep(2500);
    }
    return 0;
}

'''

s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
