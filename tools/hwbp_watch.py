"""只读硬件断点观察器：抓"谁在写 [0x523090]（视差基准 off）"。

为什么用硬件断点：上一轮用 5 字节代码补丁插桩，把预览动画本身弄挂了（Delphi 对
指令边界/栈帧敏感）。硬件断点（DR0–DR3）不改代码字节，只在访问时触发异常，
是"观测而不干扰"的唯一办法。而且本轮已确认 exe 没有壳、没有 IsDebuggerPresent、
TLS 回调全 0，可以放心上调试器。

用法（带狗时用来观察真实动画）：
    python tools/hwbp_watch.py --pkg _review/pkgA --psd X.psd --settings Y.tw3d2 \
        --cmds "7@12,10@44,12@74,13@110" --duration 130 --out _review/runs/hw

输出：每次 off 被写的 Eip、返回值地址、以及栈上 8 个 dword（用来认调用者）。
"""
import argparse
import ctypes
import json
import os
import struct
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win

k32 = ctypes.windll.kernel32

# ---- 常量 ----
DEBUG_ONLY_THIS_PROCESS = 0x00000002
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
CREATE_THREAD_DEBUG_EVENT = 2
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_THREAD_DEBUG_EVENT = 4
EXIT_PROCESS_DEBUG_EVENT = 5
LOAD_DLL_DEBUG_EVENT = 6
UNLOAD_DLL_DEBUG_EVENT = 7
OUTPUT_DEBUG_STRING_EVENT = 8
RIP_EVENT = 9
EXCEPTION_BREAKPOINT = 0x80000003
EXCEPTION_SINGLE_STEP = 0x80000004
STATUS_WX86_SINGLE_STEP = 0x4000001F
CONTEXT_DEBUG_REGISTERS = 0x00010010
CONTEXT_FULL = 0x00010007
WATCH_ADDR = 0x00523090          # off（视差基准）


class CONTEXT(ctypes.Structure):
    """i386 CONTEXT，仅到 Dr7 为止够用；后面按 716 字节补足。"""
    _fields_ = [
        ("ContextFlags", wintypes.DWORD),
        ("Dr0", wintypes.DWORD), ("Dr1", wintypes.DWORD),
        ("Dr2", wintypes.DWORD), ("Dr3", wintypes.DWORD),
        ("Dr6", wintypes.DWORD), ("Dr7", wintypes.DWORD),
        ("FloatSave", ctypes.c_byte * 112),
        ("SegGs", wintypes.DWORD), ("SegFs", wintypes.DWORD),
        ("SegEs", wintypes.DWORD), ("SegDs", wintypes.DWORD),
        ("Edi", wintypes.DWORD), ("Esi", wintypes.DWORD),
        ("Ebx", wintypes.DWORD), ("Edx", wintypes.DWORD),
        ("Ecx", wintypes.DWORD), ("Eax", wintypes.DWORD),
        ("Ebp", wintypes.DWORD), ("Eip", wintypes.DWORD),
        ("SegCs", wintypes.DWORD), ("EFlags", wintypes.DWORD),
        ("Esp", wintypes.DWORD), ("SegSs", wintypes.DWORD),
        ("ExtendedRegisters", ctypes.c_byte * 512),
    ]


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [
        ("ExceptionCode", wintypes.DWORD),
        ("ExceptionFlags", wintypes.DWORD),
        ("ExceptionRecord", ctypes.c_void_p),
        ("ExceptionAddress", ctypes.c_void_p),
        ("NumberParameters", wintypes.DWORD),
        ("ExceptionInformation", ctypes.c_void_p * 15),
    ]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("ExceptionRecord", EXCEPTION_RECORD), ("dwFirstChance", wintypes.DWORD)]


class CREATE_THREAD_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("hThread", wintypes.HANDLE), ("lpThreadLocalBase", ctypes.c_void_p),
                ("lpStartAddress", ctypes.c_void_p)]


class CREATE_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("hFile", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
                ("hThread", wintypes.HANDLE), ("lpBaseOfImage", ctypes.c_void_p),
                ("dwDebugInfoFileOffset", wintypes.DWORD), ("nDebugInfoSize", wintypes.DWORD),
                ("lpThreadLocalBase", ctypes.c_void_p), ("lpStartAddress", ctypes.c_void_p),
                ("lpImageName", ctypes.c_void_p), ("fUnicode", wintypes.WORD)]


