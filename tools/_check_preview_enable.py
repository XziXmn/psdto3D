import os, sys, time, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

u = ctypes.windll.user32
def get_menu_info(hwnd):
    top = u.GetMenu(ctypes.c_void_p(hwnd))
    sub = u.GetSubMenu(ctypes.c_void_p(top), 1)
    buf = ctypes.create_unicode_buffer(128)
    res = {}
    for j in range(u.GetMenuItemCount(ctypes.c_void_p(sub))):
        mid = u.GetMenuItemID(ctypes.c_void_p(sub), j)
        st = u.GetMenuState(ctypes.c_void_p(sub), j, 0x400)
        u.GetMenuStringW(ctypes.c_void_p(sub), j, buf, 128, 0x400)
        res[mid] = (st, buf.value)
    return res

PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\bio\a.psd"
PRJ = r"C:\bio\a.tw3d2"

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
sp.run(["cmd", "/c", "rd", "/s", "/q", r"C:\ok3dtemp"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n" + PRJ + "\r\n").encode("gbk"))

proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

print("Started")
time.sleep(1.0)
win.command(hwnd, 7) # import psd
time.sleep(3.0)

win.command(hwnd, 10) # import settings
time.sleep(3.0)
m1 = get_menu_info(hwnd)
print("After import 10: menu 12 (preview)=%s, menu 16 (tiff)=%s" % (m1.get(12), m1.get(16)))

print("Starting preview (cmd 12)...")
win.command(hwnd, 12)

# Monitor ok3dtemp file count and menu 16 state for 40 seconds
for sec in range(40):
    time.sleep(1.0)
    files = [f for f in os.listdir(r"C:\ok3dtemp")] if os.path.exists(r"C:\ok3dtemp") else []
    m2 = get_menu_info(hwnd)
    if sec % 5 == 0 or (m2.get(16) and m2.get(16)[0] == 0):
        print("sec %2d: temp files=%d, menu16 state=0x%X" % (sec, len(files), m2.get(16)[0]))
    if m2.get(16) and m2.get(16)[0] == 0:
        print("Menu 16 ENABLED at sec %d!" % sec)
        break

sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
