# -*- coding: utf-8 -*-
"""让 [0x523230] 在任何层数下都补上（不只是 >33 层）。
   修「导入设置点取消 → 0x5125FA 空指针」这个原版缺陷。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cancel_fix' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '    if (*slot || layers == 0 || layers <= 33) return 0;      /* 33 层以内程序自己没问题 */'
NEW = '    /* cancel_fix: 任何层数都补，否则导入设置点取消会读空指针（0x5125FA） */\n    if (*slot || layers == 0) return 0;'
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
