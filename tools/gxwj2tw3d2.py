# -*- coding: utf-8 -*-
"""把 PSDTO3D 99 的工程文件（.gxwj，标记 39550）转成 10.1/2022 的 .tw3d2（标记 99100）。

两个格式都是 GBK 纯文本、CRLF 分隔，差异只有头部几行：

    99  (.gxwj)                    10.1 / 2022 (.tw3d2)
    0  <psd 路径>                  <psd 路径>                （需重定向到本机实际文件）
    1   LPI Angles X Depth         同
    2  39550 0 0 0                99100 <层数> <宽> <高>    （由 PSD 头部读出）
    3  banner1                     同
    4  banner2                     同
    5   <99 独有的大数>            Author: <作者>
    6  <DPI 行>                     <保存时间>
    7  ...                          <DPI 行>
    8+ 图层整数 / 角度行 / 曲线块   整体后移一行，内容逐字节相同

用法：
    python tools/gxwj2tw3d2.py in.gxwj out.tw3d2 --psd X.psd [--author 名字]
"""
import argparse
import io
import struct
import sys
import time


def psd_head(path):
    """返回 (宽, 高, 图层数)。图层数取 PSD 图层信息块里的计数。"""
    with open(path, 'rb') as fh:
        head = fh.read(26)
        if head[:4] != b'8BPS':
            raise SystemExit('%s 不是 PSD' % path)
        h, w = struct.unpack('>II', head[14:22])        # PSD 头顺序是 高、宽
        n = struct.unpack('>I', fh.read(4))[0]          # 颜色模式数据
        fh.seek(n, 1)
        n = struct.unpack('>I', fh.read(4))[0]          # 图像资源
        fh.seek(n, 1)
        fh.read(4)                                      # 图层与蒙版长度
        fh.read(4)                                      # 图层信息长度
        cnt = abs(struct.unpack('>h', fh.read(2))[0])
    return w, h, cnt


def convert(src, dst, psd, author='', newline='\r\n'):
    raw = io.open(src, 'rb').read().decode('gbk', errors='replace')
    lines = raw.split('\r\n')
    if len(lines) < 7:
        raise SystemExit('源文件行数不足，可能不是 99 工程')
    tag = lines[2].split(' ')[0]
    if tag != '39550':
        raise SystemExit('源文件标记是 %s，不是 39550（不是 99 工程）' % tag)

    w, h, layers = psd_head(psd)
    ts = time.strftime('%Y/%m/%d %H:%M:%S')

    out = []
    out.append(psd)                       # 0 路径
    out.append(lines[1])                  # 1 LPI/Angles/X/Depth
    out.append('99100 %d %d %d' % (layers, w, h))   # 2 标记+层数+宽高
    out.append(lines[3])                  # 3 banner1
    out.append(lines[4])                  # 4 banner2
    out.append('Author: %s' % author)     # 5 作者
    out.append(ts)                        # 6 保存时间
    tail = lines[6:]
    if tail and tail[-1] == '':           # 源文件末尾的空元素不写出去（与官方保存结果一致）
        tail = tail[:-1]
    out.extend(tail)                      # 7+ 原 DPI 行及其后全部

    data = newline.join(out)
    io.open(dst, 'wb').write(data.encode('gbk', errors='replace'))
    print('转换完成：%s → %s（%d 层 %dx%d，源 %d 行 → 目标 %d 行）'
          % (src, dst, layers, w, h, len(lines), len(out)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--psd', required=True, help='工程指向的 PSD（用来取宽高与层数）')
    ap.add_argument('--author', default='')
    a = ap.parse_args()
    return convert(a.src, a.dst, a.psd, a.author)


if __name__ == '__main__':
    sys.exit(main())
