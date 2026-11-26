# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()

# ini 列表里去掉 fix_cancel
t = t.replace('   fix_cancel=1    「导入设置」点取消不崩\n', '')
# 老段落里的 fix_cancel 说明也去掉
t = t.replace(''' 顺带修了一个原版的小毛病：在「导入设置」里点【取消】原本会弹
 Access violation（Button12Click 里对空指针取下标）。本版加了保护，
 取消后不再崩溃，程序保持原状。开关是 _fix_cancel.txt。
''', '')
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
