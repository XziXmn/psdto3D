# -*- coding: utf-8 -*-
"""给真实对话框分支也加上层数检查（用户点确定后立刻判断）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'psd_guard_dialog(file)' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''    note("EMU gofn exhausted");
    if (o_gofna) return ((BOOL (WINAPI *)(void *))o_gofna)(p);
    return FALSE;
}'''
NEW = '''    note("EMU gofn exhausted");
    if (o_gofna) {
        BOOL ok = ((BOOL (WINAPI *)(void *))o_gofna)(p);
        if (ok && file && psd_guard_dialog(file)) return FALSE;
        return ok;
    }
    return FALSE;
}'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
