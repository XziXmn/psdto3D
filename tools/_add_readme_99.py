# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '兼容 99 版工程' in t:
    print('already there')
    raise SystemExit(0)

ANCHOR = '五、目录里哪些文件是干什么的'
ADD = """四之补充、兼容 99 版工程（.gxwj）
--------------------------------
 99 版工程标记是 39550，本版是 99100；两者都是 GBK 纯文本，差别只在头部几行。
 工具目录里有转换器，把 99 工程转成本版能直接打开的 .tw3d2：

   工具\\转换99工程.cmd  旧工程.gxwj  新工程.tw3d2  该工程用的psd

 做法：层数/宽/高 从 PSD 头部读出写进第 3 行；第 1 行改成你给的 PSD 路径；
 其余内容（LPI/角度/景深/每层数值/角度表/画线数据）逐字节原样搬过去。
 验证：10.1 → 99 → 10.1 回转，除"作者/保存时间"两行外逐字节一致；
       回转后的工程在本版里能正常打开、预览、导出 TIFF（6,899,708 字节，与原生一致）。

 注意：转换只解决"工程格式"。若 PSD 本身是 5 通道（CMYK+Alpha），
 本版导入器会崩（实测 Access violation in Button8Click），
 请先在 Photoshop 里转成 RGB 8 位 3 通道再导入。

"""
assert ANCHOR in t
t = t.replace(ANCHOR, ADD + ANCHOR, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
