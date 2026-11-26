# -*- coding: utf-8 -*-
"""继续定位：每层值区段到底哪儿不对。
   A) 用程序自己保存的 50 行每层值（x.tw3d2）
   B) 用 99 转换的 50 行每层值
   C) 用 99 的前 32 行 + 参照的角度表
"""
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
SAVED = r'C:\bio\x.tw3d2'
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
    p = r'C:\bio\v_%s.tw3d2' % name
    io.open(p, 'wb').write('\r\n'.join(lines).encode('gbk', errors='replace'))
    return p


def main():
    ref = io.open(REF, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    conv = io.open(CONV, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    saved = io.open(SAVED, 'rb').read().decode('gbk', errors='replace').split('\r\n')

    print('参照 8..11 :', ref[8:12])
    print('保存 8..11 :', saved[8:12])
    print('转换 8..11 :', conv[8:12])

    cases = {}
    # A: 参照头 + 程序保存的 50 行 + 参照剩余
    a = list(ref)
    a[0] = NEWPSD
    a[2] = '99100 50 1575 1890'
    a = a[:8] + saved[8:58] + a[8 + 32:]
    cases['A_saved50'] = a

    # B: 参照头 + 转换的 50 行 + 参照剩余
    b = list(ref)
    b[0] = NEWPSD
    b[2] = '99100 50 1575 1890'
    b = b[:8] + conv[8:58] + b[8 + 32:]
    cases['B_conv50'] = b

    # C: 完全照抄保存文件（程序自己存的 73 行），只改路径
    c = list(saved)
    c[0] = NEWPSD
    cases['C_saved_all'] = c

    for name, lines in cases.items():
        p = save(lines, name)
        err, title = test(p)
        print('%-12s 行数%-5d -> %-26s | %s' % (name, len(lines), (err or 'OK')[:26], title))
    return 0


if __name__ == '__main__':
    sys.exit(main())
