# -*- coding: utf-8 -*-
"""[0x523230] 是 "array of array of integer"：给每层分配一个空的内部数组（预留 0x60 字节），
这样 [edx+0x38] 落在我们自己分配的内存里，不会读到非法地址。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'INNER_BYTES' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    for (i = 0; i < layers; i++) ((int *)(mem + 2))[i] = 0;  /* 每项为空字符串 */'''
NEW = '''    for (i = 0; i < layers; i++) {
        /* 每层一个内部动态数组：refcount=-1、长度=0，但预留 0x60 字节可读 */
        int *inner = (int *)HeapAlloc(GetProcessHeap(), 0, 8 + 0x60);
        if (!inner) { ((int *)(mem + 2))[i] = 0; continue; }
        memset(inner, 0, 8 + 0x60);
        inner[0] = -1;
        inner[1] = 0;
        ((int *)(mem + 2))[i] = (int)(inner + 2);
    }'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
s = s.replace('note("layerstr: 已为 %u 层分配字符串数组 @%p"',
              'note("layerstr: 已为 %u 层分配内部数组 @%p"', 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
