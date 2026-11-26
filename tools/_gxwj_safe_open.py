# -*- coding: utf-8 -*-
"""修 I/O 103：程序会用不同打开方式多次打开同一个工程文件，
我们把转换产物强行用"只读 + 共享 + 已存在"打开，避免第二次把它截断。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'GXWJ open safe' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''            char conv[MAX_PATH];
            if (gxwj_convert(name, conv, MAX_PATH))
                return o_cfa(conv, acc, share, sa, disp, flags, tmpl);'''
NEW = '''            char conv[MAX_PATH];
            if (gxwj_convert(name, conv, MAX_PATH)) {
                /* GXWJ open safe: 只用只读+共享+OPEN_EXISTING，绝不截断程序正在读的文件 */
                HANDLE hc = o_cfa(conv, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                  0, OPEN_EXISTING, 0, 0);
                note("GXWJ open safe: %s -> %p", conv, hc);
                return hc;
            }'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
