# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if 'nil_tolerant' in t:
    print('already there')
    raise SystemExit(0)

OLD = '   layers_up=1     解除 33 层限制（0 = 恢复原版，34 层以上预览会报错）\n'
NEW = ('   layers_up=1     解除 33 层限制（0 = 恢复原版，34 层以上预览会报错）\n'
       '   nil_tolerant=1  容忍"某层数组为空"的崩溃点（0x50A001），图层特别多时必须开\n')
assert OLD in t
t = t.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated')
