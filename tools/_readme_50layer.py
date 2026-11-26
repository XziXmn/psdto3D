# -*- coding: utf-8 -*-
"""把 50 层突破写进说明文档。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '50 层工程' in t and 'zu06' in t:
    print('already there')
    raise SystemExit(0)

ANCHOR = '五、目录里哪些文件是干什么的'
ADD = """四之补充三、50 层工程（2026-11-25 突破）
--------------------------------------
 之前 50 层工程会报 Invalid numeric input / Invalid floating point，
 原因不是图层数上限，而是**许可证数据通道没接管**：

 真正读 PSD、填层记录的模块是 zu06.dll，它有一套自己独立的加密狗会话，
 走 WriteFile/ReadFile 存储模型（不是主程序的 DeviceIoControl）：

   write addr=003A dtl=58   会话握手
   write addr=000A dtl=10   索要许可证块
   read  addr=000A dtl=501  返回 501 字节许可证数据

 插狗时真狗返回真实许可证，一切正常；
 不插狗时仿真器回的是「导出会话」的旧抓包，许可证值全变 0，调用方除零。

 本版处理：
 1. 接管 zu06.dll 自己的 IAT（CreateFile/DeviceIoControl/ReadFile/WriteFile 等 15 项）
 2. 回放表（replay_table.h）重建为 116 条事件：
      前 43 条 = 真狗 50 层导入会话的完整记录（含 zu06 的 003A / 002A / 000A 通道）
      后 73 条 = 导出阶段的历史抓取
 3. 开关 psdto3d_green.ini 里的 zu06_patch_iat=1（本版默认已开）

 实测（1575×1890 / 50 层工程，全程不插狗）：
   打开工程  OK  标题显示 1114 .psd + 1114 -1.gxwj
   预览      OK  无弹框
   导出 TIFF OK  11,418,702 字节
   导出 PSD  OK  163,722,366 字节（1575×1890，13 层，图层完整）

 回归（32 层工程 / 4370×5197）：打开、导入、预览、导出 TIFF/PSD 全部正常。

"""
assert ANCHOR in t
t = t.replace(ANCHOR, ADD + ANCHOR, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