class LOAD_DLL_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("hFile", wintypes.HANDLE), ("lpBaseOfDll", ctypes.c_void_p),
                ("dwDebugInfoFileOffset", wintypes.DWORD), ("nDebugInfoSize", wintypes.DWORD),
                ("lpImageName", ctypes.c_void_p), ("fUnicode", wintypes.WORD)]


class U_DEBUG_EVENT(ctypes.Union):
    _fields_ = [("Exception", EXCEPTION_DEBUG_INFO),
                ("CreateThread", CREATE_THREAD_DEBUG_INFO),
                ("CreateProcessInfo", CREATE_PROCESS_DEBUG_INFO),
                ("LoadDll", LOAD_DLL_DEBUG_INFO)]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [("dwDebugEventCode", wintypes.DWORD), ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD), ("u", U_DEBUG_EVENT)]


class STARTUPINFOA(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", ctypes.c_char_p), ("lpDesktop", ctypes.c_char_p),
        ("lpTitle", ctypes.c_char_p), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


k32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                               ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.LPCWSTR,
                               ctypes.POINTER(STARTUPINFOA), ctypes.POINTER(PROCESS_INFORMATION)]
k32.WaitForDebugEvent.argtypes = [ctypes.POINTER(DEBUG_EVENT), wintypes.DWORD]
k32.ContinueDebugEvent.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
k32.Wow64GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.POINTER(CONTEXT)]
k32.Wow64SetThreadContext.argtypes = [wintypes.HANDLE, ctypes.POINTER(CONTEXT)]
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]


def read_mem(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) and got.value == n:
        return buf.raw
    return None


