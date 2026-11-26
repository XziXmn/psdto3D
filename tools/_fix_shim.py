# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

s = s.replace('__attribute__((used)) void *g_writepsd_c;\r\n', '')
s = s.replace('__attribute__((used)) void *g_writepsd_c;\n', '')
s = s.replace('static int __cdecl writepsd_c(', 'int __cdecl writepsd_c(')
s = s.replace('            g_writepsd_c = (void *)writepsd_c;\r\n', '')
s = s.replace('            g_writepsd_c = (void *)writepsd_c;\n', '')

old_asm = ('        "pushl %ecx\\n\\t"\r\n'
           '        "pushl %edx\\n\\t"\r\n'
           '        "pushl %eax\\n\\t"\r\n'
           '        "movl g_writepsd_c, %eax\\n\\t"\r\n'
           '        "call *%eax\\n\\t"\r\n'
           '        "addl $12, %esp\\n\\t"\r\n'
           '        "ret\\n\\t");')
new_asm = ('        "pushl %ecx\\n\\t"\r\n'
           '        "pushl %edx\\n\\t"\r\n'
           '        "pushl %eax\\n\\t"\r\n'
           '        "call writepsd_c\\n\\t"\r\n'
           '        "addl $12, %esp\\n\\t"\r\n'
           '        "ret\\n\\t");')
if old_asm in s:
    s = s.replace(old_asm, new_asm)
else:
    # 退一步：逐段替换
    s = s.replace('"movl g_writepsd_c, %eax\\n\\t"', '"call writepsd_c\\n\\t"')
    s = s.replace('"call *%eax\\n\\t"\r\n', '')
    s = s.replace('"call *%eax\\n\\t"\n', '')

io.open(P, 'w', encoding='utf-8').write(s)
print('ok')
