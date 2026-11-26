"""完整驱动 PSDTO3D 的导出流程：打开工程 → 预览产视图 → 停止 → 输出tiff。

    python tools/run_export.py --pkg psdto3d2022绿色版 \
        --project "1114/1114/1114-1_10.1_2022.tw3d2" --out out.tif [--preview-timeout 300]

预览阶段会写出 C:\ok3dtemp\vw1..N.bmp，导出阶段写出 vwd*.gjs 和最终 TIFF。
"""
import argparse
import glob
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win

WORKDIR = r'C:\ok3dtemp'
CMD_OPEN, CMD_PREVIEW, CMD_STOP, CMD_TIFF = 3, 12, 13, 16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default='psdto3d2022绿色版')
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--project', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--preview-timeout', type=int, default=300)
    ap.add_argument('--export-timeout', type=int, default=300)
    ap.add_argument('--keep-app', action='store_true')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        os.remove(out)
    for f in glob.glob(os.path.join(WORKDIR, 'vw*.bmp')) + \
             glob.glob(os.path.join(WORKDIR, 'vw*.gjs')) + \
             glob.glob(os.path.join(WORKDIR, 'vwd*.gjs')):
        try:
            os.remove(f)
        except OSError:
            pass

    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg,
                                      os.path.abspath(a.project), out)
    pid = rep['pid']
    time.sleep(6)
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    seen = set()

    def drain(tag):
        for h, cls, title, vis in win.windows(pid):
            if cls in ('TMessageForm', 'TProgressForm') and vis and h not in seen:
                seen.add(h)
                print('  [%s] %s %r' % (tag, cls, title), flush=True)
                for kh, kcls, _ktxt in win.children(h, 3):
                    if kcls == 'TButton':
                        win.click(kh)
                        break
                time.sleep(0.8)

    print('打开工程 ...', flush=True)
    win.command(hwnd, CMD_OPEN)
    time.sleep(12)
    drain('open')

    print('预览 ...', flush=True)
    win.command(hwnd, CMD_PREVIEW)
    t0 = time.time()
    n = 0
    while time.time() - t0 < a.preview_timeout:
        time.sleep(5)
        drain('preview')
        files = [f for f in glob.glob(os.path.join(WORKDIR, 'vw*.bmp'))
                 if re.fullmatch(r'vw\d+\.bmp', os.path.basename(f))]
        if len(files) != n:
            n = len(files)
            print('  t=%.0fs 视图 %d' % (time.time() - t0, n), flush=True)
        if n >= 13:
            break
    print('停止预览', flush=True)
    win.command(hwnd, CMD_STOP)
    time.sleep(4)
    drain('stop')

    print('输出tiff ...', flush=True)
    win.command(hwnd, CMD_TIFF)
    t0 = time.time()
    while time.time() - t0 < a.export_timeout:
        time.sleep(5)
        drain('tiff')
        if os.path.exists(out):
            print('  输出出现 t=%.0fs  %d 字节' % (time.time() - t0, os.path.getsize(out)),
                  flush=True)
            break
    if os.path.exists(out):
        d = open(out, 'rb').read(16)
        print('  头 16 字节: %s' % d.hex(' '))
    else:
        g = glob.glob(os.path.join(WORKDIR, 'vwd*.gjs'))
        print('  没有输出；vwd*.gjs = %d' % len(g))
        if g:
            print('  %s 头: %s' % (os.path.basename(g[0]),
                                   open(g[0], 'rb').read(16).hex(' ')))
    if not a.keep_app:
        os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0 if os.path.exists(out) else 2


if __name__ == '__main__':
    sys.exit(main())
