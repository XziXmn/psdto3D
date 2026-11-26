"""一次跑完整流程并给出固定格式的结论。调用方给全命令时刻表，脚本不猜。

    python tools/run_flow.py --psd A.psd --project B.tw3d2 --settings C.gxwj \
        --cmds "3@3,7@12,10@24,12@45,13@130,16@145,17@175" --out 归档/实验/_export_test/run

对话框按命令顺序配：3->project, 7->psd, 10->settings，之后继续用 psd。
判据：导入层数、TIFF 尺寸/大小/md5、PSD 大小/md5、以及实际弹出的对话框序列。
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['NODLGPATCH'] = '1'

import dialogless_launch
import win

KDE = r'C:\ok3dtemp'


def md5_of(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()[:12]


def tif_dims(p):
    with open(p, 'rb') as f:
        d = f.read(2048)
    if d[:2] not in (b'II', b'MM'):
        return None
    le = d[:2] == b'II'
    fmt = '<' if le else '>'
    off = struct.unpack_from(fmt + 'I', d, 4)[0]
    try:
        n = struct.unpack_from(fmt + 'H', d, off)[0]
        w = h = None
        for i in range(n):
            b = off + 2 + 12 * i
            tag, typ, cnt, val = struct.unpack_from(fmt + 'HHII', d, b)
            if tag == 0x100:
                w = val
            elif tag in (0x101, 0x116):
                h = val
        return [w, h]
    except Exception:
        return None


def clean_kde():
    if not os.path.isdir(KDE):
        return
    for f in os.listdir(KDE):
        try:
            os.remove(os.path.join(KDE, f))
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default='归档/实验/_export_test/m32')
    ap.add_argument('--psd', required=True)
    ap.add_argument('--project', default=None)
    ap.add_argument('--settings', default=None)
    ap.add_argument('--out', default='归档/实验/_export_test/run')
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--cmds', default='7@3,12@30,13@105,16@120,17@150')
    ap.add_argument('--duration', type=float, default=185)
    ap.add_argument('--dog', action='store_true')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    outd = os.path.abspath(a.out)
    os.makedirs(outd, exist_ok=True)
    out_tif = os.path.join(outd, 'out.tif')
    out_psd = os.path.join(outd, 'out.psd')
    for p in (out_tif, out_psd):
        if os.path.exists(p):
            os.remove(p)
    clean_kde()

    psd = os.path.abspath(a.psd)
    proj = os.path.abspath(a.project) if a.project else None
    sett = os.path.abspath(a.settings) if a.settings else None

    open_list = []
    if proj:
        open_list.append(proj)
    open_list.append(psd)
    if sett:
        open_list.append(sett)
    open_list.append(psd)          # 之后的对话框都用 PSD 顶着
    with open(os.path.join(pkg, '_dlgopen.txt'), 'wb') as f:
        for p in open_list:
            f.write((p + '\r\n').encode('gbk', 'ignore'))
    with open(os.path.join(pkg, '_dlgsave.txt'), 'wb') as f:
        f.write((out_tif + '\r\n').encode('gbk', 'ignore'))
        f.write((out_psd + '\r\n').encode('gbk', 'ignore'))

    logp = os.path.join(pkg, '_dongle.log')
    if os.path.exists(logp):
        os.remove(logp)

    sched = sorted((float(t), int(c)) for c, t in (x.split('@') for x in a.cmds.split(',')))
    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg, proj or psd, out_tif)
    pid = rep['pid']
    hwnd = None
    for _ in range(60):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)
    if not hwnd:
        print(json.dumps({'error': 'no main window'}, ensure_ascii=False))
        return 1

    BTN = ('ok', '确定', '是', 'yes', 'close', '关闭')
    seen = set()

    def dismiss():
        for h, cls, title, vis in win.windows(pid):
            if not vis or cls == 'TForm1':
                continue
            try:
                kids = win.children(h, 3)
            except Exception:
                kids = []
            target = None
            for kh, kcls, ktxt in kids:
                if kcls in ('TButton', 'Button') and (ktxt or '').strip().lower() in BTN:
                    target = kh
                    break
            if target is None:
                for kh, kcls, ktxt in kids:
                    if kcls in ('TButton', 'Button'):
                        target = kh
                        break
            if target:
                win.click(target)
            else:
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)

    t0 = time.time()
    nxt = 0
    sent = []
    next_dismiss = 0.0
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if nxt < len(sched) and el >= sched[nxt][0]:
            win.command(hwnd, sched[nxt][1])
            sent.append(sched[nxt][1])
            nxt += 1
        if el >= next_dismiss:
            next_dismiss = el + 1.5
            dismiss()
        time.sleep(0.2)

    res = {
        'psd_in': os.path.basename(psd),
        'project': os.path.basename(proj) if proj else None,
        'settings': os.path.basename(sett) if sett else None,
        'dog': bool(a.dog),
        'cmds_sent': sent,
        'dialogs': [],
        'layers': 0,
        'tif': None,
        'psd': None,
        'av': 0,
    }
    if os.path.exists(out_tif):
        res['tif'] = {'size': os.path.getsize(out_tif), 'md5': md5_of(out_tif),
                      'dims': tif_dims(out_tif)}
    if os.path.exists(out_psd):
        res['psd'] = {'size': os.path.getsize(out_psd), 'md5': md5_of(out_psd)}
    if os.path.isdir(KDE):
        res['layers'] = len([f for f in os.listdir(KDE) if re.match(r'ly\d+\.gjs$', f)])
    if os.path.exists(logp):
        with open(logp, encoding='utf-8', errors='replace') as f:
            for line in f:
                if 'OPEN ' in line or 'SAVE ' in line:
                    res['dialogs'].append(line.strip()[:110])
                elif 'AV@' in line:
                    res['av'] += 1
    res['dialogs'] = res['dialogs'][:8]

    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
