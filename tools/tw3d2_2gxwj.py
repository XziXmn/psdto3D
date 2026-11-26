# -*- coding: utf-8 -*-
"""把 10.1 工程 (.tw3d2) 反写成 99 工程 (.gxwj)，用于验证 gxwj2tw3d2 的映射是否正确。

    python tools/tw3d2_2gxwj.py in.tw3d2 out.gxwj
"""
import io
import sys


def main():
    src, dst = sys.argv[1], sys.argv[2]
    lines = open(src, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    out = []
    out.append(lines[0])                                    # 路径
    out.append(lines[1])                                    # LPI/Angles/X/Depth
    out.append('39550 0 0 0')                               # 99 标记（层数/宽高在 99 里是 0）
    out.append(lines[3])                                    # banner1
    out.append(lines[4])                                    # banner2
    out.append(' 4.63400000000000E+0004')                   # 99 独有的一行
    out.extend(lines[7:])                                   # DPI 行及其后
    data = '\r\n'.join(out)
    open(dst, 'wb').write(data.encode('gbk', errors='replace'))
    print('反写完成 %s → %s（%d 行 → %d 行）' % (src, dst, len(lines), len(out)))


if __name__ == '__main__':
    main()
