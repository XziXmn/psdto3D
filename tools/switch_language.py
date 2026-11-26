"""Switch the 99 build to Chinese via its Languages menu and report what it persists."""
import ctypes
import hashlib
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

u = ctypes.windll.user32


def snapshot(root):
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for n in files:
            p = os.path.join(dirpath, n)
            try:
                out[p] = (os.path.getsize(p), hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16])
            except OSError:
                pass
    return out


def main():
    pkg = os.path.abspath(sys.argv[1])
    exe = sys.argv[2]
    lang_id = int(sys.argv[3])
    shot = sys.argv[4]
    before = snapshot(pkg)
    proc = sp.Popen([os.path.join(pkg, exe)], cwd=pkg)
    time.sleep(5)
    pid = proc.pid
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    print('main', hwnd)
    win.capture(hwnd, shot + '_before.png')
    win.command(hwnd, lang_id)
    time.sleep(3)
    for h, cls, title, vis in win.windows(pid):
        if cls in ('TMessageForm', '#32770') and vis:
            print('dialog after switch:', cls, repr(title))
            for kh, kcls, ktxt in win.children(h, maxdepth=1):
                if kcls == 'Static' and ktxt:
                    print('   ', ktxt[:80])
            for kh, kcls, ktxt in win.children(h, maxdepth=2):
                if kcls == 'TButton':
                    win.click(kh)
                    break
            time.sleep(1)
    win.capture(hwnd, shot + '_after.png')
    time.sleep(1)
    after = snapshot(pkg)
    print('changed files:')
    for p in sorted(after):
        if before.get(p) != after[p]:
            print('   ', p, before.get(p), '->', after[p])
    print('new files:')
    for p in sorted(set(after) - set(before)):
        print('   ', p)
    proc.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())
