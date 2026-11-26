# -*- coding: utf-8 -*-
"""逐个导入 sample 里的 PSD，记录是否成功（不改任何东西，只观察）。"""
import ctypes
import os
import struct
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win


def psd_meta(path):
    with open(path, 'rb') as fh:
        head = fh.read(26)
        ch = struct.unpack('>H', head[12:14])[0]
        h, w = struct.unpack('>II', head[14:22])
        depth = struct.unpack('>H', head[22:24])[0]
        mode = struct.unpack('>H', head[24:26])[0]
        fh.seek(4, 1)
        n = struct.unpack('>I', fh.read(4))[0]; fh.seek(n, 1)
        n = struct.unpack('>I', fh.read(4))[0]; fh.seek(n, 1)
        fh.read(8)
        layers = abs(struct.unpack('>h', fh.read(2))[0])
    return ch, w, h, depth, mode, layers


MODES = {0: 'Bitmap', 1: 'Gray', 2: 'Indexed', 3: 'RGB', 4: 'CMYK', 7: 'Multichannel', 9: 'Lab'}


def try_import(pkg, psd):
    sp.run(['taskkill', '/IM', 'psdto3d101.exe', '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    open(os.path.join(pkg, '_dlgopen.txt'), 'w').write(psd + '\n')
    proc = sp.Popen([os.path.join(pkg, 'psdto3d101.exe')], cwd=pkg)
    pid = proc.pid
    hwnd = None
    for _ in range(80):
        m = [x for x in win.windows(pid) if x[1] == 'TForm1']
        if m:
            hwnd = m[0][0]
            break
        time.sleep(0.25)
    time.sleep(1.5)
    win.command(hwnd, 7)
    time.sleep(6)
    dlg = []
    for h, cls, t, vis in win.windows(pid):
        if vis and cls in ('TMessageForm', '#32770'):
            kids = [k[2][:60] for k in win.children(h, 2) if k[1] in ('Static', 'TStaticText') and k[2]]
            dlg.append(kids[:1])
    title = None
    for h, cls, t, vis in win.windows(pid):
        if h == hwnd:
            title = t
    sp.run(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return dlg, title


def main():
    pkg = os.path.abspath(sys.argv[1])
    sample = os.path.join(pkg, 'sample')
    for name in sorted(os.listdir(sample)):
        if not name.lower().endswith('.psd'):
            continue
        path = os.path.join(sample, name)
        ch, w, h, depth, mode, layers = psd_meta(path)
        dlg, title = try_import(pkg, path)
        ok = '✅' if not dlg and title and 'Psdto3d 101' not in (title or '') else '❌'
        print('%-24s %4dch %dx%d %2dbit %-8s %2d层  %s %s'
              % (name, ch, w, h, depth, MODES.get(mode, str(mode)), layers, ok, dlg[:1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
