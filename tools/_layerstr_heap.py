# -*- coding: utf-8 -*-
"""改用进程堆自己分配（refcount=-1 = 常量数组，Delphi 不会去释放），避免跨线程调 GetMem 破坏堆。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'HeapAlloc(GetProcessHeap(), 0, 8 + layers' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    getmem = (PF_GETMEM)((char *)he + 0x00270C);             /* FUN_0040270c = GetMem */
    mem = (int *)getmem(8 + layers * 4);
    if (!mem) { note("layerstr: GetMem 失败"); return 0; }
    mem[0] = 1;                     /* refcount */
    mem[1] = layers;                /* length */'''
NEW = '''    (void)getmem;
    mem = (int *)HeapAlloc(GetProcessHeap(), 0, 8 + layers * 4);
    if (!mem) { note("layerstr: HeapAlloc 失败"); return 0; }
    memset(mem, 0, 8 + layers * 4);
    mem[0] = -1;                    /* refcount = -1：静态数组，Delphi 不会释放 */
    mem[1] = layers;                /* length */'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
