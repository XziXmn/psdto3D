# -*- coding: utf-8 -*-
"""把过滤器里的中文字面量改成 GBK 字节转义（源码是 UTF-8，直接写会变乱码）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

old_build = '''    if (!gxwj_filter[0]) {
        lstrcpyA(gxwj_filter, "工程文件 (*.tw3d2;*.gxwj;*.tw3d)\\0*.tw3d2;*.gxwj;*.tw3d\\0所有文件 (*.*)\\0*.*\\0");
        /* 补最后一个 \\0（lstrcpyA 只复制到第一个 \\0，需手工补齐） */
        {
            static const char tail[] = "*.tw3d2;*.gxwj;*.tw3d\\0所有文件 (*.*)\\0*.*\\0";
            int head = lstrlenA(gxwj_filter) + 1;
            lstrcpynA(gxwj_filter + head, tail, sizeof(gxwj_filter) - head);
        }
    }'''

new_build = '''    if (!gxwj_filter[0]) {
        /* GBK 字节：工程文件 / 所有文件 */
        static const char label1[] = "\\xB9\\xA4\\xB3\\xCC" "\\xCE\\xC4\\xBC\\xFE";
        static const char label2[] = "\\xCB\\xF9\\xD3\\xD0" "\\xCE\\xC4\\xBC\\xFE";
        int p = 0;
        p += wsprintfA(gxwj_filter + p, "%s (*.tw3d2;*.gxwj;*.tw3d)", label1) + 1;
        p += wsprintfA(gxwj_filter + p, "*.tw3d2;*.gxwj;*.tw3d") + 1;
        p += wsprintfA(gxwj_filter + p, "%s (*.*)", label2) + 1;
        p += wsprintfA(gxwj_filter + p, "*.*") + 1;
        gxwj_filter[p] = 0;
    }'''

if old_build in s:
    s = s.replace(old_build, new_build, 1)
    io.open(P, 'w', encoding='utf-8').write(s)
    print('rewritten')
else:
    print('anchor not found; dumping current block:')
    i = s.find('gxwj_patch_filter')
    print(s[i:i + 700])
