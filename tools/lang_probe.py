"""Check whether the .inf 'language flag' switches the UI to Chinese in each build.

The 99 build stores it as the last integer of the first line (0 = English, 1 = Chinese).
For 10.1 / 2022 the same position is tested; each run is captured for comparison.
"""
import os
import shutil
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win


def read_inf(path):
    return open(path, 'rb').read().decode('gbk', 'replace')


def write_inf(path, text):
    open(path, 'wb').write(text.encode('gbk', 'replace'))


def set_flag(text, value):
    lines = text.split('\r\n')
    parts = lines[0].split()
    parts[-1] = str(value)
    lines[0] = ' '.join(parts)
    return '\r\n'.join(lines)


def run_and_shoot(pkg, exe, shot, flag=None):
    inf = None
    for n in os.listdir(pkg):
        if n.lower().endswith('.inf'):
            inf = os.path.join(pkg, n)
            break
    original = None
    if inf and flag is not None:
        original = read_inf(inf)
        write_inf(inf, set_flag(original, flag))
    proc = sp.Popen([os.path.join(pkg, exe)], cwd=pkg)
    time.sleep(5)
    pid = proc.pid
    mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
    if not mw:
        proc.kill()
        return 'no window'
    win.capture(mw[0][0], shot)
    # read the first menu caption to judge the language
    import ctypes
    u = ctypes.windll.user32
    u.GetMenu.restype = ctypes.c_void_p
    menu = u.GetMenu(ctypes.c_void_p(mw[0][0]))
    caps = []
    for i in range(u.GetMenuItemCount(ctypes.c_void_p(menu))):
        buf = ctypes.create_unicode_buffer(64)
        u.GetMenuStringW(ctypes.c_void_p(menu), i, buf, 64, 0x400)
        caps.append(buf.value)
    proc.kill()
    time.sleep(0.5)
    if inf and original is not None:
        write_inf(inf, original)
    return caps


def main():
    tests = [
        ('99', r'C:\Home\Workspace\UGit\psdto\psdto3d99绿色版\psdto3d99绿色版', 'psdto3d.exe'),
        ('10.1', r'C:\Home\Workspace\UGit\psdto\psdto3d10.1绿色版', 'psdto3d101.exe'),
        ('2022', r'C:\Home\Workspace\UGit\psdto\psdto3d2022绿色版', 'psdto3d101.exe'),
    ]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_test')
    os.makedirs(out, exist_ok=True)
    for tag, pkg, exe in tests:
        for flag in (0, 1):
            shot = os.path.join(out, 'lang_%s_%d.png' % (tag.replace('.', '_'), flag))
            caps = run_and_shoot(pkg, exe, shot, flag)
            print('%-5s flag=%d menus=%s' % (tag, flag, caps))
    return 0


if __name__ == '__main__':
    sys.exit(main())
