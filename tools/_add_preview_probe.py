# -*- coding: utf-8 -*-
"""在预览入口 0x50AD74 打点，记录 [0x523230] 及其长度、层数，判断数组何时/为何没分配。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'sppreview' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static int sppreview_armed;

static void arm_preview_probe(void)
{
    if (sppreview_armed) return;
    sppreview_armed = 1;
    sbp_arm(0x0050AD74);            /* SpeedButton9Click = 预览入口 */
    note("sppreview: 已在 0x50AD74 打点");
}

static void log_preview_probe(void)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned long *p = (unsigned long *)((char *)he + 0x123230);
    unsigned long *pa = (unsigned long *)*p;
    note("sppreview: [523230]=%08lX len=%ld layers=%u",
         (unsigned long)*p, pa ? (long)pa[-1] : -1,
         (unsigned)(*(unsigned short *)((char *)he + 0x12315C)));
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_nil_tolerant.txt") != INVALID_FILE_ATTRIBUTES) {'''
NEW = '''        if (GetFileAttributesA("_sbp_psd.txt") != INVALID_FILE_ATTRIBUTES)
            arm_preview_probe();
        if (GetFileAttributesA("_nil_tolerant.txt") != INVALID_FILE_ATTRIBUTES) {'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)

# 在 VEH 里对 0x50AD74 命中做记录
OLD2 = '''    if (code == 0xC0000005 && GetFileAttributesA("_avdump.txt") != INVALID_FILE_ATTRIBUTES) {'''
NEW2 = '''    if (code == 0x80000003 && ep->ContextRecord->Eip == 0x0050AD74 + 1 &&
        GetFileAttributesA("_sbp_psd.txt") != INVALID_FILE_ATTRIBUTES)
        log_preview_probe();
    if (code == 0xC0000005 && GetFileAttributesA("_avdump.txt") != INVALID_FILE_ATTRIBUTES) {'''
if OLD2 in s:
    s = s.replace(OLD2, NEW2, 1)
else:
    OLDB = '''static LONG CALLBACK sbp_veh(EXCEPTION_POINTERS *ep)
{
    DWORD code = ep->ExceptionRecord->ExceptionCode;'''
    NEWB = OLDB + '''
    if (code == 0x80000003 && ep->ContextRecord->Eip == 0x0050AD74 + 1 &&
        GetFileAttributesA("_sbp_psd.txt") != INVALID_FILE_ATTRIBUTES)
        log_preview_probe();'''
    assert OLDB in s, 'veh anchor missing'
    s = s.replace(OLDB, NEWB, 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
