"""Open a project in psdto3d exactly like a user would (pywinauto, real input).

    python gui_open.py <exe> <file> [--menu "Open project"] [--shot out.png]
"""
import argparse
import os
import sys
import time

from pywinauto import Application
from pywinauto.keyboard import send_keys

import win


def shot(hwnd, path):
    try:
        win.capture(hwnd, path)
        return path
    except Exception as exc:  # noqa: BLE001
        return 'capture failed: %s' % exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('file')
    ap.add_argument('--menu', default='Open project')
    ap.add_argument('--shot', default=None)
    ap.add_argument('--settle', type=float, default=8.0)
    ap.add_argument('--action', default='open', choices=['open', 'import', 'settings'])
    a = ap.parse_args()

    app = Application(backend='win32').start(os.path.abspath(a.exe))
    time.sleep(5)
    win_ = app.top_window()
    hwnd = win_.handle
    print('main:', win_.window_text(), hwnd)
    try:
        win_.set_focus()
        print('set_focus ok')
    except Exception as exc:  # noqa: BLE001
        print('set_focus failed:', exc)

    # menu: click by Ctrl shortcut / by text
    label = {'open': 'Open project', 'import': 'Import *.psd', 'settings': 'Import settings'}[a.action]
    try:
        win_.menu_select(label, exact=False)
        print('menu_select ok:', label)
    except Exception as exc:  # noqa: BLE001
        print('menu_select failed:', exc)
        return 1
    time.sleep(3)

    # the shell dialog belongs to the same process
    dlg = None
    for w in app.windows():
        if w.class_name() == '#32770':
            dlg = w
            break
    if dlg is None:
        print('no file dialog')
        return 1
    print('dialog:', dlg.window_text())
    try:
        dlg.set_focus()
    except Exception:  # noqa: BLE001
        pass
    # type the path into the file name box
    try:
        edits = dlg.descendants(control_type='Edit')
        print('edits:', [(e.handle, e.window_text()) for e in edits][:4])
    except Exception as exc:  # noqa: BLE001
        print('descendants failed:', exc)
    try:
        dlg.type_keys(a.file, with_spaces=True, set_foreground=True)
        time.sleep(0.4)
        dlg.type_keys('{ENTER}')
        print('typed path + enter')
    except Exception as exc:  # noqa: BLE001
        print('typing failed:', exc)

    time.sleep(a.settle)
    msgs = []
    for w in win.windows(app.process):
        if w[1] in ('TMessageForm', '#32770') and w[3]:
            msgs.append((w[1], w[2]))
    print('dialogs after:', msgs)
    if a.shot:
        print(shot(hwnd, a.shot))
    return 0


if __name__ == '__main__':
    sys.exit(main())
