# -*- coding: utf-8 -*-
"""AV 时打印动态数组长度（Delphi dynarray 的 [-1] 是长度）与出错层元素内容。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'AVDUMP len' in s:
    print('already there')
    raise SystemExit(0)

OLD = '''            {
                unsigned long *a = (unsigned long *)*arrB;'''
NEW = '''            {
                unsigned long *c = (unsigned long *)((char *)he + 0x1230B4);
                unsigned long *pa = (unsigned long *)*arrB;
                unsigned long *pb = (unsigned long *)*arrA;
                unsigned long *pc = (unsigned long *)*c;
                note("AVDUMP len A=%ld B=%ld C=%ld",
                     pa ? (long)pa[-1] : -1, pb ? (long)pb[-1] : -1,
                     pc ? (long)pc[-1] : -1);
                if (pc) {
                    unsigned long idx = (unsigned long)c0->Eax;
                    (void)idx;
                    {
                        char el[400];
                        int o = 0, k;
                        unsigned short li = *(unsigned short *)((char *)he + 0x12315C);
                        unsigned long i2 = (li > 0 ? li - 1 : 0);
                        unsigned char *base = (unsigned char *)pc + i2 * 0x38;
                        for (k = 0; k < 0x38 && o < 380; k++) o += wsprintfA(el + o, "%02X", base[k]);
                        note("AVDUMP C[last] idx=%u bytes=%s", (unsigned)li, el);
                    }
                }
            }
            {
                unsigned long *a = (unsigned long *)*arrB;'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
