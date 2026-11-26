"""Field-level bisection for the `Invalid numeric input` dialog on project open.

Generates variants of a .tw3d2 project, opens each in a target green build via
the dialog-stub launcher, and reports which variant still pops a dialog.

    python tools/bisect_numeric.py <pkg> <project.tw3d2> [--exe name] [--seconds 18]
"""
import argparse
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win


def dialogs(pid):
    out = []
    for h, cls, title, vis in win.windows(pid):
        if cls == '#32770' and vis:
            texts = [t for _, c, t in win.children(h, maxdepth=1) if c == 'Static' and t]
            out.append(' | '.join(texts))
    return out


def run_one(pkg, exe_name, project, seconds):
    exe = os.path.join(pkg, exe_name)
    rep, _ = dialogless_launch.launch(exe, pkg, project,
                                      os.path.join(pkg, '_bisect.tif'))
    pid = rep['pid']
    try:
        time.sleep(3)
        forms = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if not forms:
            return 'NO MAIN WINDOW', 0
        hwnd = forms[0][0]
        win.command(hwnd, 3)
        deadline = time.time() + seconds
        while time.time() < deadline:
            d = dialogs(pid)
            if d:
                return d[0][:90], 0
            time.sleep(1.5)
        return 'CLEAN (no dialog in %ds)' % seconds, 1
    finally:
        os.system('taskkill /PID %d /F >nul 2>&1' % pid)


def load(path):
    return open(path, 'rb').read().split(b'\r\n')


def save(lines, dst):
    open(dst, 'wb').write(b'\r\n'.join(lines))


def variants(src):
    """Yield (name, lines) for every bisect variant of the project text."""
    L = load(src)
    n = int(L[2].split()[1]) if L[2].split()[:1] == [b'99100'] else None
    # layout: 0..7 header, 8..8+n-1 angle ints, 8+n..8+2n-1 layer lines, rest curves
    a0, l0 = 8, 8 + n
    c0 = 8 + 2 * n
    header, angles, layers, curves = L[:a0], L[a0:l0], L[l0:c0], L[c0:]

    yield 'asis', L
    yield 'nocurves', L[:c0]
    z = list(curves)
    for i, line in enumerate(z):
        m = re.match(rb'^(\d+ \d+ \d+ (\d+))\r?$', line)
        pass
    # zero the coordinate payloads: every non-empty line after a curve header
    out = []
    expect = 0
    for line in curves:
        if line == b'':
            out.append(line)
            expect = 0
            continue
        parts = line.split()
        if expect == 0 and len(parts) == 4:
            expect = int(parts[3])
            out.append(line)
        else:
            toks = [b'0'] * (len(parts) - (1 if line.endswith(b' ') else 0))
            out.append(b' '.join(toks) + (b' ' if line.endswith(b' ') else b''))
            expect = 0
    yield 'coords0', L[:c0] + out
    yield 'layers1', L[:l0] + [b'8 1  1.00000000000000E+0000'] * n + curves
    yield 'angles10', L[:a0] + [b'10'] * n + L[l0:]
    h2 = list(header)
    h2[1] = b' 1.00000000000000E+0001 17 5  1.00000000000000E+0000'
    yield 'hdr2min', h2 + L[a0:]
    h8 = list(header)
    h8[7] = b' 1.00000000000000E+0003  1.00000000000000E+0001  1.00000000000000E+0001 2 8'
    yield 'hdr8min', h8 + L[a0:]
    # strip trailing spaces on every line
    yield 'notrail', [x.rstrip() for x in L]
    # drop empty separator lines inside the curve block
    yield 'noempty', L[:c0] + [x for x in curves if x != b'']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg')
    ap.add_argument('project')
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--seconds', type=int, default=18)
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    src = os.path.abspath(a.project)
    tmpdir = os.path.join(pkg, '_bisect')
    os.makedirs(tmpdir, exist_ok=True)
    results = []
    for name, lines in variants(src):
        dst = os.path.join(tmpdir, 'v_%s.tw3d2' % name)
        save(lines, dst)
        try:
            msg, ok = run_one(pkg, a.exe, dst, a.seconds)
        except Exception as e:
            msg, ok = 'ERROR %s' % e, 0
        results.append((name, ok, msg))
        print('%-10s %s  %s' % (name, 'OK ' if ok else 'FAIL', msg))
    clean = [n for n, ok, _ in results if ok]
    print('\nclean variants: %s' % (clean or 'NONE'))


if __name__ == '__main__':
    sys.exit(main())
