# -*- coding: utf-8 -*-
"""让导入器容忍"某层指针为空"：空则跳过该次写入，不再 AV（用于 41+ 层）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'nil_tolerant' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 容忍空层指针（41+ 层时原版会 AV） ================= */
static int nil_tolerant_applied;

static void patch_nil_tolerant(void *base)
{
    unsigned char *p = (unsigned char *)base + 0x109FFE;
    static const unsigned char expect[] = { 0x8B, 0x04, 0x98, 0x8B, 0x04, 0xB8 };
    DWORD oldp;
    if (nil_tolerant_applied) return;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        note("NIL tolerant: 指令不匹配，跳过");
        return;
    }
    if (!VirtualProtect(p, 22, PAGE_EXECUTE_READWRITE, &oldp)) return;
    /* mov eax,[eax+ebx*4] ; test eax,eax ; jz +0x0F ; mov eax,[eax+edi*4] ;
       mov edx,[0x52309c] ; mov edx,[edx+ebx*4] ; mov [edx+esi*4],eax */
    p[0] = 0x8B; p[1] = 0x04; p[2] = 0x98;
    p[3] = 0x85; p[4] = 0xC0;
    p[5] = 0x74; p[6] = 0x0F;
    p[7] = 0x8B; p[8] = 0x04; p[9] = 0xB8;
    p[10] = 0x8B; p[11] = 0x15; p[12] = 0x9C; p[13] = 0x30; p[14] = 0x52; p[15] = 0x00;
    p[16] = 0x8B; p[17] = 0x14; p[18] = 0x9A;
    p[19] = 0x89; p[20] = 0x04; p[21] = 0xB2;
    VirtualProtect(p, 22, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), p, 22);
    nil_tolerant_applied = 1;
    note("NIL tolerant: 已修 0x509FFE（空层指针跳过）");
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_inline_cfa.txt") != INVALID_FILE_ATTRIBUTES)'''
NEW = '''        if (GetFileAttributesA("_nil_tolerant.txt") != INVALID_FILE_ATTRIBUTES) {
            HMODULE he3 = GetModuleHandleA(0);
            if (he3) patch_nil_tolerant(he3);
        }
        if (GetFileAttributesA("_inline_cfa.txt") != INVALID_FILE_ATTRIBUTES)'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
