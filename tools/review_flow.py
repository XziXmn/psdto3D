"""复查用驱动：比 run_flow.py 多做三件事——检测进程存活、记录每次弹窗的标题与按钮、
按时序记录 ok3dtemp 变化。应用一退出就立刻结束，不空转。

    python tools/review_flow.py --pkg _review/pkgA --project X.tw3d2 --psd Y.psd \
        --cmds "3@3,7@10" --out _review/runs/a1 --duration 300 --label A

对话框顺序：工程 -> PSD -> (settings) -> PSD。与 run_flow 一致。
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['NODLGPATCH'] = '1'

import dialogless_launch
import win

KDE = r'C:\ok3dtemp'
BTN = ('ok', '确定', '是', 'yes', 'close', '关闭')
# 启动时会出现但不该被"点掉"的窗口：TAboutBox 会自己关，WM_CLOSE 它会把整个进程带走
IGNORE_CLS = {'TForm1', 'TApplication', 'TAboutBox', 'TPUtilWindow', 'ComboLBox',
              'IME', 'MSCTFIME UI'}


def md5_of(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def alive(pid):
    r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                       capture_output=True, text=True, errors='replace')
    return str(pid) in (r.stdout or '')


def kde_state():
    if not os.path.isdir(KDE):
        return {'files': 0}
    fs = [f for f in os.listdir(KDE) if f.lower().endswith('.gjs')]
    lys = [f for f in fs if re.match(r'ly\d+\.gjs$', f, re.I)]
    vwd = [f for f in fs if re.match(r'vwd\d+\.gjs$', f, re.I)]
    ly1 = os.path.join(KDE, 'ly1.gjs')
    return {
        'files': len(fs), 'ly': len(lys), 'vwd': len(vwd),
        'ly1_size': os.path.getsize(ly1) if os.path.exists(ly1) else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--psd', required=True)
    ap.add_argument('--project', default=None)
    ap.add_argument('--settings', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--cmds', default='3@3,7@10')
    ap.add_argument('--duration', type=float, default=300)
    ap.add_argument('--label', default='run')
    ap.add_argument('--shots', action='store_true', help='每 20 秒给主窗口截图')
    ap.add_argument('--set-edit', default=None,
                    help='形如 7:11 —— 把主窗口里文本为 7 的 TEdit 改成 11（视图数就是从这里读的）')
    ap.add_argument('--keep-kde', action='store_true')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    outd = os.path.abspath(a.out)
    os.makedirs(outd, exist_ok=True)
    out_tif = os.path.join(outd, 'out.tif')
    out_psd = os.path.join(outd, 'out.psd')
    for p in (out_tif, out_psd):
        if os.path.exists(p):
            os.remove(p)
    if not a.keep_kde and os.path.isdir(KDE):
        for f in os.listdir(KDE):
            try:
                os.remove(os.path.join(KDE, f))
            except OSError:
                pass

    psd = os.path.abspath(a.psd)
    proj = os.path.abspath(a.project) if a.project else None
    sett = os.path.abspath(a.settings) if a.settings else None
    open_list = []
    if proj:
        open_list.append(proj)
    open_list.append(psd)
    if sett:
        open_list.append(sett)
    open_list.append(psd)
    with open(os.path.join(pkg, '_dlgopen.txt'), 'wb') as f:
        for p in open_list:
            f.write((p + '\r\n').encode('gbk', 'ignore'))
    with open(os.path.join(pkg, '_dlgsave.txt'), 'wb') as f:
        f.write((out_tif + '\r\n').encode('gbk', 'ignore'))
        f.write((out_psd + '\r\n').encode('gbk', 'ignore'))
    for name in ('_dongle.log', '_dlgonly.txt'):
        p = os.path.join(pkg, name)
        if os.path.exists(p):
            os.remove(p)

    sched = sorted((float(t), int(c)) for c, t in (x.split('@') for x in a.cmds.split(',')))
    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg, proj or psd, out_tif)
    pid = rep['pid']
    hwnd = None
    for _ in range(60):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1' and w[3]]
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)

    log = {'label': a.label, 'pid': pid, 'hwnd': hwnd, 'main_window': bool(hwnd),
           'dialogs': [], 'cmds_sent': [], 'kde_timeline': [], 'exited_at': None,
           'exit_stage': None}
    if not hwnd:
        log['fatal'] = 'no main window'
        print(json.dumps(log, ensure_ascii=False, indent=1))
        return 1

    seen = set()
    t0 = time.time()
    nxt = 0
    next_poll = 0.0
    exit_stage = None
    edited = False
    next_edit = 0.0
    edit_hits = 0

    def apply_set_edit():
        """把 7 改成 11：视图数是程序从这个 Edit 里现读的（会被初始化覆盖，所以要反复设）。"""
        if not a.set_edit:
            return 0
        try:
            old, new = a.set_edit.split(':')
        except ValueError:
            return 0
        hit = 0
        for kh, kcls, ktxt in win.children(hwnd, 6):
            if kcls in ('TEdit', 'Edit') and (ktxt or '').strip() == old.strip():
                win.set_text(kh, new.strip())
                hit += 1
        return hit

    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if a.set_edit and el >= next_edit:
            next_edit = el + 2.0
            n = apply_set_edit()
            if n:
                edit_hits += 1
                log['set_edit'] = {'old': a.set_edit, 'hits': edit_hits, 't': round(el, 1)}
        if not alive(pid):
            log['exited_at'] = round(el, 1)
            log['exit_stage'] = exit_stage
            break
        if nxt < len(sched) and el >= sched[nxt][0]:
            win.command(hwnd, sched[nxt][1])
            log['cmds_sent'].append({'t': round(el, 1), 'cmd': sched[nxt][1]})
            exit_stage = 'after cmd %d' % sched[nxt][1]
            nxt += 1
        if el >= next_poll:
            next_poll = el + 1.0
            if a.shots and int(el) % 20 < 1:
                try:
                    win.capture(hwnd, os.path.join(outd, 'preview_t%03d.png' % int(el)))
                except Exception:
                    pass
            st = kde_state()
            st['t'] = round(el, 1)
            if not log['kde_timeline'] or {k: v for k, v in log['kde_timeline'][-1].items() if k != 't'} != \
                    {k: v for k, v in st.items() if k != 't'}:
                log['kde_timeline'].append(st)
            for h, cls, title, vis in win.windows(pid):
                if not vis or cls in IGNORE_CLS or h in seen:
                    continue
                try:
                    kids = win.children(h, 3)
                except Exception:
                    kids = []
                btns = [(kh, kcls, ktxt) for kh, kcls, ktxt in kids
                        if kcls in ('TButton', 'Button')]
                texts = [ktxt for kh, kcls, ktxt in kids if kcls in ('TStaticText', 'Static', 'TLabel')]
                log['dialogs'].append({'t': round(el, 1), 'cls': cls, 'title': title,
                                       'buttons': [b[2] for b in btns], 'texts': texts[:4]})
                seen.add(h)
                target = None
                for kh, kcls, ktxt in btns:
                    if (ktxt or '').strip().lower() in BTN:
                        target = kh
                        break
                if target is None and btns:
                    target = btns[0][0]
                if target:
                    win.click(target)
                # 没有按钮的窗口一律不碰：WM_CLOSE 会连主进程一起干掉
        time.sleep(0.15)

    res = dict(log)
    res['kde_final'] = kde_state()
    if os.path.exists(out_tif):
        res['tif'] = {'size': os.path.getsize(out_tif), 'md5': md5_of(out_tif)}
    if os.path.exists(out_psd):
        res['psd'] = {'size': os.path.getsize(out_psd), 'md5': md5_of(out_psd)}
    dlgonly = os.path.join(pkg, '_dlgonly.txt')
    dongle = os.path.join(pkg, '_dongle.log')
    for tag, p in (('dlgonly_log', dlgonly), ('dongle_log', dongle)):
        if os.path.exists(p):
            with open(p, encoding='utf-8', errors='replace') as f:
                res[tag] = f.read().splitlines()[:60]
    if alive(pid):
        os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    with open(os.path.join(outd, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
