"""Run open-project -> export-TIFF and watch every window / file the export creates."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win

CMD_OPEN, CMD_EXPORT_TIFF = 3, 16


def main():
    pkg = os.path.abspath(sys.argv[1])
    project = os.path.abspath(sys.argv[2])
    out = os.path.abspath(sys.argv[3])
    if os.path.exists(out):
        os.remove(out)
    rep, hproc = dialogless_launch.launch(os.path.join(pkg, 'psdto3d101.exe'), pkg, project, out)
    pid = rep['pid']
    time.sleep(5)
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]

    print('open project')
    win.command(hwnd, CMD_OPEN)
    time.sleep(8)
    for h, cls, title, vis in win.windows(pid):
        if cls in ('TMessageForm', 'TProgressForm') or 'Progress' in cls:
            print('   dialog:', cls, repr(title), vis)

    print('export tiff')
    win.command(hwnd, CMD_EXPORT_TIFF)
    seen = set()
    for i in range(24):
        time.sleep(2)
        for h, cls, title, vis in win.windows(pid):
            key = (cls, title)
            if vis and key not in seen:
                seen.add(key)
                print('   t=%.0fs %-16s %r' % (i * 2, cls, title))
        if os.path.exists(out):
            print('   output appeared at t=%.0fs' % (i * 2))
            break
    print('output exists:', os.path.exists(out))
    if os.path.exists(out):
        print('size', os.path.getsize(out))
    new = []
    tmp = r'C:\ok3dtemp'
    if os.path.isdir(tmp):
        now = time.time()
        for n in os.listdir(tmp):
            p = os.path.join(tmp, n)
            if os.path.isfile(p) and now - os.path.getmtime(p) < 180:
                new.append((n, os.path.getsize(p)))
    print('recent temp files:', new[:10])
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
