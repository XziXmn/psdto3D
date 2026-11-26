# -*- coding: utf-8 -*-
"""在 VEH 里记录访问违例现场（EIP、关键寄存器、层数组指针与长度），用于定位 40 层上限。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'AVDUMP' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''static LONG CALLBACK sbp_veh(EXCEPTION_POINTERS *ep)
{
    DWORD code = ep->ExceptionRecord->ExceptionCode;'''
NEW = '''static LONG CALLBACK sbp_veh(EXCEPTION_POINTERS *ep)
{
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    if (code == 0xC0000005 && GetFileAttributesA("_avdump.txt") != INVALID_FILE_ATTRIBUTES) {
        CONTEXT *c0 = ep->ContextRecord;
        HMODULE he = GetModuleHandleA(0);
        unsigned long *arrA = (unsigned long *)((char *)he + 0x1230A0);   /* [0x5230a0] */
        unsigned long *arrB = (unsigned long *)((char *)he + 0x12309C);   /* [0x52309c] */
        note("AVDUMP eip=%08lX ebx=%lX edi=%lX esi=%lX ecx=%lX edx=%lX actual=0x%08lX",
             (unsigned long)c0->Eip, (unsigned long)c0->Ebx, (unsigned long)c0->Edi,
             (unsigned long)c0->Esi, (unsigned long)c0->Ecx, (unsigned long)c0->Edx,
             (unsigned long)ep->ExceptionRecord->ExceptionInformation[1]);
        note("AVDUMP [5230a0]=%08lX [52309c]=%08lX layers=%u", *arrA, *arrB,
             (unsigned)(*(unsigned short *)((char *)he + 0x12315C)));
    }'''
assert OLD in s, 'veh anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
