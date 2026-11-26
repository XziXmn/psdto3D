import os, sys, time, subprocess as sp, struct
sys.path.insert(0, r"C:\Home\Workspace\UGit\psdto\tools")
import win, ctypes

PKG = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
PSD = r"C:\Home\Workspace\UGit\psdto\test\psdto3d2022\sample\3d2.psd"
OUT_PSD = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1\direct_test.psd"

if os.path.exists(OUT_PSD): os.remove(OUT_PSD)

# 确保预先清空 C:\ok3dtemp，测试纯粹的“零切片直接导出PSD”
sp.run(["taskkill", "/IM", "psdto3d101.exe", "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
sp.run(["cmd", "/c", "rd", "/s", "/q", r"C:\ok3dtemp"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
time.sleep(0.5)

with open(os.path.join(PKG, "_dlgopen.txt"), "wb") as f:
    f.write((PSD + "\r\n").encode("gbk"))

with open(os.path.join(PKG, "_dlgsave.txt"), "wb") as f:
    f.write((OUT_PSD + "\r\n").encode("gbk"))

print("=== 测试直接导出 PSD 自动触发切片缓存 ===")
proc = sp.Popen([os.path.join(PKG, "psdto3d101.exe")], cwd=PKG)
pid = proc.pid
hwnd = None
for _ in range(40):
    m = [x for x in win.windows(pid) if x[1] == "TForm1"]
    if m: hwnd = m[0][0]; break
    time.sleep(0.25)

time.sleep(1.0)
print("1. 载入 PSD (cmd 7)...")
win.command(hwnd, 7)
time.sleep(2.0)

print("2. 激活主窗体消息循环 (cmd 12/13)...")
win.command(hwnd, 12)
time.sleep(1.0)
win.command(hwnd, 13)
time.sleep(1.0)

print("3. ★ 直接执行导出 PSD (cmd 17)，后台自动触发静默切片渲染...")
t0 = time.time()
win.command(hwnd, 17)

for i in range(120):
    time.sleep(1.0)
    if os.path.exists(OUT_PSD) and os.path.getsize(OUT_PSD) > 1000000:
        prev = os.path.getsize(OUT_PSD)
        time.sleep(2.0)
        curr = os.path.getsize(OUT_PSD)
        if prev == curr and curr > 10000000:
            print(f"   [成功] 直接导出 PSD 完成: {curr:,} 字节，总耗时 {time.time()-t0:.1f} 秒！")
            break
    if (i + 1) % 10 == 0:
        sz = os.path.getsize(OUT_PSD) if os.path.exists(OUT_PSD) else 0
        temp_cnt = len(os.listdir(r"C:\ok3dtemp")) if os.path.exists(r"C:\ok3dtemp") else 0
        print(f"   [进行中 {i+1}s] ok3dtemp切片数={temp_cnt}, direct_test.psd 大小={sz:,} 字节")
else:
    print(f"   [失败] 导出 PSD 超时！当前大小: {os.path.getsize(OUT_PSD) if os.path.exists(OUT_PSD) else 0}")

alive = proc.poll() is None
print("进程存活:", alive)
sp.run(["taskkill", "/PID", str(pid), "/F"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)

if os.path.exists(OUT_PSD):
    sz = os.path.getsize(OUT_PSD)
    with open(OUT_PSD, "rb") as f: head = f.read(26)
    sig, ver, res, chan, h, w, depth, mode = struct.unpack(">4sH6sHIIHH", head)
    print("="*50)
    print("=== 最终产物校验 ===")
    print(f"文件大小: {sz:,} 字节")
    print(f"签名: {sig}, 尺寸: {w}x{h}, 通道: {chan}, 模式: {mode}")
    print("="*50)
    os.remove(OUT_PSD)
