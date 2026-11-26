"""Start psdto3d with its file dialogs answered automatically (memory-only patch).

Why not patch the file: this image has ``OriginalFirstThunk = 0``, so its IAT doubles
as the import lookup table and the loader rewrites those slots on every start.  The
redirection therefore happens after the loader ran:

    CreateProcess(SUSPENDED) -> VirtualAllocEx(RWX) -> write stubs + paths ->
    overwrite the two comdlg32 IAT slots -> ResumeThread

Each stub fills ``OPENFILENAME.lpstrFile`` with a fixed path and returns TRUE, so the
application behaves as if the user had picked that file.

    python dialogless_launch.py --exe <exe> --open <project.tw3d2> --save <out.tif>
"""
import argparse
import ctypes
import json
import os
import struct
import sys
import time
from ctypes import wintypes

import pefile

CREATE_SUSPENDED = 0x00000004
MEM_COMMIT_RESERVE = 0x3000
PAGE_EXECUTE_READWRITE = 0x40
PAGE_READWRITE = 0x04


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR), ('lpDesktop', wintypes.LPWSTR),
        ('lpTitle', wintypes.LPWSTR), ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
        ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD),
        ('dwXCountChars', wintypes.DWORD), ('dwYCountChars', wintypes.DWORD),
        ('dwFillAttribute', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
        ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
        ('lpReserved2', ctypes.c_void_p), ('hStdInput', wintypes.HANDLE),
        ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD)]


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
                               ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)]

STUB = (
    b'\x8b\x74\x24\x04'            # 0  mov esi,[esp+4]        ; OPENFILENAME*
    b'\x56'                        # 4  push esi
    b'\x8b\x7e\x1c'                # 5  mov edi,[esi+0x1C]    ; lpstrFile
    b'\xb9\x00\x00\x00\x00'        # 8  mov ecx,<pathlen+1>
    b'\xbe\x00\x00\x00\x00'        # 13 mov esi,<path>
    b'\xf3\xa4'                    # 18 rep movsb
    b'\x5e'                        # 20 pop esi
    b'\x66\xc7\x46\x38\x00\x00'    # 21 mov word [esi+0x38],<fileoff>  ; nFileOffset
    b'\x66\xc7\x46\x3a\x00\x00'    # 27 mov word [esi+0x3A],<extoff>   ; nFileExtension
    b'\x8b\x7e\x24'                # 33 mov edi,[esi+0x24]    ; lpstrFileTitle
    b'\x85\xff'                    # 36 test edi,edi
    b'\x74\x0c'                    # 38 jz +12 -> 52
    b'\xb9\x00\x00\x00\x00'        # 40 mov ecx,<titlelen+1>
    b'\xbe\x00\x00\x00\x00'        # 45 mov esi,<title>
    b'\xf3\xa4'                    # 50 rep movsb
    b'\xb8\x01\x00\x00\x00'        # 52 mov eax,1
    b'\xc2\x04\x00'                # 57 ret 4
)


def make_stub(path, path_va, title_va=0, fill=False):
    """Build the OPENFILENAME-filling stub for one path (GBK encoded)."""
    p = path.encode('gbk')
    name = os.path.basename(path)
    t = name.encode('gbk')
    fileoff = path.rfind('\\') + 1
    extoff = path.rfind('.') + 1 if '.' in name else 0
    code = bytearray(STUB)
    struct.pack_into('<I', code, 9, len(p) + 1)      # path length
    struct.pack_into('<I', code, 14, path_va)        # path pointer
    struct.pack_into('<H', code, 25, fileoff if fill else 0)     # nFileOffset
    struct.pack_into('<H', code, 31, extoff if fill else 0)      # nFileExtension
    struct.pack_into('<I', code, 41, len(t) + 1)                 # title length
    struct.pack_into('<I', code, 46, title_va if fill else 0)    # title pointer
    return bytes(code)


