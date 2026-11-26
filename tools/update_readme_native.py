# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()

OLD_START = t.find('导出 PSD（2026-11-23 已解决）')
OLD_END = t.find('依赖：导出前必须先跑过一次')
if OLD_START < 0 or OLD_END < 0:
    print('anchor not found')
    raise SystemExit(1)
tail = t[t.rfind('\n', 0, OLD_END) + 1:]

NEW = """导出 PSD（2026-11-23 · 原生实现）
----------------------------
程序原本调用 zu06.dll 的 writepsd，只写出约 3 KB 的骨架（层头正确、没有像素）。
现在仿真狗在内存里把这次调用接管了：

  1. 你点 Export PSD 并选好文件名；
  2. 程序照常调用 writepsd —— 但执行的是仿真狗里的实现；
  3. 它直接用 ok3dtemp 里的 vwd* / vwdt* 中间文件写出完整 PSD，
     11 层、ghm01..ghm11、4370x5197，约 1.07 GB；
  4. 程序认为导出成功并继续后续流程。

实测：1,067,412,782 字节，md5 775A3882…（与手工组装的完全一致）。

开关：_native_psd.txt（存在=启用原生接管；删掉=回到程序自己的 3 KB 骨架）。
依赖：导出前必须先跑过一次「导出 *.tiff」——那一步才会生成 vwd* / vwdt* 中间文件。
"""

t2 = t[:OLD_START] + NEW + tail
io.open(P, 'w', encoding='gbk', errors='replace').write(t2)
print('readme updated')
