# -*- coding: utf-8 -*-
"""找出勾线块数量的上限：把 1114 的勾线块截断到 N 块再试。"""
import io
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

PKG = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1'
CONV = os.path.join(PKG, '_gxwj_conv.tw3d2')
NEWPSD = r'C:\bio\x.psd'
HEAD = 108          # 8 头 + 50 层值 + 50 角度


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


def take_blocks(tail, n):
    """取前 n 个块（每块 = 头行 + 坐标行）"""
    out = []
    i = 0
    got = 0
    while i < len(tail) and got < n:
        if not tail[i].strip():
            break
        out.append(tail[i])
        i += 1
        if i < len(tail) and tail[i].strip():
            out.append(tail[i])
            i += 1
        got += 1
    return out


def main():
    conv = io.open(CONV, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    conv[0] = NEWPSD
    head, tail = conv[:HEAD], conv[HEAD:]
    print('总块数约', len([x for x in tail if x.strip()]) // 2)

    for n in (0, 1, 5, 20, 50, 100, 200, 400):
        lines = head + take_blocks(tail, n)
        p = r'C:\bio\blk_%03d.tw3d2' % n
        io.open(p, 'wb').write('\r\n'.join(lines).encode('gbk', errors='replace'))
        err, title = test(p)
        print('块数%-4d 行数%-5d -> %-26s | %s' % (n, len(lines), (err or 'OK')[:26], title))
    return 0


if __name__ == '__main__':
    sys.exit(main())
