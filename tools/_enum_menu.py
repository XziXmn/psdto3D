import os, sys, time, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

u = ctypes.windll.user32
PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"

proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

top = u.GetMenu(ctypes.c_void_p(hwnd))
n = u.GetMenuItemCount(ctypes.c_void_p(top))
print(f"Top menu count: {n}")

def dump_menu(hmenu, depth=0):
    cnt = u.GetMenuItemCount(ctypes.c_void_p(hmenu))
    buf = ctypes.create_unicode_buffer(128)
    for i in range(cnt):
        mid = u.GetMenuItemID(ctypes.c_void_p(hmenu), i)
        u.GetMenuStringW(ctypes.c_void_p(hmenu), i, buf, 128, 0x400)
        st = u.GetMenuState(ctypes.c_void_p(hmenu), i, 0x400)
        sub = u.GetSubMenu(ctypes.c_void_p(hmenu), i)
        print("  " * depth + f"pos={i} id={mid} state=0x{st:X} text='{buf.value}'")
        if sub:
            dump_menu(sub, depth + 1)

dump_menu(top)
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
