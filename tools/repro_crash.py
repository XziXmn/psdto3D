"""Reproduce the 0x50A001 crash with real mouse clicks.

open dialog -> click the first file in the list -> click 打开 -> dismiss any
message box -> trigger 3D preview/export -> report the dialogs (captured as PNG).
"""
import ctypes, subprocess as sp, sys, time
from ctypes import wintypes
import win

u = ctypes.windll.user32


def force_foreground(hwnd):
    fg = u.GetForegroundWindow()
    tt = u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), None)
    ft = u.GetWindowThreadProcessId(ctypes.c_void_p(fg), None)
    cur = ctypes.windll.kernel32.GetCurrentThreadId()
    att = []
    for t in (ft, tt):
        if t and t != cur and u.AttachThreadInput(cur, t, True):
            att.append(t)
    u.BringWindowToTop(ctypes.c_void_p(hwnd))
    u.SetForegroundWindow(ctypes.c_void_p(hwnd))
    time.sleep(0.25)
    for t in att:
        u.AttachThreadInput(cur, t, False)


def click_at(x, y):
    u.SetCursorPos(x, y)
    time.sleep(0.15)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.25)


def center(hwnd):
    r = wintypes.RECT()
    u.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
    return (r.left + r.right) // 2, (r.top + r.bottom) // 2, r


def boxes(pid):
    return [w for w in win.windows(pid) if w[1] == 'TMessageForm' and w[3]]


def dismiss_boxes(pid, tag):
    seen = []
    for h, cls, title, vis in boxes(pid):
        png = '%s_msg_%d.png' % (tag, h)
        try:
            win.capture(h, png)
        except Exception:  # noqa: BLE001
            png = None
        seen.append(png)
        for kh, kcls, ktxt in win.children(h, maxdepth=2):
            if kcls == 'TButton':
                win.click(kh)
                break
        time.sleep(0.7)
    return seen


def main():
    exe_dir, tag = sys.argv[1], sys.argv[2]
    cmds = [int(x) for x in sys.argv[3:]] or [12]
    proc = sp.Popen([exe_dir + r'\psdto3d101.exe'], cwd=exe_dir)
    time.sleep(5)
    pid = proc.pid
    main_w = [w for w in win.windows(pid) if w[1] == 'TForm1']
    if not main_w:
        print('FAIL: no main window')
        proc.kill()
        return 1
    hwnd = main_w[0][0]
    force_foreground(hwnd)

    win.command(hwnd, 3)
    time.sleep(3)
    dlgs = [w for w in win.windows(pid) if w[1] == '#32770' and w[3]]
    if not dlgs:
        print('no file dialog')
        proc.kill()
        return 1
    d = dlgs[-1][0]
    force_foreground(d)
    time.sleep(0.4)

    listview = [k for k in win.children(d, maxdepth=3) if k[1] == 'SysListView32' and _title_of(k[0]) == 'FolderView']
    if listview:
        lx, ly, r = center(listview[0][0])
        print('listview rect', r.left, r.top, r.right, r.bottom)
        click_at(r.left + 60, r.top + 30)     # first item
    ok = u.GetDlgItem(ctypes.c_void_p(d), 1)
    if ok:
        ox, oy, r = center(ok)
        print('open button at', ox, oy)
        click_at(ox, oy)
    time.sleep(7)

    print('messages after open:', dismiss_boxes(pid, tag + '_open'))
    time.sleep(1)

    for c in cmds:
        print('command %d' % c)
        win.command(hwnd, c)
        time.sleep(8)
        print('   messages:', dismiss_boxes(pid, '%s_cmd%d' % (tag, c)))
        time.sleep(1)

    try:
        print('main capture:', win.capture(hwnd, tag + '_main.png'))
    except Exception as exc:  # noqa: BLE001
        print('main capture failed', exc)
    print('alive:', proc.poll() is None)
    proc.kill()
    return 0


def _title_of(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(ctypes.c_void_p(h), b, 256)
    return b.value


if __name__ == '__main__':
    sys.exit(main())
