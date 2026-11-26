# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()
if '直接打开 99 版工程' in t:
    print('already there')
    raise SystemExit(0)

OLD_START = t.find('四之补充、兼容 99 版工程')
OLD_END = t.find('五、目录里哪些文件是干什么的')
assert OLD_START > 0 and OLD_END > OLD_START

NEW = """四之补充、兼容 99 版工程（.gxwj）—— 现在可以直接打开
--------------------------------------------
 99 版工程标记是 39550，本版是 99100；两者都是 GBK 纯文本，差别只在头部几行。
 本版已经在读取层做了透明转换：

   * 「打开工程」的文件对话框里，文件类型已经包含 *.gxwj，
     直接选 99 工程即可打开，不需要任何手工转换；
   * 内部流程：读到 .gxwj → 按规则转换 → 交给程序；
   * 层数/宽/高 自动从工程指向的 PSD 头部读出（99 工程里这三项是 0）；
     PSD 路径找不到时，会自动到 .gxwj 同目录找同名 .psd。

 实测：用 99 工程打开 → 预览 → 导出 TIFF 6,899,708 字节、导出 PSD 1,067,412,782 字节，
 与同一工程经手工转换后再打开的结果完全一致。

 如果某台机器上不想启用这个功能，删掉 _gxwj.txt 即可（回到只认 .tw3d2）。

 备用方案：工具\\ 目录里还有独立转换器（转换99工程.cmd），
 适合批量转换或想先看看转换结果的情况。

 注意：转换只解决"工程格式"。若 PSD 本身读不进来（例如个别特殊 PSD），
 那是导入器对 PSD 的限制，与工程格式无关。

"""
t = t[:OLD_START] + NEW + t[OLD_END:]
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