def find_iat(exe):
    pe = pefile.PE(exe, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    slots = {}
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        if entry.dll.decode().lower() != 'comdlg32.dll':
            continue
        for imp in entry.imports:
            name = imp.name.decode() if imp.name else None
            if name in ('GetOpenFileNameA', 'GetSaveFileNameA'):
                slots[name] = imp.address          # absolute VA of the IAT slot
    if len(slots) != 2:
        raise SystemExit('comdlg32 imports not found: %s' % slots)
    return slots


def launch(exe, cwd, open_path, save_path, report_path=None, wait_window=25.0):
    """Start the exe, wait until its main window exists, then redirect the import slots.

    The patch must happen *after* the loader resolved the imports: this image has
    OriginalFirstThunk = 0, so the IAT doubles as the lookup table and any value
    written before LdrInitializeThunk makes the loader fail with
    STATUS_ENTRYPOINT_NOT_FOUND (0xC0000139).
    """
    exe = os.path.abspath(exe)
    cwd = os.path.abspath(cwd or os.path.dirname(exe))
    iat = find_iat(exe)

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()
    if not k32.CreateProcessW(exe, None, None, None, False, 0, None, cwd,
                              ctypes.byref(si), ctypes.byref(pi)):
        raise SystemExit('CreateProcess failed: %s' % ctypes.WinError())

    hproc, pid = pi.hProcess, pi.dwProcessId

    import win as _win
    deadline = time.time() + wait_window
    main = None
    while time.time() < deadline:
        cands = [w for w in _win.windows(pid) if w[1] == 'TForm1']
        if cands:
            main = cands[0][0]
            break
        time.sleep(0.5)
    if main is None:
        raise SystemExit('main window did not appear (pid=%d)' % pid)

    if os.environ.get('NODLGPATCH') == '1':
        # 对话框交给进程内的 cmyktiff2.dll 处理（它按 _dlgopen.txt / _dlgsave.txt 顺序返回）
        return {'pid': pid, 'exe': exe, 'iat': {}, 'stubs': {}, 'alloc': 'none',
                'paths': {'open': open_path, 'save': save_path}}, hproc

    mem = k32.VirtualAllocEx(hproc, None, 0x1000, MEM_COMMIT_RESERVE, PAGE_EXECUTE_READWRITE)
    if not mem:
        raise SystemExit('VirtualAllocEx failed: %s' % ctypes.WinError())
    base = mem
    stub_open, stub_save = base, base + 0x80
    path_open, path_save = base + 0x200, base + 0x400
    title_open, title_save = base + 0x300, base + 0x500
    p1, p2 = open_path.encode('gbk'), save_path.encode('gbk')
    t1, t2 = os.path.basename(open_path).encode('gbk'), os.path.basename(save_path).encode('gbk')

    blob = bytearray(0x800)
    s1 = make_stub(open_path, path_open, title_open)
    s2 = make_stub(save_path, path_save, title_save)
    blob[0:len(s1)] = s1
    blob[0x80:0x80 + len(s2)] = s2
    blob[0x200:0x200 + len(p1) + 1] = p1 + b'\x00'
    blob[0x300:0x300 + len(t1) + 1] = t1 + b'\x00'
    blob[0x400:0x400 + len(p2) + 1] = p2 + b'\x00'
    blob[0x500:0x500 + len(t2) + 1] = t2 + b'\x00'

    written = ctypes.c_size_t()
    if not k32.WriteProcessMemory(hproc, ctypes.c_void_p(base), bytes(blob), len(blob),
                                  ctypes.byref(written)):
        raise SystemExit('WriteProcessMemory(stub) failed: %s' % ctypes.WinError())

    lo = min(iat.values())
    span = max(iat.values()) - lo + 4
    old = wintypes.DWORD()
    k32.VirtualProtectEx(hproc, ctypes.c_void_p(lo), span, PAGE_READWRITE, ctypes.byref(old))
    for name, target in (('GetOpenFileNameA', stub_open), ('GetSaveFileNameA', stub_save)):
        buf = struct.pack('<I', target)
        if not k32.WriteProcessMemory(hproc, ctypes.c_void_p(iat[name]), buf, 4,
                                      ctypes.byref(written)):
            raise SystemExit('WriteProcessMemory(IAT %s) failed: %s' % (name, ctypes.WinError()))
    k32.VirtualProtectEx(hproc, ctypes.c_void_p(lo), span, PAGE_READWRITE, ctypes.byref(old))

    report = {
        'pid': pid,
        'exe': exe,
        'iat': {k: hex(v) for k, v in iat.items()},
        'stubs': {'GetOpenFileNameA': hex(stub_open), 'GetSaveFileNameA': hex(stub_save)},
        'paths': {'open': open_path, 'save': save_path},
        'alloc': hex(base),
    }
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return report, hproc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--open', required=True)
    ap.add_argument('--save', required=True)
    ap.add_argument('--cwd', default=None)
    ap.add_argument('--report', default=None)
    a = ap.parse_args()
    rep, _ = launch(a.exe, a.cwd, a.open, a.save, a.report)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

