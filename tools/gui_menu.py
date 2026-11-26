"""Drive psdto3d with pywinauto (real focus handling) and dump its menu tree,
including the Languages submenu, so we can switch the UI to Chinese."""
import sys
import time

from pywinauto import Application
from pywinauto.keyboard import send_keys

EXE = sys.argv[1] if len(sys.argv) > 1 else r'C:\Home\Workspace\UGit\psdto\psdto3d10.1绿色版\psdto3d101.exe'


def dump_menu(menu, depth=0, path=''):
    for item in menu.items():
        text = item.text()
        mid = item.ID
        state = []
        try:
            checked = item.is_checked()
        except Exception:
            checked = False
        if checked:
            state.append('checked')
        print('%s%-6s id=%-4s %r %s' % ('  ' * depth, path, mid, text, ' '.join(state)))
        try:
            sub = item.sub_menu()
        except Exception:
            sub = None
        if sub:
            dump_menu(sub, depth + 1, path + str(mid) + '.')


app = Application(backend='win32').start(EXE)
time.sleep(5)
win = app.top_window()
win.set_focus()
print('main:', win.window_text(), win.handle)
menu = win.menu()
dump_menu(menu)
print('--- try Languages submenu')
for item in menu.items():
    if 'Language' in item.text():
        sub = item.sub_menu()
        if sub:
            dump_menu(sub, 1, 'lang.')
        break
print('--- values that may carry the language choice')
try:
    print('settings combo:', [c.window_text() for c in win.descendants(control_type='ComboBox')][:6])
except Exception as exc:  # noqa: BLE001
    print('descendants failed', exc)
