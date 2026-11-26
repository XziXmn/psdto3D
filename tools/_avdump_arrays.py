# -*- coding: utf-8 -*-
"""AV 时把层数组 B=[0x5230a0] 的前 64 个指针打出来，看哪些是空的。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'AVDUMP B[' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''        note("AVDUMP [5230a0]=%08lX [52309c]=%08lX layers=%u", *arrA, *arrB,
             (unsigned)(*(unsigned short *)((char *)he + 0x12315C)));'''
NEW = '''        note("AVDUMP [5230a0]=%08lX [52309c]=%08lX layers=%u", *arrA, *arrB,
             (unsigned)(*(unsigned short *)((char *)he + 0x12315C)));
        {
            unsigned long *b = (unsigned long *)*arrA;
            char line[900];
            int o = 0, k;
            if (b) {
                for (k = 0; k < 64; k++) o += wsprintfA(line + o, "%s%lX", k ? "," : "", b[k]);
                note("AVDUMP B[0..63]=%s", line);
            }
            {
                unsigned long *a = (unsigned long *)*arrB;
                o = 0;
                if (a) {
                    for (k = 0; k < 64; k++) o += wsprintfA(line + o, "%s%lX", k ? "," : "", a[k]);
                    note("AVDUMP A[0..63]=%s", line);
                }
            }
        }'''
assert OLD in s, 'avdump anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
