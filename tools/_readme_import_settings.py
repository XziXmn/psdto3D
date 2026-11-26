# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '导入设置也能用 99 工程' in t:
    print('already there')
    raise SystemExit(0)

ANCHOR = ' 如果某台机器上不想启用这个功能，删掉 _gxwj.txt 即可（回到只认 .tw3d2）。'
ADD = """ 导入设置也能用 99 工程：在「导入设置」里选 .gxwj 同样会走透明转换，
 实测能正确应用（导出 TIFF 仍为 6,899,708 字节）。
 文件对话框的过滤器是全局替换的，「打开工程」和「导入设置」两处都会显示 *.gxwj。

 顺带修了一个原版的小毛病：在「导入设置」里点【取消】原本会弹
 Access violation（Button12Click 里对空指针取下标）。本版加了保护，
 取消后不再崩溃，程序保持原状。开关是 _fix_cancel.txt。

""" + ANCHOR
assert ANCHOR in t
t = t.replace(ANCHOR, ADD, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
