# -*- coding: utf-8 -*-
"""移除 fix_cancel 补丁：它会破坏"打开工程"（实测触发 I/O error 103）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'fix_cancel_removed' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''        if (cfg_on("fix_cancel", 1, "_fix_cancel.txt")) {
            HMODULE he3 = GetModuleHandleA(0);
            if (he3) patch_cancel_guard(he3);
        }'''
if OLD not in s:
    # 允许有细微差异，做宽松匹配
    import re
    m = re.search(r'\n\s*if \(cfg_on\("fix_cancel".*?\n\s*\}\n', s, re.S)
    if not m:
        print('anchor not found')
        raise SystemExit(1)
    s = s[:m.start()] + '\n        /* fix_cancel_removed: 该补丁会破坏打开工程，已停用 */\n' + s[m.end():]
else:
    s = s.replace(OLD, '        /* fix_cancel_removed: 该补丁会破坏打开工程，已停用 */', 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
