# -*- coding: utf-8 -*-
"""为 [0x523230]（每层的字符串数组）按真实层数补分配，让 >33 层的预览不再因空指针崩溃。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'alloc_layer_strs' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 补分配 [0x523230]（array of string，每层一个） ================= */
typedef void * (__attribute__((regparm(3))) *PF_GETMEM)(int size);

static int g_layerstr_layers;

static int alloc_layer_strs(void)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned long *slot;
    unsigned short layers;
    PF_GETMEM getmem;
    int *mem;
    unsigned i;

    if (!he) return 0;
    slot = (unsigned long *)((char *)he + 0x123230);
    layers = *(unsigned short *)((char *)he + 0x12315C);
    if (*slot || layers == 0 || layers <= 33) return 0;      /* 33 层以内程序自己没问题 */
    if ((int)layers == g_layerstr_layers) return 0;

    getmem = (PF_GETMEM)((char *)he + 0x00270C);             /* FUN_0040270c = GetMem */
    mem = (int *)getmem(8 + layers * 4);
    if (!mem) { note("layerstr: GetMem 失败"); return 0; }
    mem[0] = 1;                     /* refcount */
    mem[1] = layers;                /* length */
    for (i = 0; i < layers; i++) ((int *)(mem + 2))[i] = 0;  /* 每项为空字符串 */
    *slot = (unsigned long)(mem + 2);
    g_layerstr_layers = layers;
    note("layerstr: 已为 %u 层分配字符串数组 @%p", (unsigned)layers, (void *)(mem + 2));
    return 1;
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_selfprobe.txt") != INVALID_FILE_ATTRIBUTES)'''
NEW = '''        if (GetFileAttributesA("_layerstr.txt") != INVALID_FILE_ATTRIBUTES)
            alloc_layer_strs();
        if (GetFileAttributesA("_selfprobe.txt") != INVALID_FILE_ATTRIBUTES)'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
