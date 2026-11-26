# -*- coding: utf-8 -*-
"""修 trampoline：若 CreateFileA 开头是 E9（转发到 kernelbase），直接解析目标后跳过去。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'tramp resolves forwarder' in s:
    print('already there')
    raise SystemExit(0)

OLD = '''    t = (unsigned char *)g_cfa_tramp;
    memcpy(t, p, 5);                                   /* 原前 5 字节（push ebp / mov ebp,esp 等） */
    t[5] = 0xE9;
    rel = (long)((p + 5) - (t + 10));
    *(long *)(t + 6) = rel;'''
NEW = '''    t = (unsigned char *)g_cfa_tramp;
    if (p[0] == 0xE9) {                                /* tramp resolves forwarder: jmp rel32 */
        unsigned char *target = p + 5 + *(long *)(p + 1);
        t[0] = 0xE9;
        *(long *)(t + 1) = (long)(target - (t + 5));
    } else {
        memcpy(t, p, 5);                               /* 复制原开头 5 字节，再跳回 +5 */
        t[5] = 0xE9;
        *(long *)(t + 6) = (long)((p + 5) - (t + 10));
    }'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
