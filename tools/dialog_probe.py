"""Find a focus-free way to close the shell file dialog, then report which method worked."""
import ctypes, subprocess as sp, sys, time
from ctypes import wintypes
import win

u = ctypes.windll.user32
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_COMMAND = 0x0111
BM_CLICK = 0x00F5
VK_RETURN = 0x0D


def visible(pid, cls='#32770'):
    return [w for w in win.windows(pid) if w[1] == cls and w[3]]


def main():
    exe_dir = sys.argv[1]
    proc = sp.Popen([exe_dir + r'\psdto3d101.exe'], cwd=exe_dir)
    time.sleep(5)
    pid = proc.pid
    hwnd = [w for w in win.windows(pid) if w[1] == 'TForm1'][0][0]
    win.command(hwnd, 3)
    time.sleep(3)
    d = visible(pid)
    if not d:
        print('no dialog')
        proc.kill()
        return 1
    dlg = d[-1][0]
    ok = u.GetDlgItem(ctypes.c_void_p(dlg), 1)
    print('dlg=%s ok=%s' % (dlg, ok))

    def closed():
        time.sleep(1.5)
        return not any(w[0] == dlg and w[3] for w in win.windows(pid))

    tests = [
        ('A post WM_KEYDOWN/UP to dialog',
         lambda: (u.PostMessageW(ctypes.c_void_p(dlg), WM_KEYDOWN, wintypes.WPARAM(VK_RETURN), wintypes.LPARAM(0x001C0001)),
                  u.PostMessageW(ctypes.c_void_p(dlg), WM_KEYUP, wintypes.WPARAM(VK_RETURN), wintypes.LPARAM(0xC01C0001)))),
        ('B post WM_COMMAND IDOK to dialog',
         lambda: u.PostMessageW(ctypes.c_void_p(dlg), WM_COMMAND, wintypes.WPARAM(1), wintypes.LPARAM(ok))),
        ('C send WM_COMMAND IDOK with button hwnd',
         lambda: u.SendMessageW(ctypes.c_void_p(dlg), WM_COMMAND, wintypes.WPARAM(1), wintypes.LPARAM(ok))),
        ('D BM_CLICK on OK button',
         lambda: u.SendMessageW(ctypes.c_void_p(ok), BM_CLICK, 0, 0)),
        ('E post mouse down/up on OK button',
         lambda: (u.PostMessageW(ctypes.c_void_p(ok), 0x0201, wintypes.WPARAM(1), wintypes.LPARAM(0x00050005)),
                  u.PostMessageW(ctypes.c_void_p(ok), 0x0202, wintypes.WPARAM(0), wintypes.LPARAM(0x00050005)))),
        ('F DM_GETDEFID then BM_CLICK',
         lambda: u.SendMessageW(ctypes.c_void_p(dlg), 0x0400, 0, 0)),
    ]
    for name, fn in tests:
        if not any(w[0] == dlg and w[3] for w in win.windows(pid)):
            print('dialog already closed before', name)
            break
        try:
            r = fn()
        except Exception as exc:  # noqa: BLE001
            print(name, 'error', exc)
            continue
        print('%-42s -> %s  closed=%s' % (name, r, closed()))
        time.sleep(0.5)

    print('remaining dialogs:', visible(pid))
    print('messages:', [w for w in win.windows(pid) if w[1] == 'TMessageForm' and w[3]])
    proc.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())
