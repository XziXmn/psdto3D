# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '工程里的 PSD 路径' in t:
    print('already there')
    raise SystemExit(0)

ANCHOR = '五、目录里哪些文件是干什么的'
ADD = """七、工程文件里的 PSD 路径会自动修复
--------------------------------
 工程（.tw3d2/.tw3d/.gxwj）第一行写的是 PSD 的绝对路径，
 从别的电脑拷过来时通常指向不存在的盘符，打开时会报错或弹
 "Confirm / continue?"。

 现在的处理：打开工程时先看那行路径是否存在；
 不存在就在**工程同目录**里找同名 .psd（目录里只有一个 .psd 时也用它），
 找到就把工程改指向它再交给程序，日志里会写：

   tw3d2: PSD 路径修复 E:\\别的机器\\海报.psd -> D:\\活\\海报.psd

 找不到时不改动，行为与原来一致（程序自己报错）。

"""
assert ANCHOR in t
t = t.replace(ANCHOR, ADD + ANCHOR, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated')
