# -*- coding: utf-8 -*-
"""以能打开的 10.1 参照工程为骨架，一步步替换成 1114 的数据，找出哪一步开始崩。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'
REF = r'C:\Home\Workspace\UGit\psdto\test\0《生化危机：爆发夜》第一人称海报汉化\0《生化危机：爆发夜》第一人称海报汉化.tw3d2'
CONV = os.path.join(PKG, '_gxwj_conv.tw3d2')
NEWPSD = r'C:\bio\x.psd'


def test(path):
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    io.open(os.path.join(PKG, '_dlgopen.txt'), 'wb').write((path + '\r\n').encode('gbk'))
    proc = sp.Popen([os.path.join(PKG, 'psdto3d101.exe')], cwd=PKG)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    time.sleep(1.5)
    win.command(hwnd, 3)
    err = ''
    t0 = time.time()
    while time.time() - t0 < 12:
        for h, cls, t, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm'):
                kids = [k[2][:40] for k in win.children(h, 3) if k[2] and len(k[2]) > 3]
                err = kids[0] if kids else '(dialog)'
                break
        if err:
            break
        time.sleep(0.4)
    title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return err, (title[0] if title else '')


def save(lines, name):
    p = r'C:\bio\step_%s.tw3d2' % name
    io.open(p, 'wb').write('\r\n'.join(lines).encode('gbk', errors='replace'))
    return p


def main():
    ref = io.open(REF, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    conv = io.open(CONV, 'rb').read().decode('gbk', errors='replace').split('\r\n')

    steps = []

    # 0: 参照原样
    steps.append(('0_ref', list(ref)))

    # 1: 只改 PSD 路径
    a = list(ref)
    a[0] = NEWPSD
    steps.append(('1_path', a))

    # 2: 再改标记行（32层 4370x5197 -> 50层 1575x1890）
    b = list(a)
    b[2] = '99100 50 1575 1890'
    steps.append(('2_marker', b))

    # 3: 用转换文件的 50 行每层值替换参照的 32 行
    c = b[:8] + conv[8:58] + b[8 + 32:]
    steps.append(('3_layerints', c))

    # 4: 角度表也换成 50 行
    d = c[:58] + conv[58:108] + c[58 + 32:]
    steps.append(('4_angles', d))

    # 5: 完全用转换文件
    e = list(conv)
    e[0] = NEWPSD
    steps.append(('5_full', e))

    for name, lines in steps:
        p = save(lines, name)
        err, title = test(p)
        print('%-12s 行数%-5d -> %-26s | %s' % (name, len(lines), (err or 'OK')[:26], title))
    return 0


if __name__ == '__main__':
    sys.exit(main())
