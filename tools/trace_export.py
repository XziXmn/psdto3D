"""带调试器跑一次导出：按时刻发表单命令，定时截屏，弹框自动点掉，
并在 Delphi 异常（0xEEDFADE）时走 EBP 链把真实抛点打出来。

    python tools/trace_export.py --pkg psdto3d2022绿色版 \
        --project "1114/1114/1114-1_10.1_2022.tw3d2" --out 归档/实验/_export_test/t.tif \
        --cmds "3@1,12@20,13@100,16@105" --duration 260 --shot-every 15

截图落在 <out 目录>/shots/ 下，文件名带秒数。
"""
import argparse
import ctypes
import os
import struct
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dialogless_launch
import win
from trace_exception import (DEBUG_EVENT, EXCEPTION_DEBUG_EVENT,
                            EXIT_PROCESS_DEBUG_EVENT, modules, owning)
from trace_stack_at_raise import CONTEXT, CONTEXT_FULL, CONTEXT_SIZE, get_context, rpm

k32 = ctypes.windll.kernel32
u32 = ctypes.windll.user32
DBG_CONTINUE = 0x00010002
BUTTON_HINTS = ('ok', '确定', '是', 'yes', 'close', '关闭')


def snapshot(pid, label, shots):
    """截主窗 + 枚举所有可见顶窗，返回需要点掉的对话框。"""
    dialogs = []
    for h, cls, title, vis in win.windows(pid):
        if not vis:
            continue
        if cls in ('TForm1', 'TApplication'):
            p = os.path.join(shots, '%s_%s.png' % (label, cls))
            try:
                win.capture(h, p)
            except Exception:  # noqa: BLE001
                pass
            continue
        kids = win.children(h, 4)
        p = os.path.join(shots, '%s_dlg_%d.png' % (label, h))
        try:
            win.capture(h, p)
        except Exception:  # noqa: BLE001
            pass
        if cls in ('TMessageForm', '#32770', 'TProgressForm') or 'Message' in cls:
            dialogs.append((h, cls, title, kids))
    return dialogs


def click_ok(dialogs, seen):
    for h, cls, title, kids in dialogs:
        if h in seen:
            continue
        seen.add(h)
        print('  > 对话框 %s %r' % (cls, title), flush=True)
        target = None
        for kh, kcls, ktxt in kids:
            if kcls in ('TButton', 'Button') and (ktxt or '').strip().lower() in BUTTON_HINTS:
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
            u32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE 兜底


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default='psdto3d2022绿色版')
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--project', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cmds', default='3@1,12@20,13@100,16@105')
    ap.add_argument('--duration', type=float, default=260)
    ap.add_argument('--shot-every', type=float, default=15)
    ap.add_argument('--debug', action='store_true', help='附加调试器抓 Delphi 异常栈')
    ap.add_argument('--no-break', action='store_true',
                    help='输出文件出现后不退出，继续按时刻表发命令')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        os.remove(out)
    shots = os.path.join(os.path.dirname(out), 'shots')
    os.makedirs(shots, exist_ok=True)
    sched = sorted((float(t), int(c)) for c, t in
                   (x.split('@') for x in a.cmds.split(',')))

    rep, _ = dialogless_launch.launch(os.path.join(pkg, a.exe), pkg,
                                      os.path.abspath(a.project), out)
    pid = rep['pid']
    print('pid=%d' % pid, flush=True)
    time.sleep(1.0)
    # 先拿窗口句柄，再附加调试器 —— 顺序反了会在附加后卡在窗口枚举上
    hwnd = None
    for _ in range(40):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)
    if not hwnd:
        raise SystemExit('没有找到主窗口')
    if a.debug and not k32.DebugActiveProcess(pid):
        print('DebugActiveProcess 失败，继续无调试运行', flush=True)
        a.debug = False

    t0 = time.time()
    seen = set()
    next_cmd = 0
    next_shot = 0.0
    reported = 0
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if a.debug:
            ev = DEBUG_EVENT()
            if k32.WaitForDebugEvent(ctypes.byref(ev), 100):
                if ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
                    rec = ev.u.Exception.ExceptionRecord
                    if rec.ExceptionCode in (0xEEDFADE, 0xC0000005) and reported < 6:
                        params = [int(rec.ExceptionInformation[i] or 0)
                                  for i in range(min(rec.NumberParameters, 7))]
                        ctx, err = get_context(pid, ev.dwThreadId)
                        print('=== 异常 0x%08X t=%.1fs  site=0x%08x obj=0x%08x ==='
                              % (rec.ExceptionCode, el,
                                 params[0] if params else 0,
                                 params[1] if len(params) > 1 else 0), flush=True)
                        if ctx:
                            mods = modules(pid)
                            print('  eip=%08x eax=%08x ebx=%08x ecx=%08x edx=%08x esi=%08x edi=%08x'
                                  % (ctx.Eip, ctx.Eax, ctx.Ebx, ctx.Ecx, ctx.Edx,
                                     ctx.Esi, ctx.Edi), flush=True)
                            ebp = ctx.Ebp
                            for i in range(18):
                                fr = rpm(pid, ebp, 8)
                                if not fr or len(fr) < 8:
                                    break
                                nxt, ret = struct.unpack('<II', fr)
                                name, off = owning(ret, mods)
                                print('  frame %2d ebp=%08x ret=0x%08x  %s+0x%x'
                                      % (i, ebp, ret, name, off), flush=True)
                                if nxt <= ebp or nxt > 0x7FFF0000:
                                    break
                                ebp = nxt
                        else:
                            print('  上下文不可用: %s' % err, flush=True)
                        reported += 1
                elif ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                    print('进程退出 t=%.1fs' % el, flush=True)
                    k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
                    break
                k32.ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE)
        else:
            time.sleep(0.2)

        if next_cmd < len(sched) and el >= sched[next_cmd][0]:
            cmd = sched[next_cmd][1]
            next_cmd += 1
            win.command(hwnd, cmd)
            print('t=%.1fs 发命令 %d' % (el, cmd), flush=True)

        if el >= next_shot and not a.debug:
            next_shot = el + a.shot_every
            d = snapshot(pid, 't%03d' % el, shots)
            click_ok(d, seen)
            if os.path.exists(out):
                print('t=%.1fs 输出出现 %d 字节' % (el, os.path.getsize(out)), flush=True)
                if not a.no_break:
                    break

    if os.path.exists(out):
        print('输出: %s  %d 字节' % (out, os.path.getsize(out)))
        print('头 16 字节: %s' % open(out, 'rb').read(16).hex(' '))
    else:
        print('没有输出文件')
    if a.debug:
        try:
            k32.DebugActiveProcessStop(pid)
        except Exception:  # noqa: BLE001
            pass
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
