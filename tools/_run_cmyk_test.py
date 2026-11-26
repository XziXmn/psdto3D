import os, sys, time, subprocess as sp, struct
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\Home\Workspace\UGit\psdto\test\psdto3d2022\sample\psdsampleCMYK.psd"
OUT_TIF = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\cmyk_out.tif"
OUT_PSD = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\cmyk_out.psd"

for p in (OUT_TIF, OUT_PSD):
    if os.path.exists(p): os.remove(p)

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
time.sleep(0.5)

with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n").encode("gbk"))
with open(os.path.join(PKG, "_dlgsave.txt"), "wb") as f:
    f.write((OUT_TIF + "\r\n" + OUT_PSD + "\r\n").encode("gbk"))

print("=== CMYK 4通道工程测试 ===")
proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

time.sleep(1.0)
print("1. 载入 CMYK PSD (cmd 7)...")
win.command(hwnd, 7)
time.sleep(2.0)

print("2. 预览 (cmd 12/13)...")
win.command(hwnd, 12)
time.sleep(2.0)
win.command(hwnd, 13)
time.sleep(1.0)

print("3. 导出 TIFF (cmd 16)...")
win.command(hwnd, 16)
for i in range(40):
    if os.path.exists(OUT_TIF) and os.path.getsize(OUT_TIF) > 1000:
        print(f"   CMYK TIFF 生成: {os.path.getsize(OUT_TIF):,} 字节")
        break
    time.sleep(0.5)

time.sleep(2.0)
print("4. 导出 PSD (cmd 17)...")
win.command(hwnd, 17)
for i in range(40):
    if os.path.exists(OUT_PSD) and os.path.getsize(OUT_PSD) > 1000:
        print(f"   CMYK PSD 生成: {os.path.getsize(OUT_PSD):,} 字节")
        break
    time.sleep(0.5)

alive = proc.poll() is None
print("进程存活:", alive)
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

if os.path.exists(OUT_PSD):
    with open(OUT_PSD, "rb") as f: head = f.read(26)
    sig, ver, res, chan, h, w, depth, mode = struct.unpack(">4sH6sHIIHH", head)
    print(f"SUCCESS CMYK PSD: {w}x{h}, Channels={chan}, Mode={mode} (4=CMYK)")
else:
    print("FAILED: CMYK PSD missing")
