# -*- coding: utf-8 -*-
"""让"打开工程"的文件对话框也能列出 .gxwj（改 lpstrFilter）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'gxwj_filter' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static char gxwj_filter[256];
static void gxwj_patch_filter(void *ofn)
{
    char **pf = (char **)((char *)ofn + 0x0C);   /* OPENFILENAME.lpstrFilter */
    if (!pf || !*pf) return;
    if (strstr(*pf, ".gxwj")) return;
    if (!gxwj_filter[0]) {
        lstrcpyA(gxwj_filter, "工程文件 (*.tw3d2;*.gxwj;*.tw3d)\0*.tw3d2;*.gxwj;*.tw3d\0所有文件 (*.*)\0*.*\0");
        /* 补最后一个 \0（lstrcpyA 只复制到第一个 \0，需手工补齐） */
        {
            static const char tail[] = "*.tw3d2;*.gxwj;*.tw3d\0所有文件 (*.*)\0*.*\0";
            int head = lstrlenA(gxwj_filter) + 1;
            lstrcpynA(gxwj_filter + head, tail, sizeof(gxwj_filter) - head);
        }
    }
    *pf = gxwj_filter;
}
'''

ANCHOR = 'static BOOL WINAPI e_gofna(void *p)'
if ANCHOR not in s:
    ANCHOR = 'static BOOL WINAPI e_gofna(LPVOID p)'
assert ANCHOR in s, 'gofna anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 在 e_gofna 内部（进入队列分支之前）插入过滤器改写
OLD = '''static BOOL WINAPI e_gofna(void *p)
{'''
NEW = '''static BOOL WINAPI e_gofna(void *p)
{
    if (p && GetFileAttributesA("_gxwj.txt") != INVALID_FILE_ATTRIBUTES) gxwj_patch_filter(p);'''
if OLD in s:
    s = s.replace(OLD, NEW, 1)
else:
    OLD2 = '''static BOOL WINAPI e_gofna(LPVOID p)
{'''
    NEW2 = '''static BOOL WINAPI e_gofna(LPVOID p)
{
    if (p && GetFileAttributesA("_gxwj.txt") != INVALID_FILE_ATTRIBUTES) gxwj_patch_filter(p);'''
    assert OLD2 in s, 'gofna body anchor missing'
    s = s.replace(OLD2, NEW2, 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
