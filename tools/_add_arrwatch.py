# -*- coding: utf-8 -*-
"""周期性记录 [0x523230] 指针/长度与层数，观察它在导入/预览过程中何时被分配。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'arrwatch' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static unsigned long arrwatch_last_p, arrwatch_last_len;
static unsigned short arrwatch_last_layers;

static void arrwatch_tick(void)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned long *p, *a;
    unsigned long len;
    unsigned short layers;
    if (!he) return;
    p = (unsigned long *)((char *)he + 0x123230);
    a = (unsigned long *)*p;
    len = a ? (unsigned long)a[-1] : 0xFFFFFFFF;
    layers = *(unsigned short *)((char *)he + 0x12315C);
    if (*p != arrwatch_last_p || len != arrwatch_last_len || layers != arrwatch_last_layers) {
        arrwatch_last_p = *p; arrwatch_last_len = len; arrwatch_last_layers = layers;
        note("arrwatch: [523230]=%08lX len=%ld layers=%u", *p, (long)len, (unsigned)layers);
    }
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_tabfix.txt") != INVALID_FILE_ATTRIBUTES)'''
NEW = '''        if (GetFileAttributesA("_arrwatch.txt") != INVALID_FILE_ATTRIBUTES)
            arrwatch_tick();
        if (GetFileAttributesA("_tabfix.txt") != INVALID_FILE_ATTRIBUTES)'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
