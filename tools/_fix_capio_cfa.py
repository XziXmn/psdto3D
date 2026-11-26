# -*- coding: utf-8 -*-
"""修正：cap_io 模式下只直通"设备路径"，普通文件仍走我们的转换/修复逻辑。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cap_io() && is_dongle_path' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    if (cap_io()) {
        note("CAP cfa %s acc=%08lX share=%lX disp=%lu", name, acc, share, disp);
        h = o_cfa(name, acc, share, sa, disp, flags, tmpl);
        note("CAP cfa -> %p", h);
        return h;
    }'''
NEW = '''    if (cap_io() && is_dongle_path(name)) {
        /* 设备路径直通真狗；普通文件仍要走 gxwj 转换/路径修复 */
        note("CAP cfa(dev) %s acc=%08lX share=%lX disp=%lu", name, acc, share, disp);
        h = o_cfa(name, acc, share, sa, disp, flags, tmpl);
        note("CAP cfa(dev) -> %p", h);
        return h;
    }'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
