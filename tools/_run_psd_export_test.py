import os, sys, time, subprocess as sp, struct
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

u = ctypes.windll.user32
PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\Home\Workspace\UGit\psdto\test\psdto3d2022\sample\3d2.psd"
OUT_TIF = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\sample_out.tif"
OUT_PSD = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\sample_out.psd"

for p in (OUT_TIF, OUT_PSD):
    if os.path.exists(p): os.remove(p)

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
time.sleep(0.5)

# 写入打开与保存队列
with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n").encode("gbk"))

with open(os.path.join(PKG, "_dlgsave.txt"), "wb") as f:
    f.write((OUT_TIF + "\r\n" + OUT_PSD + "\r\n").encode("gbk"))

print("Starting psdto3d101.exe...")
proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

if not hwnd:
    print("Failed to find main window!")
    proc.terminate()
    sys.exit(1)

print(f"Main window hwnd=0x{hwnd:X}, loading PSD (cmd 7)...")
time.sleep(1.0)
win.command(hwnd, 7)
time.sleep(2.0)

print("Starting preview (cmd 12)...")
win.command(hwnd, 12)
time.sleep(2.0)

print("Stopping preview (cmd 13)...")
win.command(hwnd, 13)
time.sleep(1.0)

print("Exporting TIFF (cmd 16)...")
win.command(hwnd, 16)

# 等待 TIFF 导出彻底结束（文件生成且大小稳定，主程序恢复）
for i in range(50):
    if os.path.exists(OUT_TIF) and os.path.getsize(OUT_TIF) > 1000:
        prev_sz = os.path.getsize(OUT_TIF)
        time.sleep(1.5)
        curr_sz = os.path.getsize(OUT_TIF)
        if prev_sz == curr_sz:
            print(f"TIFF export finished: {curr_sz:,} bytes")
            break
    time.sleep(0.5)

time.sleep(2.0) # 确保主程序完全恢复事件循环

# 检查菜单项 17 状态
top = u.GetMenu(ctypes.c_void_p(hwnd))
sub = u.GetSubMenu(ctypes.c_void_p(top), 1)
st = u.GetMenuState(ctypes.c_void_p(sub), 17, 0x0)
print(f"Menu 17 state before trigger: 0x{st:X}")

print("Triggering Export PSD (cmd 17)...")
win.command(hwnd, 17)

for i in range(50):
    if os.path.exists(OUT_PSD) and os.path.getsize(OUT_PSD) > 1000:
        print(f"PSD created: {os.path.getsize(OUT_PSD):,} bytes!")
        break
    time.sleep(0.5)

time.sleep(1.0)
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

if os.path.exists(OUT_PSD):
    sz = os.path.getsize(OUT_PSD)
    with open(OUT_PSD, "rb") as f:
        head = f.read(26)
    sig, ver, reserved, channels, h, w, depth, mode = struct.unpack(">4sH6sHIIHH", head)
    print("="*50)
    print(f"SUCCESS: PSD File Size = {sz:,} bytes")
    print(f"  Signature : {sig}")
    print(f"  Version   : {ver}")
    print(f"  Channels  : {channels}")
    print(f"  Dimensions: {w} x {h}")
    print(f"  Depth     : {depth}-bit")
    print(f"  Mode      : {mode} (3=RGB, 4=CMYK)")
    print("="*50)
else:
    print("FAILED: OUT_PSD does not exist!")
    log_path = os.path.join(PKG, "_dongle.log")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="latin1", errors="ignore") as f:
            lines = f.readlines()[-40:]
        print("Last log lines:")
        for l in lines: print("  " + l.strip())
