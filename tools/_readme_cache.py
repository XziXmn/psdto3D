# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '关于缓存和日志' in t:
    print('already there')
    raise SystemExit(0)

ANCHOR = '五、目录里哪些文件是干什么的'
ADD = """六、关于缓存和日志（常见疑问）
--------------------------
 1. ok3dtemp 临时目录
    程序把每次预览/导出的中间文件都写在 %%SystemDrive%%\\ok3dtemp
    （一次 4370x5197 的预览大约 1.5 GB 以上）。
    这个目录程序自己**不会**清理，会一直累积。
    本包附了「清理缓存.cmd」，双击确认后会清空它（不影响已导出的成品），
    建议每隔一段时间点一次。

 2. _dongle.log
    这是仿真狗的运行日志，只用于排错。
    * 每次启动时如果它超过 4 MB，会被自动清空重来；
    * 想彻底不要日志：把 psdto3d_green.ini 里的 log 改成 0；
    * 排查问题时再改回 1，重现一次问题后把日志发出来即可。

 3. ok3d_ascii_*.psd
    路径含中文时，程序需要 ASCII 路径，我们会在 ok3dtemp 里建一个硬链接。
    这些文件每次启动会自动清掉，不用管。

"""
assert ANCHOR in t
t = t.replace(ANCHOR, ADD + ANCHOR, 1)
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
