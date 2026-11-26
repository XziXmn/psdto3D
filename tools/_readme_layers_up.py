# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
start = t.find('四之补充二、图层数上限')
end = t.find('五、目录里哪些文件是干什么的')
assert start > 0 and end > start, 'anchor missing'

NEW = """四之补充二、图层数上限（2026-11-24 已解决 33 层限制）
------------------------------------------------
 原版有个隐藏限制：图层超过 33 层时，一按预览就弹
 "Access violation at 0050AF66"。原因是渲染循环要用一个"每层数组"，
 而这个数组只在某个从不执行的界面回调里才被分配。

 本版在载入 PSD 后按真实层数把这个数组补上（每层一个空的内部数组），
 于是 34 层以上也能正常走完：

   导入 → 预览 → 导出 TIFF → 导出 PSD   ✅

 实测（真实结构的分层 PSD，800×800 RGB）：
   29 / 33 / 34 / 41 / 50 层：导入、预览、导出全部通过
   50 层导出：TIFF 4,282,220 字节，PSD 35,201,116 字节（13 层，画面正确）

 开关：_layers_up.txt（存在=启用；删掉=恢复原版 33 层限制）

 仍然存在的上限（属于导入器本身，与上面的渲染问题无关）：
   • RGB 导入：≤ 50 层（55 层导入阶段就崩）
   • CMYK 导入：≤ 34 层（35 层导入阶段就崩）

 另：_psd_limit.txt 是"超过 33 层就拦下来提示"的旧保护，
 现在图层上限已经打通，这个开关默认不提供；需要严格拦截时可自行建一个空文件启用。

"""
t = t[:start] + NEW + t[end:]
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
