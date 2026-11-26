import os, sys, time, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

u = ctypes.windll.user32
PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\Home\Workspace\UGit\psdto\test\psdto3d2022\sample\3d2.psd"
OUT_TIF = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\check_menu.tif"
OUT_PSD = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\check_menu.psd"

for f in [OUT_TIF, OUT_PSD]:
    if os.path.exists(f): os.remove(f)

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n").encode("gbk"))
with open(os.path.join(PKG, "_dlgsave.txt"), "wb") as f:
    f.write((OUT_TIF + "\r\n" + OUT_PSD + "\r\n").encode("gbk"))

proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

time.sleep(1.0)
win.command(hwnd, 7) # import psd
time.sleep(2.0)
win.command(hwnd, 12) # preview
time.sleep(3.0)
win.command(hwnd, 13) # stop preview
time.sleep(1.0)

# Export TIFF
win.command(hwnd, 16)
for _ in range(30):
    if os.path.exists(OUT_TIF): break
    time.sleep(0.5)
print("TIFF size:", os.path.getsize(OUT_TIF) if os.path.exists(OUT_TIF) else 0)

# Unlock menu 17 and menu 18
top = u.GetMenu(ctypes.c_void_p(hwnd))
sub = u.GetSubMenu(ctypes.c_void_p(top), 1)
u.EnableMenuItem(ctypes.c_void_p(sub), 17, 0x00000000) # MF_ENABLED
u.EnableMenuItem(ctypes.c_void_p(sub), 18, 0x00000000)

print("Sending cmd 17 (Export PSD)...")
win.command(hwnd, 17)
for _ in range(30):
    if os.path.exists(OUT_PSD) and os.path.getsize(OUT_PSD) > 1000: break
    time.sleep(0.5)

print("PSD size:", os.path.getsize(OUT_PSD) if os.path.exists(OUT_PSD) else 0)

sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
