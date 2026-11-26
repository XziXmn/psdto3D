"""End-to-end GUI driver: open a project, generate, export, and report what lands on disk.

The shell file dialog cannot be driven with messages, but it always selects the
first item, so the caller renames the target project to sort first.  Everything
else (message boxes, the save dialog) is handled with real Enter keys after the
window is forced to the foreground.
"""
import ctypes, os, subprocess as sp, sys, time
from ctypes import wintypes
import win

u = ctypes.windll.user32

CMD_OPEN_PROJECT = 3
CMD_IMPORT_PSD = 7
CMD_PREVIEW = 12
CMD_STOP_PREVIEW = 13
CMD_EXPORT_TIFF = 16
CMD_EXPORT_PSD = 17
CMD_EXPORT_GIF = 18


def force_fg(hwnd):
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
    time.sleep(0.3)
    for t in att:
        u.AttachThreadInput(cur, t, False)
    return u.GetForegroundWindow() == hwnd


def enter():
    u.keybd_event(0x0D, 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(0x0D, 0, 2, 0)


def snap(pid, tag):
    """Report windows and capture visible message boxes."""
    out = []
    for w in win.windows(pid):
        h, cls, title, vis = w
        if not vis or cls in ('tooltips_class32', 'MSCTFIME UI', 'IME', 'ComboLBox'):
            continue
        out.append((h, cls, title))
    return out


def dismiss(pid, tag, shot_prefix):
    """Click OK / press Enter on any visible TMessageForm."""
    handled = []
    for h, cls, title, vis in win.windows(pid):
        if cls != 'TMessageForm' or not vis:
            continue
        png = '%s_%s_%d.png' % (shot_prefix, cls, h)
        try:
            win.capture(h, png)
        except Exception:  # noqa: BLE001
            png = None
        clicked = False
        for kh, kcls, ktxt in win.children(h, maxdepth=2):
            if kcls == 'TButton':
                win.click(kh)
                clicked = True
                break
        if not clicked:
            force_fg(h)
            enter()
        handled.append((png, clicked))
        time.sleep(0.8)
    return handled


def dialogs(pid, cls):
    return [w for w in win.windows(pid) if w[1] == cls and w[3]]


def main():
    exe_dir, tag, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
    steps = [int(x) for x in sys.argv[4:]] or [CMD_PREVIEW]
    before = set()
    for root in (exe_dir, os.path.join(exe_dir, 'sample')):
        if os.path.isdir(root):
            for n in os.listdir(root):
                before.add(os.path.join(root, n))

    proc = sp.Popen([os.path.join(exe_dir, 'psdto3d101.exe')], cwd=exe_dir)
    time.sleep(5)
    pid = proc.pid
    mw = [w for w in win.windows(pid) if w[1] == 'TForm1']
    if not mw:
        print('FAIL no main window')
        return 1
    main_hwnd = mw[0][0]
    print('main fg:', force_fg(main_hwnd))

    win.command(main_hwnd, CMD_OPEN_PROJECT)
    time.sleep(3)
    dlg = dialogs(pid, '#32770')
    if not dlg:
        print('FAIL no open dialog')
        proc.kill()
        return 1
    print('dialog fg:', force_fg(dlg[-1][0]))
    time.sleep(0.4)
    enter()                       # accepts the first (selected) item
    time.sleep(6)
    print('after open:', snap(pid, tag))
    print('dismiss:', dismiss(pid, tag, out_png + '_open'))
    time.sleep(1)

    for c in steps:
        print('--- command', c)
        win.command(main_hwnd, c)
        time.sleep(10)
        print('windows:', snap(pid, tag))
        d = dialogs(pid, '#32770')
        if d:
            print('save dialog, fg:', force_fg(d[-1][0]))
            time.sleep(0.6)
            enter()
            time.sleep(6)
        print('dismiss:', dismiss(pid, tag, '%s_cmd%d' % (out_png, c)))

    print('final windows:', snap(pid, tag))
    try:
        print('main capture:', win.capture(main_hwnd, out_png + '_main.png'))
    except Exception as exc:  # noqa: BLE001
        print('capture failed', exc)
    print('alive:', proc.poll() is None)

    after = []
    for root in (exe_dir, os.path.join(exe_dir, 'sample'), r'C:\ok3dtemp'):
        if os.path.isdir(root):
            for n in os.listdir(root):
                p = os.path.join(root, n)
                if p not in before:
                    try:
                        after.append((p, os.path.getsize(p)))
                    except OSError:
                        after.append((p, -1))
    print('new files in package/sample/temp:')
    for p, sz in after:
        print('   %10d  %s' % (sz, p))
    proc.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())
