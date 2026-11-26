# -*- coding: utf-8 -*-
"""修正：只给"工程类"对话框（过滤器里含 tw3d）加 .gxwj，导入 PSD 的对话框保持原样。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'only project dialogs' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    char **pf = (char **)((char *)ofn + 0x0C);   /* OPENFILENAME.lpstrFilter */
    if (!pf || !*pf) return;
    if (strstr(*pf, ".gxwj")) return;'''
NEW = '''    char **pf = (char **)((char *)ofn + 0x0C);   /* OPENFILENAME.lpstrFilter */
    if (!pf || !*pf) return;
    if (strstr(*pf, ".gxwj")) return;
    /* only project dialogs: 只有过滤器里含 tw3d 的才改，导入 PSD 的对话框保持原样 */
    if (!strstr(*pf, "tw3d")) return;'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
