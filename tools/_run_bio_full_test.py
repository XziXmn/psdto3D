import os, sys, time, subprocess as sp
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\bio\a.psd"
PRJ = r"C:\bio\a.tw3d2"
OUT_TIF = r"C:\bio\bio_out.tif"
OUT_PSD = r"C:\bio\bio_out.psd"
OUT_GIF = r"C:\bio\bio_out.gif"

for f in [OUT_TIF, OUT_PSD, OUT_GIF]:
    if os.path.exists(f): os.remove(f)

sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
sp.run(["cmd", "/c", "rd", "/s", "/q", r"C:\ok3dtemp"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n" + PRJ + "\r\n").encode("gbk"))
with open(os.path.join(PKG, "_dlgsave.txt"), "wb") as f:
    f.write((OUT_TIF + "\r\n" + OUT_PSD + "\r\n" + OUT_GIF + "\r\n").encode("gbk"))

print("=== 生化危机大工程全流程回归测试 (4370x5197 32层) ===")
proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)
print(f"Process started, pid={pid} hwnd=0x{hwnd:X}")

time.sleep(1.0)
print("[1/4] 载入大图 PSD a.psd (cmd 7)...")
win.command(hwnd, 7)
time.sleep(3.0)

print("[2/4] 载入立体镜头参数 a.tw3d2 (cmd 10)...")
win.command(hwnd, 10)
time.sleep(2.5)

print("[3/4] 启动高精切片渲染与 TIFF 导出 (cmd 16)...")
t0 = time.time()
win.command(hwnd, 16)
for i in range(180):
    time.sleep(1.0)
    if os.path.exists(OUT_TIF) and os.path.getsize(OUT_TIF) > 5000000:
        prev = os.path.getsize(OUT_TIF)
        time.sleep(3.0)
        curr = os.path.getsize(OUT_TIF)
        if prev == curr and curr > 6000000:
            print(f"   TIFF 导出成功: {curr:,} 字节，总耗时 {time.time()-t0:.1f} 秒")
            break
    if (i + 1) % 15 == 0:
        temp_cnt = len(os.listdir(r"C:\ok3dtemp")) if os.path.exists(r"C:\ok3dtemp") else 0
        print(f"   [进行中 {i+1:3d}s] ok3dtemp 切片数: {temp_cnt}")
else:
    print(f"   TIFF 导出超时，当前大小: {os.path.getsize(OUT_TIF) if os.path.exists(OUT_TIF) else 0}")

time.sleep(3.0)

print("[4/4] 组装并导出多层超大 PSD (cmd 17)...")
t1 = time.time()
win.command(hwnd, 17)
for i in range(180):
    time.sleep(1.0)
    if os.path.exists(OUT_PSD) and os.path.getsize(OUT_PSD) > 500000000:
        prev = os.path.getsize(OUT_PSD)
        time.sleep(4.0)
        curr = os.path.getsize(OUT_PSD)
        if prev == curr and curr > 1000000000:
            print(f"   PSD 导出成功: {curr:,} 字节，总耗时 {time.time()-t1:.1f} 秒")
            break
    if (i + 1) % 15 == 0:
        sz = os.path.getsize(OUT_PSD) if os.path.exists(OUT_PSD) else 0
        print(f"   [进行中 {i+1:3d}s] bio_out.psd 大小: {sz:,} 字节")
else:
    print(f"   PSD 导出超时，当前大小: {os.path.getsize(OUT_PSD) if os.path.exists(OUT_PSD) else 0}")

time.sleep(3.0)

print("[可选] 导出动图 GIF (cmd 18)...")
t2 = time.time()
win.command(hwnd, 18)
for i in range(60):
    time.sleep(1.0)
    if os.path.exists(OUT_GIF) and os.path.getsize(OUT_GIF) > 2000000:
        prev = os.path.getsize(OUT_GIF)
        time.sleep(2.0)
        curr = os.path.getsize(OUT_GIF)
        if prev == curr and curr > 3500000:
            print(f"   GIF 导出成功: {curr:,} 字节，总耗时 {time.time()-t2:.1f} 秒")
            break
else:
    print(f"   GIF 导出超时，当前大小: {os.path.getsize(OUT_GIF) if os.path.exists(OUT_GIF) else 0}")

alive = proc.poll() is None
print("主程序进程存活状态:", alive)
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

print("\n" + "="*50)
print("=== 回归测试产物结果汇总 ===")
for p, name in [(OUT_TIF, "TIFF"), (OUT_PSD, "PSD"), (OUT_GIF, "GIF")]:
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"  [{name}] {p}: {sz:,} 字节 (成功)")
    else:
        print(f"  [{name}] {p}: 缺失 (失败)")
print("="*50)
