# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
# 去掉之前放错位置的前向声明
s = s.replace('static int g_zu06_patched;\r\nstatic void log_preview_probe(void);',
              'static int g_zu06_patched;')
# 放到文件靠前的位置（第一个 #define 之后）
anchor = '#define RVA_CREATEFILE_A   0x1242BC'
if 'static void log_preview_probe(void);' not in s:
    assert anchor in s, 'anchor missing'
    s = s.replace(anchor, 'static void log_preview_probe(void);\n' + anchor, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
