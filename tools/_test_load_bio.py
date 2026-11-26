import os, sys, time, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win

PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\Home\Workspace\UGit\psdto\test\0《生化危机：爆发夜》第一人称海报汉化\0《生化危机：爆发夜》第一人称海报汉化.psd"

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
sp.run(["cmd", "/c", "rd", "/s", "/q", r"C:\ok3dtemp"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n").encode("gbk"))

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

# Check for dialogs within 15 seconds
err = None
t0 = time.time()
while time.time() - t0 < 15:
    for h, cls, t, vis in win.windows(pid):
        if vis and cls in ("#32770", "TMessageForm"):
            kids = [k[2] for k in win.children(h, 3) if k[2]]
            err = kids[0] if kids else cls
            break
    if err: break
    time.sleep(0.5)

title = [t for h, c, t, v in win.windows(pid) if h == hwnd]
print("Import result: err=%s, title=%s" % (err, title[0] if title else ""))
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
