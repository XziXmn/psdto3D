# -*- coding: utf-8 -*-
"""修 0x5125FA 的空指针崩：Button12Click 收尾处 [0x523230] 为空时（=用户取消了导入设置）
直接跳过那次调用。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cancel_guard' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 修"导入设置取消后崩溃" =================
 * 原码 0x5125EE 起：mov edx,[0x523230]; mov ecx,[0x523104]; mov edx,[edx+ecx*4]; call ...
 * 用户取消时 [0x523230] 为空 -> 空指针读崩。
 * 改成：先判空，空则跳过这一句调用。
 */
static int cancel_guard_applied;

static void patch_cancel_guard(void *base)
{
    unsigned char *p = (unsigned char *)base + 0x1125EE;
    DWORD oldp;
    static const unsigned char expect[] = { 0x8B,0x15,0x30,0x32,0x52,0x00 };
    if (cancel_guard_applied) return;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        note("CANCEL guard: 指令不匹配，跳过");
        return;
    }
    if (!VirtualProtect(p, 32, PAGE_EXECUTE_READWRITE, &oldp)) return;
    /* mov edx,[0x523230] ; test edx,edx ; jz +0x14 ; mov ecx,[0x523104] ;
       mov edx,[edx+ecx*4] ; mov ecx,[0x4fd9e0] ; call 0x4064dc ; nop nop */
    p[0] = 0x8B; p[1] = 0x15; p[2] = 0x30; p[3] = 0x32; p[4] = 0x52; p[5] = 0x00;
    p[6] = 0x85; p[7] = 0xD2;                          /* test edx,edx */
    p[8] = 0x74; p[9] = 0x14;                          /* jz +0x14 -> 0x51260A */
    p[10] = 0x8B; p[11] = 0x0D; p[12] = 0x04; p[13] = 0x31; p[14] = 0x52; p[15] = 0x00;
    p[16] = 0x8B; p[17] = 0x14; p[18] = 0x8A;          /* mov edx,[edx+ecx*4] */
    p[19] = 0x8B; p[20] = 0x0D; p[21] = 0xE0; p[22] = 0xD9; p[23] = 0x4F; p[24] = 0x00;
    p[25] = 0xE8;                                      /* call rel32 */
    { long rel = (long)(0x004064DC - (0x0051260A + 5)); *(long *)(p + 26) = rel; }
    p[30] = 0x90; p[31] = 0x90;
    VirtualProtect(p, 32, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), p, 32);
    cancel_guard_applied = 1;
    note("CANCEL guard: 已修 0x5125EE（取消导入设置不再崩）");
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_native_probe.txt") != INVALID_FILE_ATTRIBUTES) {'''
NEW = '''        if (GetFileAttributesA("_fix_cancel.txt") != INVALID_FILE_ATTRIBUTES) {
            HMODULE he2 = GetModuleHandleA(0);
            if (he2) patch_cancel_guard(he2);
        }
        if (GetFileAttributesA("_native_probe.txt") != INVALID_FILE_ATTRIBUTES) {'''
assert OLD in s, 'inner anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
