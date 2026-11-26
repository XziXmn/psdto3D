# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'

OLD = """暂不可用
--------
导出 PSD：会生成约 3 KB 的空壳（11 层、每层 4 通道，但无像素数据）。

原因（已定位到根因链）：
* PSD 的层宽来自中间文件 vwd*.gjs 里的 TIFF 标签 ImageWidth(0x0100)；
* 本版程序把宽度写成了 tag 0x0103、缺 0x0100，于是加载器读到宽度 0，不写像素；
* 该中间文件由哪个模块写出尚未定位（zu06 / cmyktiff2_real / exe 已排除）。

要彻底修好，需要在插着加密狗的真机上跑一次
「启动 -> 导入 PSD -> 导入设置 -> 预览 -> 导出 PSD」并抓一份 _dongle.log。"""

NEW = """导出 PSD（2026-11-23 已解决）
----------------------------
程序自己只会写出约 3 KB 的骨架（11 层头正确、但没有像素），
仿真狗现在会在保存对话框应答之后自动补全：

  1. 你点 Export PSD 并选好文件名；
  2. 程序写出 3 KB 骨架；
  3. 约 2.5 秒后，仿真狗用 ok3dtemp 里的 vwd* / vwdt* 中间文件
     重新组装成完整 PSD（11 层、ghm01..ghm11、4370x5197、约 1.07 GB）。

实测：1,067,412,782 字节，与用户提供的参考 PSD 结构逐字段一致、画面一致。

开关：目录里的 _psd_build.txt（存在=启用自动补全；删掉=关闭，只得到 3 KB 骨架）。
依赖：导出前必须先跑过一次「导出 *.tiff」——那一步才会生成 vwd* / vwdt* 中间文件。"""

t = io.open(P, encoding='gbk').read()
assert OLD in t, 'anchor not found'
t = t.replace(OLD, NEW)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
