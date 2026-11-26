# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '图层数上限' in t:
    print('already there')
    raise SystemExit(0)

ANCHOR = '五、目录里哪些文件是干什么的'
ADD = """四之补充二、图层数上限（实测数据 + 拦截保护）
------------------------------------------
 程序对"层数"有三道不同的限制，实测（用真实结构的分层 PSD 逐级验证）：

   预览 / 渲染：≤ 33 层        （第 34 层开始必崩：会读一个从未分配的数组）
   RGB 导入   ：≤ 50 层        （55 层导入即崩）
   CMYK 导入  ：≤ 34 层        （35 层导入即崩）

 实际影响：超过 33 层的 PSD 能导入，但一按预览就会弹
 "Access violation at 0050AF66" 然后不可用。所以日常请把图层控制在 33 层以内。

 为此本版加了保护：选择 PSD 时会先读它的层数，超过 33 层直接弹中文提示
 （写清当前层数和上限），并取消这次导入，不再让程序崩掉。

 开关：_psd_limit.txt（存在=启用层数检查；删掉=不做检查，恢复原版行为）

 已确认无法靠配置规避：层数上限是程序内部的固定数组设计，
 与内存、分辨率、颜色模式都无关（100×100 的小图 41 层同样触发）。

"""
assert ANCHOR in t
t = t.replace(ANCHOR, ADD + ANCHOR, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
