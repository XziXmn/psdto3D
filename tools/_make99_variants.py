# -*- coding: utf-8 -*-
"""99 版对照实验：同一个 50 层工程，分别指向 50 层 PSD 和 32 层 PSD。"""
import io
import os

PKG = r'C:\Home\Workspace\UGit\psdto\_work\99test'


def make(src, psd, dst):
    d = io.open(src, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    d[0] = psd
    io.open(dst, 'wb').write('\r\n'.join(d).encode('gbk', errors='replace'))
    return dst


if __name__ == '__main__':
    make(os.path.join(PKG, 'p50.gxwj'), r'C:\bio\a.psd', os.path.join(PKG, 'p50_32psd.gxwj'))
    make(os.path.join(PKG, 'p50.gxwj'), r'C:\bio\x.psd', os.path.join(PKG, 'p50_50psd.gxwj'))
    print('生成 p50_32psd.gxwj / p50_50psd.gxwj')
