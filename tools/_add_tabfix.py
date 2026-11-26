# -*- coding: utf-8 -*-
"""导入后自动触发 TabSheet2Show（0x507A7C），让渲染用的每层数组按真实层数分配。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'tabfix' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 自动补跑 TabSheet2Show（层数组分配） ================= */
typedef void (__attribute__((regparm(3))) *PF_TABSHEETSHOW)(void *self, void *sender);

static int tabfix_last_layers = -1;

static void tabfix_try(void)
{
    HMODULE he = GetModuleHandleA(0);
    HWND formw = FindWindowA("TForm1", NULL);
    unsigned long *arrp, *arr;
    unsigned short layers;
    void *self;
    PF_TABSHEETSHOW fn;
    if (!he || !formw) return;
    arrp = (unsigned long *)((char *)he + 0x123230);
    arr = (unsigned long *)*arrp;
    layers = *(unsigned short *)((char *)he + 0x12315C);
    if (arr || layers == 0) return;              /* 已分配或无层 */
    if ((int)layers == tabfix_last_layers) return;
    self = (void *)(unsigned long)GetWindowLongA(formw, 0);   /* VCL 把 Self 存在窗口附加字节 0 */
    if (!self) return;
    fn = (PF_TABSHEETSHOW)((char *)he + 0x107A7C);
    note("tabfix: 层数=%u 数组为空，调用 TabSheet2Show(self=%p)", layers, self);
    fn(self, 0);
    tabfix_last_layers = (int)layers;
    note("tabfix: 调用完成，[523230]=%08lX", (unsigned long)*arrp);
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_sbp_psd.txt") != INVALID_FILE_ATTRIBUTES)'''
NEW = '''        if (GetFileAttributesA("_tabfix.txt") != INVALID_FILE_ATTRIBUTES)
            tabfix_try();
        if (GetFileAttributesA("_sbp_psd.txt") != INVALID_FILE_ATTRIBUTES)'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
