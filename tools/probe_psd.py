"""Try importing every sample PSD through the app and report which ones pass its
layer validation (no message box) — used to pick a PSD for the end-to-end test."""
import glob
import json
import os
import subprocess as sp
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win

CMD_IMPORT = 7


def main():
    pkg = os.path.abspath(sys.argv[1])
    shots = os.path.join(os.path.dirname(pkg), '_test', 'psd_probe')
    os.makedirs(shots, exist_ok=True)
    psds = sorted(glob.glob(os.path.join(pkg, 'sample', '*.psd')))
    results = []
    for psd in psds:
        name = os.path.basename(psd)
        dummy = os.path.join(shots, '_unused.tif')
        try:
            rep, hproc = dialogless_launch.launch(
                os.path.join(pkg, 'psdto3d101.exe'), pkg, psd, dummy)
        except SystemExit as exc:
            results.append({'psd': name, 'launch_failed': str(exc)})
            continue
        pid = rep['pid']
        time.sleep(4)
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if not mw:
            results.append({'psd': name, 'error': 'no main window'})
            sp.call(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            continue
        hwnd = mw[0][0]
        win.command(hwnd, CMD_IMPORT)
        time.sleep(9)
        boxes = [w for w in win.windows(pid) if w[1] == 'TMessageForm' and w[3]]
        pngs = []
        for i, (h, cls, title, vis) in enumerate(boxes):
            p = os.path.join(shots, '%s_%d.png' % (os.path.splitext(name)[0], i))
            try:
                win.capture(h, p)
                pngs.append(os.path.basename(p))
            except Exception:  # noqa: BLE001
                pass
            for kh, kcls, ktxt in win.children(h, maxdepth=2):
                if kcls == 'TButton':
                    win.click(kh)
                    break
            time.sleep(0.6)
        time.sleep(1)
        try:
            win.capture(hwnd, os.path.join(shots, '%s_main.png' % os.path.splitext(name)[0]))
        except Exception:  # noqa: BLE001
            pass
        alive = win.windows(pid) and any(w[0] == hwnd for w in win.windows(pid))
        results.append({'psd': name, 'message_boxes': pngs, 'alive': bool(alive)})
        sp.call(['taskkill', '/PID', str(pid), '/F'], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        time.sleep(1)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
