"""End-to-end test of psdto3d: open project -> preview -> export TIFF, no user input.

The file dialogs are answered by in-memory stubs (dialogless_launch.py), every
message box is dismissed by clicking its OK button, and the produced TIFF is
validated (magic, IFD tags: size/bits/compression/samples).

    python run_e2e.py --pkg psdto3d2022绿色版 --project psdto3d2022绿色版/sample/3d2.tw3d2 \
        --out _test/out_3d2.tif [--commands 3,12,16]
"""
import argparse
import json
import os
import shutil
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win

CMD = {'open': 3, 'import': 7, 'preview': 12, 'stop': 13, 'tiff': 16, 'psd': 17, 'gif': 18}


def tiff_info(path):
    data = open(path, 'rb').read()
    if len(data) < 8:
        return {'error': 'too small', 'bytes': len(data)}
    if data[:2] == b'II':
        fmt, off = '<', struct.unpack('<I', data[4:8])[0]
    elif data[:2] == b'MM':
        fmt, off = '>', struct.unpack('>I', data[4:8])[0]
    else:
        return {'error': 'not TIFF (magic %r)' % data[:2], 'bytes': len(data)}
    tags, p = {}, off + 2
    if p + 2 > len(data):
        return {'error': 'bad IFD', 'bytes': len(data)}
    count = struct.unpack(fmt + 'H', data[off:off + 2])[0]
    for _ in range(count):
        if p + 12 > len(data):
            break
        tag, typ, n = struct.unpack(fmt + 'HHI', data[p:p + 8])
        sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8}
        size = sizes.get(typ, 1) * n
        raw = data[p + 8:p + 12]
        if size <= 4:
            if typ == 3:
                v = struct.unpack(fmt + 'H', raw[:2])[0]
            elif typ == 4:
                v = struct.unpack(fmt + 'I', raw)[0]
            else:
                v = raw[0]
        else:
            v = '<data>'
        tags[tag] = v
        p += 12
    names = {256: 'width', 257: 'height', 258: 'bits', 259: 'compression', 262: 'photometric',
             273: 'strip_offsets', 277: 'samples_per_pixel', 278: 'rows_per_strip',
             284: 'planar_config', 339: 'sample_format'}
    out = {'bytes': len(data), 'endian': 'II' if fmt == '<' else 'MM', 'ifd_tags': count}
    for t, name in names.items():
        if t in tags:
            out[name] = tags[t]
    if 'strip_offsets' in out:
        out.pop('strip_offsets')
        out['strips_present'] = True
    return out


def dismiss(pid, tag, shots):
    seen = []
    for h, cls, title, vis in win.windows(pid):
        if cls != 'TMessageForm' or not vis:
            continue
        png = os.path.join(shots, '%s_%d.png' % (tag, h))
        try:
            win.capture(h, png)
            seen.append(os.path.basename(png))
        except Exception:  # noqa: BLE001
            seen.append(None)
        kids = win.children(h, maxdepth=2)
        clicked = False
        for kh, kcls, ktxt in kids:
            if kcls == 'TButton':
                win.click(kh)
                clicked = True
                break
        if not clicked and kids:
            win.click(kids[0][0])
        time.sleep(0.7)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--project', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--work', default=None)
    ap.add_argument('--commands', default='open,preview,tiff')
    ap.add_argument('--settle', type=float, default=10.0)
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--exe', default='psdto3d101.exe')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    work = os.path.abspath(a.work or os.path.join(os.path.dirname(pkg), '_test'))
    shots = os.path.join(work, 'shots')
    if os.path.isdir(work):
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(shots, exist_ok=True)
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        os.remove(out)

    report, _ = dialogless_launch.launch(
        os.path.join(pkg, a.exe), pkg, os.path.abspath(a.project), out,
        os.path.join(work, 'launch.json'))
    pid = report['pid']
    result = {'launch': report, 'steps': []}
    time.sleep(5)
    mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
    if not mw:
        result['error'] = 'no main window'
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    hwnd = mw[0][0]
    result['main_hwnd'] = hwnd

    for spec in [c.strip() for c in a.commands.split(',') if c.strip()]:
        if '=' in spec:
            name, ids = spec.split('=', 1)
            cmd = int(ids)
        else:
            name, cmd = spec, CMD[spec]
        win.command(hwnd, cmd)
        time.sleep(a.settle)
        msgs = dismiss(pid, name, shots)
        alive = win.windows(pid) and any(w[0] == hwnd for w in win.windows(pid))
        result['steps'].append({'step': name, 'command': cmd, 'message_boxes': msgs,
                                'main_alive': bool(alive)})
        if not alive:
            result['steps'][-1]['app_exited'] = True
            break

    try:
        win.capture(hwnd, os.path.join(shots, 'final_main.png'))
    except Exception as exc:  # noqa: BLE001
        result['capture_error'] = str(exc)

    result['output'] = tiff_info(out) if os.path.exists(out) else None
    recent = []
    for root in (pkg, r'C:\ok3dtemp'):
        if os.path.isdir(root):
            for dirpath, _dirs, files in os.walk(root):
                for n in files:
                    p = os.path.join(dirpath, n)
                    try:
                        if os.path.getmtime(p) > time.time() - 600:
                            recent.append((p, os.path.getsize(p)))
                    except OSError:
                        pass
    result['recent_files'] = recent
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    if not a.keep:
        win.kill(pid) if hasattr(win, 'kill') else None
        os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0 if result.get('output') and 'error' not in result['output'] else 2


if __name__ == '__main__':
    sys.exit(main())
