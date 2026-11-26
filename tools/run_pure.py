"""不用任何外来 DLL 驱动 psdto3d：只改 comdlg32 的 IAT 槽，按需换路径。

为什么需要它：往进程里塞自己的 DLL 会改变堆布局，实测会让 Delph 程序在渲染时
踩空指针（vendor DLL + Python 桩时不会崩，换成我的 DLL 就崩）。
所以"绿色版 exe 到底能不能免狗出正确的图"必须在不加载任何外来 DLL 的前提下测。

原理：CreateProcess 后在目标进程里放一个 0x1000 的 RWX 区，里面：
    +0x000  open 桩（返回路径 1）
    +0x200  save 桩（返回路径 2）
    +0x400  路径 A（GBK）
    +0x600  路径 B
每次要换文件时，改写 +0x400 的字符串（或换 IAT 槽指向另一个桩）即可。

    python tools/run_pure.py --pkg DIR --steps "7@12:psd,10@44:proj,12@74,13@194,16@209:tif,17@239:psd"
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['NODLGPATCH'] = '1'          # 不要 dialogless_launch 去装它自己的桩

import dialogless_launch as dl
import win

k32 = ctypes.windll.kernel32
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                               wintypes.DWORD, wintypes.DWORD]
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                 wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
k32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                               ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.LPCWSTR,
                               ctypes.POINTER(dl.STARTUPINFO),
                               ctypes.POINTER(dl.PROCESS_INFORMATION)]
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

OPEN_SLOT = 0x000
SAVE_SLOT = 0x100
PATH_OPEN = 0x400
PATH_SAVE = 0x600
REGION = 0x1000


def wpm(h, addr, data):
    n = ctypes.c_size_t()
    buf = ctypes.create_string_buffer(data, len(data))
    if not k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(n)):
        raise SystemExit('WriteProcessMemory failed: %s' % ctypes.WinError())


def set_path(h, slot_base, path):
    p = path.encode('gbk') + b'\x00'
    if len(p) > 0x1FE:
        raise SystemExit('路径太长: %s' % path)
    wpm(h, slot_base, p)


def build_exe_stub(h, stub_va, path_va):
    """open/save 共用的桩：把 path_va 的字符串拷进 OPENFILENAME.lpstrFile。"""
    code = bytearray(dl.STUB)
    # dl.STUB 里长度/指针槽位：mov ecx,<len+1> @9 / mov esi,<path> @14
    return code


def patch_stub_path(h, stub_va, code_template, path_va, path):
    p = path.encode('gbk')
    import struct
    code = bytearray(code_template)
    struct.pack_into('<I', code, 9, len(p) + 1)
    struct.pack_into('<I', code, 14, path_va)
    struct.pack_into('<H', code, 25, 0)
    struct.pack_into('<H', code, 31, 0)
    struct.pack_into('<I', code, 41, 0)
    struct.pack_into('<I', code, 46, 0)
    wpm(h, stub_va, bytes(code))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--exe', default='psdto3d101.exe')
    ap.add_argument('--steps', required=True,
                    help='如 "7@12:psd,10@44:proj,12@74,13@194,16@209:tif,17@239:psd"')
    ap.add_argument('--psd', required=True)
    ap.add_argument('--proj', required=True)
    ap.add_argument('--tif', required=True)
    ap.add_argument('--outpsd', required=True)
    ap.add_argument('--duration', type=float, default=330)
    ap.add_argument('--out', required=True)
    ap.add_argument('--shots', action='store_true')
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    outd = os.path.abspath(a.out)
    os.makedirs(outd, exist_ok=True)
    # 对话框返回给程序的是"用户选的路径"，程序按自己的 CWD 解析——必须给绝对路径
    a.psd = os.path.abspath(a.psd)
    a.proj = os.path.abspath(a.proj)
    a.tif = os.path.abspath(a.tif)
    a.outpsd = os.path.abspath(a.outpsd)
    for p in (a.tif, a.outpsd):
        if os.path.exists(p):
            os.remove(p)
    os.makedirs(os.path.dirname(a.tif), exist_ok=True)
    k32.SetEnvironmentVariableW('NODLGPATCH', None)

    exe = os.path.join(pkg, a.exe)
    iat = dl.find_iat(exe)
    si = dl.STARTUPINFO(); si.cb = ctypes.sizeof(si)
    pi = dl.PROCESS_INFORMATION()
    if not k32.CreateProcessW(exe, None, None, None, False, 0, None, pkg,
                              ctypes.byref(si), ctypes.byref(pi)):
        raise SystemExit('CreateProcess: %s' % ctypes.WinError())
    hproc, pid = pi.hProcess, pi.dwProcessId
    hwnd = None
    for _ in range(60):
        mw = [w for w in win.windows(pid) if w[1] == 'TForm1' and w[3]]
        if mw:
            hwnd = mw[0][0]
            break
        time.sleep(0.5)
    if not hwnd:
        print(json.dumps({'error': 'no main window', 'pid': pid}, ensure_ascii=False))
        return 1

    mem = k32.VirtualAllocEx(hproc, None, REGION, 0x3000, 0x40)
    if not mem:
        raise SystemExit('VirtualAllocEx: %s' % ctypes.WinError())
    open_stub = mem + OPEN_SLOT
    save_stub = mem + SAVE_SLOT
    p_open = mem + PATH_OPEN
    p_save = mem + PATH_SAVE
    patch_stub_path(hproc, open_stub, dl.STUB, p_open, a.psd)
    patch_stub_path(hproc, save_stub, dl.STUB, p_save, a.tif)
    set_path(hproc, p_open, a.psd)
    set_path(hproc, p_save, a.tif)

    lo = min(iat.values()); span = max(iat.values()) - lo + 4
    old = wintypes.DWORD()
    k32.VirtualProtectEx(hproc, ctypes.c_void_p(lo), span, 0x04, ctypes.byref(old))
    import struct
    wpm(hproc, iat['GetOpenFileNameA'], struct.pack('<I', open_stub))
    wpm(hproc, iat['GetSaveFileNameA'], struct.pack('<I', save_stub))

    steps = []
    for s in a.steps.split(','):
        t_part, _, kind = s.partition(':')
        cmd_s, tt_s = t_part.split('@')       # 格式是 命令@时刻
        steps.append((float(tt_s), int(cmd_s), kind))
    steps.sort()

    log = {'pid': pid, 'hwnd': hwnd, 'steps': [], 'dialogs': []}
    t0 = time.time()
    i = 0
    seen = set()
    while time.time() - t0 < a.duration:
        el = time.time() - t0
        if i < len(steps) and el >= steps[i][0]:
            tt, cmd, kind = steps[i]
            if kind == 'psd':
                set_path(hproc, p_open, a.psd)
            elif kind == 'proj':
                set_path(hproc, p_open, a.proj)
            elif kind == 'tif':
                set_path(hproc, p_save, a.tif)
            elif kind == 'outpsd':
                set_path(hproc, p_save, a.outpsd)
            win.command(hwnd, cmd)
            log['steps'].append({'t': round(el, 1), 'cmd': cmd, 'file': kind})
            i += 1
        for h, cls, title, vis in win.windows(pid):
            if vis and cls in ('#32770', 'TMessageForm') and h not in seen:
                seen.add(h)
                txt = [ktxt for kh, kcls, ktxt in win.children(h, 6) if ktxt]
                log['dialogs'].append({'t': round(el, 1), 'cls': cls, 'text': txt[:2]})
                if a.shots:
                    try:
                        win.capture(h, os.path.join(outd, 'dlg_t%03d.png' % int(el)))
                    except Exception:
                        pass
                for kh, kcls, ktxt in win.children(h, 3):
                    if kcls == 'TButton':
                        win.click(kh)
        if a.shots and int(el) % 20 < 1:
            try:
                win.capture(hwnd, os.path.join(outd, 'shot_t%03d.png' % int(el)))
            except Exception:
                pass
        time.sleep(0.15)

    kde = r'C:\ok3dtemp'
    log['kde'] = {'ly': len([f for f in os.listdir(kde) if f.lower().startswith('ly') and f.lower().endswith('.gjs')]),
                  'vwd': len([f for f in os.listdir(kde) if f.lower().startswith('vwd')])} if os.path.isdir(kde) else {}
    for tag, p in (('tif', a.tif), ('psd', a.outpsd)):
        if os.path.exists(p):
            log[tag] = {'size': os.path.getsize(p)}
    os.system('taskkill /PID %d /F >nul 2>&1' % pid)
    with open(os.path.join(outd, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(json.dumps(log, ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