def set_watch(hThread, hits_log):
    """在指定线程上把 DR0 设成"写 4 字节 @ WATCH_ADDR"。"""
    ctx = CONTEXT()
    ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS
    if not k32.Wow64GetThreadContext(hThread, ctypes.byref(ctx)):
        return False
    ctx.Dr0 = WATCH_ADDR
    # L0=1(bit0) | RW0=01 写(bits16-17) | LEN0=11 四字节(bits18-19)
    ctx.Dr7 = (ctx.Dr7 & ~0x000F0003) | 0x000D0001
    ctx.Dr6 = 0
    ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS
    ok = bool(k32.Wow64SetThreadContext(hThread, ctypes.byref(ctx)))
    hits_log.append({"set_dr0": hex(WATCH_ADDR), "ok": ok, "dr7": hex(ctx.Dr7)})
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--exe", default="psdto3d101.exe")
    ap.add_argument("--psd", required=True)
    ap.add_argument("--settings", required=True)
    ap.add_argument("--cmds", default="7@12,10@44,12@74,13@110")
    ap.add_argument("--duration", type=float, default=130)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pkg = os.path.abspath(a.pkg)
    outd = os.path.abspath(a.out)
    os.makedirs(outd, exist_ok=True)
    psd = os.path.abspath(a.psd)
    sett = os.path.abspath(a.settings)
    with open(os.path.join(pkg, "_dlgopen.txt"), "wb") as f:
        f.write((psd + "\r\n").encode("gbk", "ignore"))
        f.write((sett + "\r\n").encode("gbk", "ignore"))
        f.write((psd + "\r\n").encode("gbk", "ignore"))
    with open(os.path.join(pkg, "_dlgsave.txt"), "wb") as f:
        f.write((os.path.join(outd, "out.tif") + "\r\n").encode("gbk", "ignore"))
        f.write((os.path.join(outd, "out.psd") + "\r\n").encode("gbk", "ignore"))

    si = STARTUPINFOA(); si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()
    env = os.environ.copy()
    env["NODLGPATCH"] = "1"
    os.environ["NODLGPATCH"] = "1"
    cmd = '"%s"' % os.path.join(pkg, a.exe)
    if not k32.CreateProcessW(None, cmd, None, None, False,
                              DEBUG_ONLY_THIS_PROCESS, None, pkg,
                              ctypes.byref(si), ctypes.byref(pi)):
        raise SystemExit("CreateProcess 失败: %s" % ctypes.WinError())
    hproc, pid = pi.hProcess, pi.dwProcessId
    print(json.dumps({"pid": pid}, ensure_ascii=False))

    hits = []
    info = {"pid": pid, "hits": hits, "events": [], "dr": []}
    hwnd = None
    t0 = time.time()
    sched = sorted((float(t), int(c)) for c, t in (x.split("@") for x in a.cmds.split(",")))
    nxt = 0
    dead = False

    def set_watch_all_threads():
        """主窗口出现后再给所有线程设一次断点（Delphi 启动期会重置上下文）。"""
        TH32CS_SNAPTHREAD = 0x00000004

        class THREADENTRY32(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                        ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD)]

        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
        if snap in (None, -1):
            return
        te = THREADENTRY32(); te.dwSize = ctypes.sizeof(te)
        n = 0
        if k32.Thread32First(snap, ctypes.byref(te)):
            while True:
                if te.th32OwnerProcessID == pid:
                    h = k32.OpenThread(0x0002 | 0x0008 | 0x0010 | 0x0020, False, te.th32ThreadID)
                    if h:
                        if set_watch(h, info["dr"]):
                            n += 1
                        k32.CloseHandle(h)
                if not k32.Thread32Next(snap, ctypes.byref(te)):
                    break
        k32.CloseHandle(snap)
        info.setdefault("dr_late", []).append({"threads": n, "t": round(time.time() - t0, 1)})

    def pump(timeout_ms):
        dbe = DEBUG_EVENT()
        if not k32.WaitForDebugEvent(ctypes.byref(dbe), timeout_ms):
            return False, 0
        code = dbe.dwDebugEventCode
        cont = DBG_CONTINUE
        if code == CREATE_PROCESS_DEBUG_EVENT:
            h = dbe.u.CreateProcessInfo.hThread
            set_watch(h, info["dr"])
        elif code == CREATE_THREAD_DEBUG_EVENT:
            set_watch(dbe.u.CreateThread.hThread, info["dr"])
        elif code == EXCEPTION_DEBUG_EVENT:
            er = dbe.u.Exception.ExceptionRecord
            ec = er.ExceptionCode
            if ec in (EXCEPTION_SINGLE_STEP, STATUS_WX86_SINGLE_STEP):
                tid = dbe.dwThreadId
                hThread = k32.OpenThread(0x0008 | 0x0002, False, tid)  # SUSPEND_RESUME|GET_CONTEXT
                if hThread:
                    ctx = CONTEXT(); ctx.ContextFlags = CONTEXT_FULL
                    if k32.Wow64GetThreadContext(hThread, ctypes.byref(ctx)):
                        ret = read_mem(hproc, ctx.Esp, 40)
                        stack = list(struct.unpack_from("<10I", ret, 0)) if ret else []
                        val = read_mem(hproc, WATCH_ADDR, 4)
                        hits.append({
                            "t": round(time.time() - t0, 2),
                            "eip": hex(ctx.Eip),
                            "esp": hex(ctx.Esp),
                            "stack": [hex(v) for v in stack],
                            "off_now": struct.unpack("<I", val)[0] if val else None,
                            "eax": hex(ctx.Eax),
                        })
                    k32.CloseHandle(hThread)
                # 清 DR6 后再继续
                cont = DBG_CONTINUE
            elif ec == EXCEPTION_BREAKPOINT:
                cont = DBG_CONTINUE
            else:
                info["events"].append({"code": hex(ec), "addr": hex(er.ExceptionAddress or 0)})
                cont = DBG_EXCEPTION_NOT_HANDLED
        elif code == EXIT_PROCESS_DEBUG_EVENT:
            info["exited"] = True
            dead = True
        k32.ContinueDebugEvent(dbe.dwProcessId, dbe.dwThreadId, cont)
        return True, code

    while time.time() - t0 < a.duration and not dead:
        pump(50)
        el = time.time() - t0
        if hwnd is None:
            try:
                mw = [w for w in win.windows(pid) if w[1] == 'TForm1' and w[3]]
                if mw:
                    hwnd = mw[0][0]
                    print("hwnd", hwnd)
                    time.sleep(0.4)
                    set_watch_all_threads()
            except Exception:
                pass
        if hwnd:
            if nxt < len(sched) and el >= sched[nxt][0]:
                win.command(hwnd, sched[nxt][1])
                info.setdefault("cmds", []).append({"t": round(el, 1), "cmd": sched[nxt][1]})
                nxt += 1
            try:
                for h, cls, title, vis in win.windows(pid):
                    if vis and cls in ("#32770", "TMessageForm"):
                        for kh, kcls, ktxt in win.children(h, 3):
                            if kcls in ("TButton", "Button"):
                                win.click(kh)
                                break
            except Exception:
                pass

    info["elapsed"] = round(time.time() - t0, 1)
    os.system("taskkill /PID %d /F >nul 2>&1" % pid)
    with open(os.path.join(outd, "hwbp.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print("命中 %d 次；报告: %s" % (len(hits), os.path.join(outd, "hwbp.json")))
    for h in hits[:14]:
        print("  t=%-6s eip=%s esp=%s off=%s" % (h["t"], h["eip"], h["esp"], h["off_now"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
