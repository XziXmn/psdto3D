import os, sys, time, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\bio\a.psd"
PRJ = r"C:\bio\a.tw3d2"
OUT_TIF = r"C:\bio\test_out.tif"
OUT_PSD = r"C:\bio\test_out.psd"
OUT_GIF = r"C:\bio\test_out.gif"

for f in [OUT_TIF, OUT_PSD, OUT_GIF]:
    if os.path.exists(f): os.remove(f)

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
sp.run(["cmd", "/c", "rd", "/s", "/q", r"C:\ok3dtemp"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n" + PRJ + "\r\n").encode("gbk"))
with open(os.path.join(PKG, "_dlgsave.txt"), "wb") as f:
    f.write((OUT_TIF + "\r\n" + OUT_PSD + "\r\n" + OUT_GIF + "\r\n").encode("gbk"))

proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)
print("Process started, pid=%d hwnd=%s" % (pid, hwnd))

time.sleep(1.0)
print("1. Import PSD (cmd 7)...")
win.command(hwnd, 7)
time.sleep(3.0)

print("2. Import settings (cmd 10)...")
win.command(hwnd, 10)
time.sleep(2.0)

print("3. Preview 3D (cmd 12)...")
win.command(hwnd, 12)
time.sleep(6.0) # preview running
win.command(hwnd, 13) # stop preview
time.sleep(1.0)

print("4. Export TIFF (cmd 16)...")
win.command(hwnd, 16)
for _ in range(60):
    if os.path.exists(OUT_TIF) and os.path.getsize(OUT_TIF) > 1000000: break
    time.sleep(1.0)
tif_sz = os.path.getsize(OUT_TIF) if os.path.exists(OUT_TIF) else 0
print("   TIFF size=%d" % tif_sz)

print("5. Export PSD (cmd 17)...")
win.command(hwnd, 17)
for _ in range(60):
    if os.path.exists(OUT_PSD) and os.path.getsize(OUT_PSD) > 1000000: break
    time.sleep(1.0)
psd_sz = os.path.getsize(OUT_PSD) if os.path.exists(OUT_PSD) else 0
print("   PSD size=%d" % psd_sz)

print("6. Export GIF (cmd 18)...")
win.command(hwnd, 18)
for _ in range(40):
    if os.path.exists(OUT_GIF) and os.path.getsize(OUT_GIF) > 100000: break
    time.sleep(1.0)
gif_sz = os.path.getsize(OUT_GIF) if os.path.exists(OUT_GIF) else 0
print("   GIF size=%d" % gif_sz)

alive = proc.poll() is None
print("Process alive:", alive)
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
