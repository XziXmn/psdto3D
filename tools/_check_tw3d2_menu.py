import sys, time, os, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

u = ctypes.windll.user32
PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\bio\a.psd"
PRJ = r"C:\bio\a.tw3d2"

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n" + PRJ + "\r\n").encode("gbk"))

proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

time.sleep(1.0)
win.command(hwnd, 7) # load psd
time.sleep(2.0)
win.command(hwnd, 10) # load tw3d2
time.sleep(2.0)

top = u.GetMenu(ctypes.c_void_p(hwnd))
sub = u.GetSubMenu(ctypes.c_void_p(top), 1)
buf = ctypes.create_unicode_buffer(128)
cnt = u.GetMenuItemCount(ctypes.c_void_p(sub))
print(f"Submenu count after loading tw3d2: {cnt}")
for i in range(cnt):
    mid = u.GetMenuItemID(ctypes.c_void_p(sub), i)
    st = u.GetMenuState(ctypes.c_void_p(sub), i, 0x400)
    u.GetMenuStringW(ctypes.c_void_p(sub), i, buf, 128, 0x400)
    print(f"  pos={i:2d} id={mid:2d} state=0x{st:X} text='{buf.value}'")

sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
