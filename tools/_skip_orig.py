# -*- coding: utf-8 -*-
"""Skip the original writepsd entirely: write the full PSD ourselves and return 0."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'SKIP_ORIG' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    if (o_writepsd && (void *)o_writepsd != (void *)writepsd_shim)
        r = o_writepsd(file, dir, a3, a4, a5, a6, layers, w, h, spp);'''
NEW = '''    /* SKIP_ORIG: 原实现只写骨架，直接用它会覆盖我们的结果，所以不再调用 */
    (void)r;'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
