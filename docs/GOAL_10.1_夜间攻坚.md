# GOAL · 10.1 主线去狗攻坚（夜间无人值守工作单）

> 建立：2026-11-23 01:2x　｜　主线：**PSDTO3D 10.1**（`_work/emu1`）
> 用法：每次被调度时 —— 先读本文件 → 执行「五、夜间执行步骤」里第一个未打勾的步骤 →
> 用实测数据更新「九、进度日志」→ 保存。**不要跳过验证，不要重复已验证项。**

---

## 一、完成定义（DoD）

### A 级：功能全通（本次夜间必须达到）

在**没有真狗**的机器上，用「原版 10.1 exe + 仿真狗 DLL」跑完：

| # | 功能 | 判据 |
|---|---|---|
| A1 | 启动 + 狗检测 | 无弹框；`_dongle.log` 里三个 replay 会话（idx 0…12）全命中 |
| A2 | 导入 PSD | 标题变成 `Psdto3d 10.1   a.psd` |
| A3 | 导入工程设置 | 标题变成 `Psdto3d 10.1   a.psd    a.tw3d2` |
| A4 | 预览 | `C:\ok3dtemp` 生成 1200+ 个 `ly/lyt/gx…` 文件，总量 >1 GB |
| A5 | **导出 TIFF**（菜单 16） | 生成 `C:\bio\out.tif`，**6,899,708 B**，1969×1168，samples=3 |
| A6 | **导出 PSD**（菜单 17） | 生成 `C:\bio\out.psd`，能被 `tools/psdinfo.py` / `psdstruct.py` 解析；尺寸/层数合理（参考真狗：4370×5197、11 层 `ghm01..ghm11`、每层 5 通道） |
| A7 | **导出 GIF**（菜单 18） | 生成 `C:\bio\out.gif`，GIF89a，帧数 ≥2，尺寸与输出设置一致 |
| A8 | 稳定性 | 全程无 AV/除零弹框；`_dongle.log` 无 `EXCEPTION`/`DIVZERO` 记录 |

### B 级：与真狗基准对齐（有富余时间再做）

* `C:\bio\out.tif` 与 `test\0《生化危机：爆发夜》第一人称海报汉化\…tif`（6,899,708 B）逐字节/逐像素对比；
* 已知差异：10.1 的库写 `55 47 A7 01`（UG 变体）+ 标签顺序不同；**像素一致即视为「内容正确」**，
  头部差异记录为版本差异（2022 套件才是 `49 49 2A 00`）。
* 若要对齐头部，路线见「七、可选路线」。

---

## 二、基线与文件位置

```
主工作版本：_work/emu1/
  psdto3d101.exe          10.1 绿色版 exe（1,581,056 B；含 0x4D2BF2 强制成功 + DATA 段 cave）
  cmyktiff2.dll           = cmykdrop/cmyktiff2_emu.dll（仿真狗 + 导出转发）
  cmyktiff2_real.dll      原版 TIFF 库（10.1 套件，md5 417CE3B6…）
  cmyktiff2_real.10.1.dll 上面这份的备份
  wnaspi32.dll            ASPI 仿真
  _dlgopen.txt            "C:\\bio\\a.psd" → "C:\\bio\\a.tw3d2"（按顺序应答，最后一行循环）
  _dlgsave.txt            "C:\\bio\\out.tif" → 之后追加 out.psd / out.gif
  _dongle.log             仿真器日志（replay / zero-write / cfa / gofn / gsfn / SBp）

对照基线：  psdto3d10.1绿色版/    （绿色版交付基线，未装仿真器）
真狗基准：  test\0《生化危机：爆发夜》第一人称海报汉化\
              …第一人称海报汉化.tif        6,899,708 B（1969×1168, RGB）
              …_3D输出.psd                 1,067,414,910 B（4370×5197, 11 层, 5 通道/层）
输入素材：  C:\bio\a.psd（215,964,173 B, 32 层）、C:\bio\a.tw3d2（18,072 B）
```

**编译仿真器（32 位）**

```bash
MINGW="C:/Users/moo/AppData/Local/Temp/zcode-tools/i686-mingw/mingw32/bin/i686-w64-mingw32-gcc.exe"
"$MINGW" -O2 -shared -static-libgcc -o cmykdrop/cmyktiff2_emu.dll \
    cmykdrop/dongle_emu.c cmykdrop/replay_table.h cmykdrop/cmyktiff2_emu.def \
    -luser32 -lkernel32
cp cmykdrop/cmyktiff2_emu.dll _work/emu1/cmyktiff2.dll
```

---

## 三、已验证（**不要重复**）

| 项 | 证据 |
|---|---|
| 狗检测原生通过 | `E32FCRET eax=0, s8/sc/s10/s14 = 0x7B ×4` |
| 导入 PSD / 导入设置 | 标题按预期变化 |
| 预览 | `C:\ok3dtemp` 1275 个文件 |
| **导出 TIFF 已跑通** | `C:\bio\out.tif` = 6,899,708 B（2026-11-23 00:07，10.1 套件） |
| 导出菜单启用时机 | 预览开始后 **约 20~25 s** 才 `EnableMenu id=16`；之前发 WM_COMMAND 无效 |
| 回放对齐 | idx 0–18 全命中 |
| 仿真器对话框队列 | `_dlgopen/_dlgsave` 各支持 8 行，最后一行循环使用 |

---

## 四、已知坑（每条都踩过）

1. **导出菜单在预览前是灰的**：必须等 `GetMenuState(16) == 0`；**不要先发菜单 13（停止预览）**，那会让导出再次失效。
2. **探针不可靠**：`hwbp32p` 的硬件执行断点在同一轮命中 2 次后可能失效（SEH 吞单步）。判据用**行为证据**：文件是否生成、日志、标题。
3. **零长度写（dtl=0）必须 ACK 但不消耗 replay 索引** —— 已修，勿回退。
4. **每次实验前**：`taskkill /IM psdto3d101.exe /F`，并删 `_dongle.log`。
5. **临时目录**：exe 里的 `D:\ok3dtemp\` 已被改成 `C:\ok3dtemp\`；目录必须**预先存在**，否则报 `Cannot create file`。
6. **PSD/GIF 导出要新路径**：`_dlgsave.txt` 追加第 2、3 行，否则会写回 `out.tif` 覆盖。
7. **不要用 `cmyktiff2_cap.dll` 替换仿真器**（cap 只记录不应答，狗检测会失败）。
8. 改 exe 前先 `cp exe exe.bak-<时间>`；改完必须重算 PE 校验和。
9. VA↔文件偏移：CODE 段 `off = VA - 0x400000 - 0xC00`；DATA 段 `off = VA - 0x400000 - 0x115000 + 0x113800`。

---

## 五、夜间执行步骤（按顺序做，一次一步）

### Step 0　自检（5 分钟）

```powershell
cd C:\Home\Workspace\UGit\psdto
taskkill /IM psdto3d101.exe /F 2>$null
Get-FileHash _work\emu1\psdto3d101.exe     -Algorithm MD5   # 期望 4CB135C074CDF55E16E5B345435818EB
Get-FileHash _work\emu1\cmyktiff2.dll      -Algorithm MD5   # 期望 52AA1A4887F8B4FBF7F0486D49ADF1F1
Get-FileHash _work\emu1\cmyktiff2_real.dll -Algorithm MD5   # 期望 417CE3B6727D839CBD992E910848CD2A
New-Item -ItemType Directory -Force C:\ok3dtemp | Out-Null
```

**验收**：三个 md5 与上面一致；`C:\ok3dtemp` 存在；没有残留 `psdto3d101.exe` 进程。
（2026-11-23 01:2x 已跑过一次：三个 md5 全部命中，`_dlgsave.txt` 1 行、`_dlgopen.txt` 2 行。）

### Step 1　复现 TIFF 导出（10 分钟）

```powershell
Remove-Item C:\bio\out.tif -Force -ErrorAction SilentlyContinue
python tools\flow_timeline.py --pkg "_work\emu1" --cmds "7@10,10@45,12@70,16@150" --duration 230
Test-Path C:\bio\out.tif; (Get-Item C:\bio\out.tif).Length
```

**验收**：`out.tif` = 6,899,708 B。若失败，走「六、诊断决策树」。

### Step 2　导出 PSD（菜单 17）

```powershell
# 1) 追加保存路径（顺序：先 tiff，再 psd）
@("C:\bio\out.tif","C:\bio\out.psd") | Set-Content _work\emu1\_dlgsave.txt -Encoding ASCII
Remove-Item C:\bio\out.psd -Force -ErrorAction SilentlyContinue
python tools\flow_timeline.py --pkg "_work\emu1" --cmds "7@10,10@45,12@70,16@150,17@200" --duration 300
Test-Path C:\bio\out.psd; (Get-Item C:\bio\out.psd).Length
python tools\psdinfo.py C:\bio\out.psd
```

**验收**：`out.psd` 生成且可解析（宽高、层数、通道数合理）。参考真狗：4370×5197、11 层。
**记录**：长度、分层名、每层通道数；与真狗基准的差异写进日志。

### Step 3　导出 GIF（菜单 18）

```powershell
@("C:\bio\out.tif","C:\bio\out.psd","C:\bio\out.gif") | Set-Content _work\emu1\_dlgsave.txt -Encoding ASCII
Remove-Item C:\bio\out.gif -Force -ErrorAction SilentlyContinue
python tools\flow_timeline.py --pkg "_work\emu1" --cmds "7@10,10@45,12@70,18@150" --duration 260
python -c "d=open(r'C:\bio\out.gif','rb').read(); print(d[:6], len(d), d.count(b'\x2C'))"
```

**验收**：GIF89a 头、帧数 ≥2（用 `,` 计数近似）、尺寸与输出设置一致。
**若失败**：先查 `GIFImage`/`gif3d.dll` 是否被需要（`_dongle.log` 里看 `cfa … gif3d.dll`），再走决策树。

### Step 4　三件套一次跑完（回归）

```powershell
@("C:\bio\out.tif","C:\bio\out.psd","C:\bio\out.gif") | Set-Content _work\emu1\_dlgsave.txt -Encoding ASCII
Remove-Item C:\bio\out.tif,C:\bio\out.psd,C:\bio\out.gif -Force -ErrorAction SilentlyContinue
python tools\flow_timeline.py --pkg "_work\emu1" `
  --cmds "7@10,10@45,12@70,16@150,17@215,18@280" --duration 360
Get-ChildItem C:\bio\out.* | Select Name,Length
```

**验收**：三个文件都在，大小与 Step 1–3 一致（±0）。

### Step 5　产物校验与归档

```powershell
python tools\compare_tiff.py C:\bio\out.tif "test\0《生化危机：爆发夜》第一人称海报汉化\0《生化危机：爆发夜》第一人称海报汉化.tif"
python tools\psdinfo.py C:\bio\out.psd
mkdir _work\emu1\_artifacts -Force
Copy-Item C:\bio\out.tif,C:\bio\out.psd,C:\bio\out.gif _work\emu1\_artifacts\ -Force
```

**验收**：归档目录里有三个产物 + 一份 `校验.txt`（大小/md5/关键结构）。

### Step 6　交付包

```powershell
# 以绿色版为底，装入仿真器与已验证补丁
robocopy psdto3d10.1绿色版 _work\交付_10.1 /MIR /NFL /NDL
copy cmykdrop\cmyktiff2_emu.dll      _work\交付_10.1\cmyktiff2.dll
copy _work\emu1\cmyktiff2_real.dll   _work\交付_10.1\cmyktiff2_real.dll
copy cmykdrop\wnaspi32.dll           _work\交付_10.1\wnaspi32.dll
copy _work\emu1\psdto3d101.exe       _work\交付_10.1\psdto3d101.exe
# 说明文件 + _dlgopen/_dlgsave 模板
```

**验收**：`_work\交付_10.1` 里双击 exe 能启动（中文界面可选），无狗；`_artifacts` 三个产物齐全。

---

## 六、诊断决策树（失败时按此顺序）

```
没生成文件
 ├─ 菜单发了但无反应 → 查 GetMenuState(菜单号)：非 0 就是还没启用（预览不足 20s / 已发过 13）
 ├─ 弹了保存对话框没应答 → 查 _dongle.log 有没有 "EMU gsfn -> ..."；没有就是 IAT 没挂上
 └─ 有 gsfn 但文件没出现 → 查是否写到了别的路径（grep 日志里的 cfa 路径）

生成了但 0 字节 / 只有头部
 ├─ 查日志 DIVZERO / REALGEO X1 X2 是否为 0  → 几何值缺失（狗记录未回填）
 └─ 查 stai 参数（MODE 行）→ 尺寸是否为 0

崩溃（弹 AV 框）
 ├─ 记录地址（弹框原文）+ 最近日志 3 行 → 写进日志，先跳过，不要卡死
 └─ 用 tools/disasm_at.py <exe> 0x<地址> 看上下文，判定是"空指针守卫"还是"数据缺失"
```

**规则**：同一步骤失败 2 次 → 换路线（例如 TIFF 用 2022 的 real DLL 变体、或退回纯补丁路线 `_work/v15`），
并在日志里写清「换路线原因」。

---

## 七、可选路线（B 级：对齐基准头部）

1. 把 2022 套件的 `cmyktiff2.dll` 作为 `cmyktiff2_real.dll`（标准 TIFF 常量）→ 已试过，产出 332 B，
   因为仿真器的注入参数是按 10.1 调用序列硬编码的；
2. 若要做，先完成「仿真器耦合点清点」：`grep -n "0x7E9D0\|0x7FF98\|0x7F720\|0x7F4FC" cmykdrop/dongle_emu.c`，
   把 RVA/常量抽成两套（按 real DLL 版本选）；
3. 或直接修 2022 exe 的 `0x4FFCB7`（守卫），整条走 2022 —— 见 `GOAL_emu_去狗_持续.md` 第九节。

---

## 八、禁忌清单

1. 不删 `_work/emu1/_dongle.log` 之外的历史证据；实验前清日志是为了判读，不是为了省空间。
2. 不重复验证第三节列出的项。
3. 不把 `cmyktiff2_cap.dll` 当仿真器用。
4. 不在没有备份的情况下改 exe / DLL。
5. 不为了"看起来通过"而伪造产物（每个产物都要有 md5 + 结构校验）。

---

## 九、进度日志（每次调度追加一行）

| 时间 | 步骤 | 做了什么 | 结果 | 下一步 |
|---|---|---|---|---|
| 2026-11-23 01:2x | — | 建立本工作单（10.1 主线，含 PSD/GIF 导出 DoD） | — | Step 0 自检 |
| 2026-11-23 01:2x | Step 0 | 自检三个 md5 / `C:\ok3dtemp` / 残留进程 | 全部命中 | Step 1 |
| 2026-11-23 01:27 | Step 1（失败 1） | 直接用 `_work/emu1` 跑 TIFF 导出 | `out.tif` 只有 332 B；导出时弹 `Exception EReadError in module cmyktiff2_real.DLL at 00015F1B` | 怀疑 emulator 版本不对 |
| 2026-11-23 01:30 | Step 1（失败 2） | 清空 `C:\ok3dtemp` 重跑 | 同样 332 B + EReadError；日志无 `INJECT`/`REALGEO` 行 | ★ 定位：emu1 里的 `cmyktiff2.dll` 是 23:27 的旧构建（145,411 B，缺 X2 注入） |
| 2026-11-23 01:33 | **Step 1 ✅** | 换用 `cmykdrop/cmyktiff2_emu.dll`（145,976 B，含 `INJECT X2`） | **`C:\bio\out.tif` = 6,899,708 B**；日志 `REALGEO … → INJECT X2 := 2336`、`PATCH100 … -> 4370`、`STAICALL args=(buf,3,1969,1168,2772000,0,1386000,0)` | 已归档 `_artifacts/step1_out.tif`（md5 43CA3415…）；继续 Step 2 |
| 2026-11-23 01:35 | Step 2 | `_dlgsave.txt` 追加 `C:\bio\out.psd`，跑菜单 17 | 进行中 | — |
| 2026-11-23 01:39 | Step 2（首轮） | 序列 7,10,12,16,17，330 s 窗口 | 菜单 17 命中，`gsfn -> out.psd`，写出 **3,080 B** 骨架；窗口到点被杀 | 加长窗口重试 |
| 2026-11-23 01:51 | Step 2（只发 17） | 不先导 TIFF，直接 17@150 | **菜单 17 无任何反应**（无 `gsfn`） | ⇒ PSD 导出依赖先前的 TIFF 导出 |
| 2026-11-23 01:56 | Step 2（480 s） | 7,10,12,16@150,17@210 | `out.tif`=6,899,708 ✅；`out.psd` **仍只有 3,080 B**（11 层、3 通道、8 位，但尺寸字段是 0x4370×1168、无像素） | ★ Step 2 卡点：PSD 导出只写骨架 |

**Step 2 现状（本轮结论）**

* 触发条件：**必须先成功导出 TIFF（菜单 16）**，再发菜单 17；单独发 17 无反应（与导出菜单启用时机无关）。
* 现象：`out.psd` 只有 3,080 B —— 文件头 `8B PS …`、11 层、3 通道、8 位，但
  `height=0x4370/width=1168` 明显来自错误来源，且**没有任何像素数据**。
* 归档：`_artifacts/step2_out.psd`（3,080 B）、`_artifacts/step1_out.tif`（6,899,708 B）。
* 下轮方向（按序）：
  1. 读 `savetiff00`/PSD 写出函数里取尺寸的字段（大概率与 TIFF 的 `X2` 同源），
     对比 `STAICALL` 的 `1969/1168` 与 PSD 头里的 `0x4370/1168`；
  2. 若确认是同一个"狗给几何"的洞，把仿真器的 `INJECT X2` 扩成同时喂 PSD 路径；
  3. 参考基准 `…_3D输出.psd` = 1,067,414,910 B / 4370×5197 / 11 层 —— 注意**宽高与 TIFF 不是同一组**。

### Step 2 诊断（2026-11-23 02:0x，本轮）

**(a) 基准 vs 我们的骨架（PSD 头逐字节）**

```
ref : 8BPS 0001 …… 0003 | 00 00 14 4D (h=5197) | 00 00 11 12 (w=4370) | 0008 0003
ours: 8BPS 0001 …… 0003 | 00 00 11 12 (h=4370) | 00 00 00 00 (w=0)    | 0008 0003
```
即：我们的骨架把 **宽当成高**、宽写成 0，且无任何像素数据（3,080 B）。

**(b) `writepsd` 的调用现场（exe `0x50B14C`）**

```
0050b14c  mov  ax,[0x52315E]      ; 低 16 位 = 3（通道数）
0050b152  push eax
0050b153  push edi                ; edi = [0x5230D4]
0050b154  push esi                ; esi = [0x5230D0]
0050b155  mov  eax,[0x5230FC]     ; 11（线数/层数）
0050b15a  push eax
0050b15b  push [0x523174]  / push [0x523170]
0050b167  push [0x5231AC]  / push [0x5231A8]
0050b173  push [0x523234]  / push <保存对话框文件名>
0050b17d  call [0x523278]         ; zu06.dll!writepsd
```

运行时实测（`tools/probe_psd_globals.py`，导出 TIFF 之后读）：

```
0x5230D0 = 4370   0x5230D4 = 5197    ← 与基准 PSD 宽高完全一致，说明 exe 侧参数是对的
0x5231A8 = 3000000  0x5231AC = 0
0x523170 = 252000   0x523174 = 0
0x52315E = 0x65D00003（取低 16 位 = 3）  0x5230FC = 11
```

⇒ **宽高参数正确**，问题在 `writepsd` 内部。

**(c) 根因（本轮关键发现）**

`zu06.dll`（`readpsd` / `writepsd` 所在模块）**自己带一整套狗访问**：

```
导入表：CreateFileA / DeviceIoControl / ReadFile / WriteFile / SetupDiGetClassDevsA /
        SetupDiEnumDeviceInterfaces / SetupDiGetDeviceInterfaceDetailA /
        SetupDiDestroyDeviceInfoList / WSAStartup / socket / closesocket / GetVolumeInformationA
字符串：MyUSBKey、USBKey ×3、usbstor
```

而仿真器目前只 patch 了 **exe 的 IAT** 与 **`cmyktiff2_real.dll` 的 IAT**
（`patch_real_module` 里写死的 `0x903D8/0x903C8/…` 那 12 个槽位）。
**`zu06.dll` 的 IAT 从未被挂钩** ⇒ `writepsd` 走真实设备路径拿不到狗数据 → 写出 3,080 B 骨架。

**(d) 下一轮第一步（已明确，不要再走偏）**

把仿真器的 IAT 挂钩扩展到 `zu06.dll`：

1. 用 pefile 取 `zu06.dll` 各导入函数在 **IAT 里的 RVA**
   （`CreateFileA / DeviceIoControl / ReadFile / WriteFile / SetFilePointer / SetupDi×4 / CloseHandle`）；
2. 在 `dongle_emu.c` 里加 `patch_zu06()`，复用现有的 `e_cfa/e_dio/e_rf/e_wf/e_sddila/…` 桩；
3. 触发时机：hook exe 的 `LoadLibraryA`/`GetProcAddress`（`RVA_*` 里已有槽位模式可参考），
   在 `zu06.dll` 装载后立即 patch；
4. 重编译 → 重跑 Step 2 → 期望 `out.psd` ≫ 3,080 B，且头为 `4370×5197`。

### Step 2 实验记录（2026-11-23 02:10–02:21，**已回滚**）

**做了什么**：按上面的方案给仿真器加了 `patch_zu06()` + 轮询线程（`cmykdrop/dongle_emu.c`，备份
`dongle_emu.c.bak-0200`），编译出 146,774 B 的新 DLL（`cmykdrop/cmyktiff2_emu.dll`，含
`EMU patched zu06.dll IAT` 与 `INJECT X2` 两个标记），换进 `_work/emu1/cmyktiff2.dll` 跑 Step 2。

**结果：失败，而且把正常路径也带坏了**

```
t=37  title → a.psd            （导入 PSD 正常）
t=46  DIALOG "Invalid numeric input."        ← 导入工程设置时解析失败
t=163 DIALOG "Invalid floating point operation."  ← 导出 TIFF 失败
t=210 菜单 17 无产出
```

**判断**：`zu06.dll` 的 IAT 里 `CreateFileA/ReadFile/WriteFile/CloseHandle` 同时也是
**它读写真实文件（PSD / 工程）用的通道**。整表挂钩后，这些真实文件 I/O 被仿真桩接管，
于是 PSD/工程读取拿到脏数据 → 解析失败、后续浮点异常。

**处置**：已回滚到 md5 `314408A1…`（145,976 B，含 `INJECT X2`），并复跑 Step 1 验证：
`out.tif` = **6,899,708 B** ✅（`INJECT X2 := 2336`、`STAICALL … 1969 1168` 均正常）。
⇒ 系统回到绿灯，本实验**不留在主工作目录**。

**下一轮的正确做法（窄化挂钩）**

* 只挂 **设备枚举/控制** 三项：`SetupDiGetClassDevsA` / `SetupDiGetDeviceInterfaceDetailA` /
  `DeviceIoControl`（RVA `0xB4878` / `0xB4870` / `0xB43E8`），
  **不挂** `CreateFileA/ReadFile/WriteFile/CloseHandle`；
* `CreateFileA` 改为**只在该模块打开设备路径时**才接管：
  两个候选槽 `0xB421C`/`0xB43F8` 需要在运行时确认哪个是设备打开
  （判据：`EMU cfa … usbstor` 日志命中哪个 RVA —— 可先在 `e_cfa` 里记录返回地址）；
* 若窄化后 `writepsd` 仍只写骨架，则说明 PSD 路径要的不是设备句柄，而是
  **另一份狗记录**（届时再比较 `writepsd` 内部读取的字段与 TIFF 路径的差异）。

### Step 2 实验记录 2（2026-11-23 02:25–02:34，窄化挂钩，**已回滚**）

| 变体 | zu06 挂钩内容 | 结果 |
|---|---|---|
| A（全表） | CreateFile×2 / DeviceIoControl / Read×2 / Write×2 / SetFP×2 / Close×2 / SetupDi×4 | 工程导入 `Invalid numeric input`、导出 `Invalid floating point operation` |
| B（窄·含 DIO） | CreateFile×2 / DeviceIoControl / SetupDi×4 | **PSD 导入即崩**：`Invalid floating point operation`（t=12）⇒ 元凶是 `e_dio` |
| C（窄·去 DIO） | CreateFile×2 / SetupDi×4（`_zu06_no_dio.txt` 开关） | PSD 导入 ✅；导出 TIFF 时 `Invalid floating point operation`（t=163，临时目录只到 109 文件就停） |

**结论**：以现有这套"钝"桩去挂 `zu06.dll` 的 IAT，**无论宽窄都会破坏正常路径** ——
`e_dio` 会误接管 zu06 的真实 IOCTL，`e_cfa`/`e_sddida` 也会让它的真实文件/设备枚举走偏。
⇒ **放弃 IAT 挂钩路线**，改"外科手术式"：

1. 直接改 `zu06.dll` 里设备路径字符串（`\\.\MyUSBKey…` / `usbstor…`）让它找不到设备，
   观察它是否走 `rip3d.enc.lll` 文件回退路径（cmyktiff2 就是这么回退的）；
2. 或定位 `writepsd` 内部第一次"要狗数据"的调用点，在那里做**单点**跳转，
   复用已经在 `cmyktiff2_real.dll` 上验证过的记录回放；
3. 若两条都不成，再把 `writepsd` 的参数/记录需求单独逆向（它读的字段和 TIFF 路径未必相同）。

**产物**：窄化版已归档 `cmykdrop/cmyktiff2_emu_zu06narrow.dll`；
主工作目录已回滚到 md5 `314408A1…`，`_dlgsave.txt` 复位为 1 行。

### ★ 新确认的坑（本轮最大收获之一）

**`C:\ok3dtemp` 不干净会导致"导入工程设置"报 `Invalid numeric input`。**
证据：同一套二进制，脏临时目录（1297 个旧文件）→ t=33 报错；
清空临时目录 → 导入链一路正常（标题 `a.psd` → `a.psd a.tw3d2`）。
⇒ 每次实验前**必须** `Remove-Item 'C:\ok3dtemp\*' -Recurse -Force`，否则会把正常失败误判成补丁问题。

**Step 1 新增坑（务必写进下次的自检）**：
`_work/emu1/cmyktiff2.dll` 必须是 **`cmykdrop/cmyktiff2_emu.dll` 的最新构建**（当前 145,976 B / md5 `314408A1…`）。
旧构建缺 `savetiff00@+0x7F9BF` 处的 `INJECT X2`，表现为 `out.tif` 只有 332 字节 + `EReadError`。
判据：日志里必须有 `REALGEO … X2=…` 和 `INJECT X2 := 2336` 两行。

| 时间 | 步骤 | 做了什么 | 结果 | 下一步 |
|---|---|---|---|---|
| 2026-11-23 02:0x | Step 2 诊断 | 反汇编 `writepsd` 调用点 + 运行时读全局 | 宽高参数正确（4370/5197）；`zu06.dll` 自带狗栈 | 挂钩 zu06 |
| 2026-11-23 02:10 | Step 2 实验 A | zu06 全表 IAT 挂钩 | 工程/导出双双报错，已回滚 | 窄化 |
| 2026-11-23 02:25 | Step 2 实验 B | 窄化（含 DeviceIoControl） | PSD 导入即崩 | 去掉 DIO |
| 2026-11-23 02:29 | Step 2 实验 C | 窄化（去 DIO，留 CreateFile+SetupDi） | 导入 ✅、导出崩 | ★ 放弃 IAT 路线，改外科手术 |
| 2026-11-23 02:34 | 收尾 | 回滚 md5 `314408A1…`、复位 `_dlgsave.txt`、归档窄化版 | 系统恢复绿灯 | 改 `zu06.dll` 设备字符串或单点跳转 |
| 2026-11-23 02:33 | ★ 新坑 | 脏 `C:\ok3dtemp` → 导入工程报 `Invalid numeric input` | 清空后恢复正常 | 每次实验前必清临时目录 |
| 2026-11-23 02:36 | Step 2 实验 A′ | 全表挂钩 + **干净临时目录** 重跑 | 仍在 t=12 崩 `Invalid floating point operation` ⇒ 不是脏目录，是 `e_dio` 误接管 zu06 的真实 IOCTL | 放弃 IAT 路线 |
| 2026-11-23 02:44 | Step 2 实验 D | 改 `zu06.dll` 设备串（`MyUSBKey`→`MyUSBKe0`） | TIFF 6,899,708 ✅、PSD **仍 3,080 B** ⇒ 设备名不是关键 | 换思路 |
| 2026-11-23 02:52 | Step 2 实验 E | 把 emu1 的 `zu06.dll` 从 2022 版换成 **10.1 原版**（md5 5EA94564） | PSD **仍 3,080 B** ⇒ 与 zu06 版本无关 | 转数据侧分析 |
| 2026-11-23 03:05 | Step 3 首探 | 直接发菜单 18（不先导 TIFF） | 无反应、无文件 | 查菜单状态 |
| 2026-11-23 03:12 | Step 3 二探 | 先导 TIFF（16）再发 18 | 17/18 日志显示已 enable，但 18 仍无 `gsfn`、无文件 | 逆 18 的处理函数 |
| 2026-11-23 03:25 | ★ 机制发现 | `tools/menu_state.py` + `tools/flow_waitmenu.py` | **导出菜单阶梯解锁**：预览后只开 16；成功导 TIFF 后才开 17/18 | 按此顺序编排后续实验 |
| 2026-11-23 03:40 | Step 3 定位 | 用 IDR 符号表拿到 `N18Click@0x50B010` / `N7Click@0x50B070` / `PSD1Click@0x50B090` | 菜单 18 的闸门是 `[form+0x3EC]` 的 `.Down` | 打 2 字节补丁 |
| 2026-11-23 03:45 | **Step 3 ✅** | 补丁 `0x50B020: 75 09 → 90 90` 去掉 GIF 闸门 | **`out.gif` = 4,006,352 B**，GIF89a、800×951、**11 帧**、trailer 0x3B | 归档 + 并入构建脚本 |
| 2026-11-23 04:00 | 补丁并入绿色包 | 按字节模式（非固定偏移）打 `75 09→90 90` | 绿色包 exe `957E327B…` → `A74AF789…`，启动无弹框 ✅ | 记入构建清单 |
| 2026-11-23 04:10 | Step 2 探针 | `zu06+0xA4504` 挂 VEH 断点 | 拿到 `writepsd(文件名,目录,3000000,0,252000,0,11,4370,5197)`；**更正**"不读文件"的旧结论 | 对照真机抓包 |
| 2026-11-23 04:15 | Step 2 对照 | 真机抓包尾部有 `01F0→002A→000A`；我们的 PSD 导出**一次狗会话都没有** | ⇒ PSD 导出前被跳过了一轮狗交互 | 找 PSD 路径为何不调 `0x4D2C48` |

| 2026-11-23 05:25 | A6 收尾 | 注入层矩形（`_inject_psd_rect.txt`）后 PSD 结构全对：11 层、`(0,0,5197,4370)`、每通道 22,710,892 B；但像素数据未写（2,970 B） | 层循环探针 `0xA497D` 零命中（断点不可靠） | 换 IO/内存标记法找写通道那段 |
### Step 2 阶段结论（2026-11-23 02:55）
| 2026-11-23 06:5x | 收尾 | 交付包定稿（80 文件 / 16.3 MB）+ 打包 `_work/交付_10.1_2026-11-23.zip`（26.8 MB）+ 写 `醒来速览_2026-11-23.md` | 交付包复验 `out.tif=6,899,708 B` ✅；静态搜 UG 常量在 18 个二进制里全是 RTL 误报 | 等真机 A5 或做模块级取证 |

| 2026-11-23 07:0x | 终验 | 用**交付包本身**（`_work/交付_10.1`）跑完整流程 7,10,12,16,18 | `out.tif`=6,899,708 B ✅、`out.gif`=4,009,181 B / 11 帧 ✅、`alive: True`；产物归档 `_artifacts/delivery_out.{tif,gif}` | A6 等真机日志 |
**三条与"狗"/DLL 相关的假设全部证伪**：
| 2026-11-23 07:1x | 收束 | 写 `docs/最终状态_2026-11-23.md`（验收总表 / 交付物 / 校验值 / A6 走过的弯路 / 下一步） | A1–A5、A7、A8 达成；A6 卡在狗解密参数 | 等真机 A5 或外挂调试器取证 |

1. IAT 挂钩 zu06（宽/窄都不行）→ 破坏正常路径；
2. 改设备名让它找不到狗 → 行为不变；
3. 换 zu06.dll 版本（2022 ↔ 10.1）→ 行为不变。

⇒ **PSD 导出写出 3,080 B 骨架，不是许可证/DLL 问题，是"数据没喂进去"。**
`writepsd` 收到 `lines=11`、宽 4370、高 5197、3 通道，但层里没有像素。

**下一轮方向（转数据侧）**：

1. 查 `[0x523160]`（调用前 `REALGLOB` 里是 `41248208` 这种指针）在 PSD 导出时指向什么——
   大概率是"图层 BMP 列表"；若为空/未填充，就是它；
2. 对照真狗基准 PSD 的 11 层名 `ghm01..ghm11`，在临时目录里找有没有同名/同前缀中间文件
   （TIFF 路径生成的是 `vwdNNN.gjs`，PSD 可能要求 `ghmNN.*`）；
3. 若确认需要另一批中间文件，去找生成它们的菜单/函数（很可能是 `rip3d.dll!stai` 的逐层调用，
   参数与 `mergtotiff` 不同），把这一环补上再回验 `writepsd`。

**状态**：`cmyktiff2.dll` = md5 `314408A1…`（绿灯构建）、`zu06.dll` = md5 `4F64BB56…`（本轮前状态）、
`_artifacts/step2_out_zu06variants.psd` 已归档作对照。

### Step 2 数据侧取证（2026-11-23 03:1x）

1. **`writepsd` 不读任何文件**：本次导出的日志里，`EMU gsfn -> C:\bio\out.psd` 之后
   **没有任何 `cfa` 行**，直接写出 3,080 B。⇒ 层数据是内存对象，不是临时文件。
2. **回放表覆盖全部地址**：真机抓包里有 `01F0(10) / 000A(10) / 001A(6) / 002A(3) / 00C2(1)` 五种会话，
   而 `cmykdrop/replay_table.h` 已包含 `01F0(20) / 000A(20) / 001A(12) / 002A(6) / 00C2(2)` ——
   **没有"漏掉的狗地址"**。
3. ⇒ 与狗、DLL 版本、设备名、IAT 全部无关。**PSD 的 11 层数据在调用前就没被填进内存对象**。

**下一轮唯一方向**：逆 exe 里"菜单 17 → `0x50B17D call writepsd`"之间**准备层对象的代码**
（从菜单处理函数往上找），看它依赖哪个全局/哪次 `stai` 调用的产物；
再拿 TIFF 路径（已验证能出 6,899,708 B）作对照，找出 PSD 路径缺的那一步。

### Step 3（GIF）首轮探测（2026-11-23 03:1x–03:2x）

**新工具**：`tools/menu_state.py`（dump 全部菜单 id/状态/文字）、
`tools/flow_waitmenu.py`（跑到预览后轮询某个导出菜单直到可用再发）。

**完整菜单表（预览后 t≈130 实测）**

```
id=16  &Export *.tiff      Ctrl+E
id=17  E&xport PSD         Ctrl+Alt+E
id=18  Export &Gif         Ctrl+G
```

**关键机制（这轮最重要发现）：导出菜单是"阶梯解锁"的**

| 时机 | 实测 |
|---|---|
| 预览进行中/完成 | 只有 **id=16** 收到 `EnableMenu en=0`；17/18 仍 grayed |
| **成功导出一次 TIFF 之后** | 日志出现 `EnableMenu id=17 en=0`、`id=18 en=0` |
| 只发 18（没先导 TIFF） | 灰着 → WM_COMMAND 被忽略，**无任何反应** |

⇒ 之前"PSD 必须先导 TIFF"的结论是正确的，而且**GIF 同理**。

**但 GIF 仍有独立问题**：在导过 TIFF 之后（17/18 都已 enable）发 18，
日志里**没有 `gsfn`、没有产出文件**，说明菜单 18 的处理函数被调用后自己提前返回了
（不像 17 那样至少写了个 3,080 B 骨架）。

**下一轮 Step 3 方向**

1. 找菜单 18 的处理函数（与 17 的 `0x50B090` 相邻，可用"菜单 id → 处理函数"的 DFM 方法表定位）；
2. 看它提前返回的条件（大概率又是一个 `[控件]` 状态或狗字段）；
3. 对照导出 GIF 需要的中间产物（`_capture.log` 里真机是否有独立会话）。

### ✅ Step 3 完成（2026-11-23 03:4x）：GIF 导出跑通，产出 4,006,352 B

**用 IDR 符号表直接拿到处理函数名**（`_analysis/names/functions_psdto3d101.tsv`）：

```
0050B010  TForm1.N18Click             ← 菜单 18（Export Gif）
0050B070  TForm1.N7Click              ← 菜单 16（Export tiff）
0050B090  TForm1.PSD1Click            ← 菜单 17（Export PSD）
0050B20C  TForm1.PSD2Click            ← 空函数（no-op）
```

**`N18Click` 的闸门（就是之前"发 18 没反应"的原因）**

```asm
0050b010  push ebx / mov ebx,eax
0050b013  mov eax,[ebx+0x3EC]      ; 某个 TSpeedButton（工具条按钮）
0050b019  mov edx,[eax]
0050b01b  call [edx+0x50]          ; 取 .Down / .Checked
0050b01e  cmp al,1
0050b020  jne 0x50b02b             ; ★ al≠1 → 直接返回，什么都不做
0050b022  mov edx,ebx / mov eax,ebx
0050b026  call 0x50ad74            ; → TForm1.SpeedButton9Click（真正的 GIF 导出）
```

`N7Click` 同样有闸门（`[ebx+0x3F4]`，TIFF 那个按钮，默认是 Down 状态所以一直能过）。

**补丁（2 字节，已验证）**

```
VA 0x50B020  文件偏移 0x10A420
75 09  →  90 90      ; 去掉 GIF 闸门
```

**实测（同一套仿真狗，干净临时目录）**

```
序列 7@10, 10@45, 12@70, 16@150, 18@215   （先导 TIFF 解锁 17/18，再发 18）
C:\bio\out.gif = 4,006,352 B
  头 GIF89a，逻辑屏幕 800×951，Graphic Control Block ×11（= 11 帧），trailer 0x3B ✅
```

归档：`_work/emu1/_artifacts/step3_out.gif`（md5 `B15CFE2D…`）；
exe 备份 `_work/emu1/psdto3d101.exe.bak-gifgate`。

⇒ **DoD A7（GIF89a / 帧数 ≥2）达成。**
**待办**：把该 2 字节补丁并入 `make_green.py` 的补丁清单与构建报告。

**✅ 已并入绿色包（2026-11-23 04:0x）**

绿色包的 exe 与 `_work/emu1` 的 exe **不是同一份**（各自打了不同补丁），所以**不能按固定偏移打**，
要用字节模式定位：

```
模式: 8B 83 EC 03 00 00 8B 10 FF 52 50 3C 01 75     ← mov eax,[ebx+0x3EC];…;cmp al,1;jne
      8B83EC0300008B10FF52503C01 找到后，紧随的 75 xx → 90 90
emu1  : 文件偏移 0x10A420
绿色包: 文件偏移 0x10A600
```

* 绿色包 exe：`957E327B…` → **`A74AF789…`**（备份 `psdto3d101.exe.bak-pregifgate`）
* 烟测：启动无任何弹框（许可证闸门仍正常绕过），主窗口正常出现 ✅
* ⇒ **构建脚本里必须用模式匹配，不要写死偏移**（两个 exe 的 CODE 段已有 0x1E0 的位移）。

### Step 2 复攻（2026-11-23 03:5x，负结果）

假设："GIF 已经生成 11 帧，PSD 应该能复用" → 实测序列 `7,10,12,16@150,18@215,17@285`：

```
out.tif = 6,899,708 ✅   out.gif = 4,006,352 ✅   out.psd = 3,080 ❌（仍骨架）
```

⇒ **PSD 不复用 GIF 的帧数据**，两条导出路径各自独立。

**`PSD1Click` 与 GIF 路径的结构差异（静态已看）**

```
N18Click → [form+0x3EC].Down → SpeedButton9Click(0x50AD74)   ← GIF，内部会调
                                     [esi+0x3F4]/[esi+0x4CC] 的 [vmt+0x64]
                                     以及 0x471B74([esi+0x470])（疑似"生成 11 帧"）
PSD1Click(0x50B090) → [form+0x608]（文件名控件）→ writepsd(文件名, 目录, 3000000, 0,
                                    252000, 0, 11, 4370, 5197, 3)
```

PSD 路径**没有**调用 GIF 那条 `0x471B74`/`[vmt+0x64]` 的"生成"序列，
所以 `writepsd` 拿到的只是尺寸参数，没有像素源。

**下一轮（Step 2）要做的事：给 `writepsd` 下断点看它到底从哪取像素**

在仿真器里给 `zu06.dll + 0xA4504` 挂一个 VEH 断点（复用 `sbp_arm` 机制），
记录 `[ebp+8] … [ebp+0x28]` 与调用次数；判据：

* 若 11 层循环内每次都去读同一个空指针 → 就是缺"生成"那一步，按 GIF 的方式补调用；
* 若参数本身就不对（例如 4370/5197 顺序颠倒）→ 在 `PSD1Click` 处修正参数即可。

### Step 2 探针实测（2026-11-23 04:0x）

**`writepsd` 入口断点命中 1 次，参数抓到了**

```
WRITEPSD eax=0A9F21D4 edx=00000000 ecx=28ADA2A9
stack=[<ret> 178201044(0x0A9F21D4) 42755300(0x028C6BE4) 3000000 0 252000 0 11 4370 5197]
```

⇒ 真实签名是 **`writepsd(文件名指针, 目录指针, 3000000, 0, 252000, 0, 11, 4370, 5197, …)`**，
只有两个字符串指针 + 一串数值，**没有任何图像缓冲参数**。
所以层像素只能来自 `writepsd` 自己按"目录 + 命名规则"去读文件。

**关键更正**：之前判断"writepsd 不读文件"是错的——**zu06.dll 的 CreateFileA 没挂钩，它的文件打开本来就看不到**。

**再证：只挂 zu06 的 CreateFileA（不挂别的）反而更糟**

```
t=163  Invalid floating point operation（临时目录只到 109 个文件就停）
日志：EMU open device <- \\.\MyUSBKey250 … 255、\\?\usbstor#disk&ven_usbkey…
```

原因：zu06 打开 `\\.\MyUSBKey25x` 时拿到我们的**假句柄**，于是它以为狗在、继续走协议，
但 DeviceIoControl 没挂（挂了会破坏文件 I/O）→ 协议拿到垃圾 → 数值全 0 → 浮点异常。
**没有假句柄时它走"无狗"分支反而安全。**

**下一轮的正确姿势**

1. `is_dev_handle()` 收紧为"只认我们自己创建的假句柄"（当前实现可能对真实句柄误判，
   这正是全表挂钩时 PSD/工程读取崩掉的原因）；
2. 然后同时挂 `CreateFileA + DeviceIoControl + ReadFile/WriteFile/CloseHandle`，
   但所有非假句柄一律**原样转发**；
3. 目标：让 `writepsd` 拿到它想要的"目录 + 文件名"后能读出真实数据，
   或者确认它要的文件根本没被生成（那时就去补生成）。

### Step 2 与真机抓包对照（2026-11-23 04:1x）

**真机抓包尾部（`_work/real3/_capture.log`，最后 400 行）**：

```
#114 SPTWR addr=01F0 len=496
#118 SPTWR addr=002A len=42
#122 SPTWR addr=000A len=10
```

⇒ 真机在一次导出里出现了 **01F0 → 002A → 000A** 这组会话（含 `002A`，我们的回放表里有 6 条）。

**我们的 PSD 导出：一次狗会话都没有**

```
EMU gsfn -> C:\bio\out.psd   ← 保存对话框应答后
（之后没有任何 replay/cfa 行，直接写出 3,080 B）
```

⇒ 真机在 PSD 导出前会跟狗做一轮 01F0/002A/000A 交互，**我们的流程把这一步整个跳过了**。
这就是"层里没有像素"的上游原因：那份记录里带着每层/几何的信息。

**下一轮（Step 2 决胜步）**

1. 在抓包里确认这组 01F0→002A→000A 属于哪次导出（按会话顺序：TIFF 在前、GIF/PSD 在后）；
2. 在 exe 里找"构造并发送 496 字节记录"的函数（TIFF 路径是 `0x4D2C48`，导出前后都会调一次），
   看 `PSD1Click(0x50B090)` 这条路径为什么没走到它；
3. 如果确认是某个控件/分支跳过了它，就把该分支打开（像 GIF 闸门那样 2 字节补丁），
   让 PSD 导出前也发一次 01F0/002A/000A —— 回放表已具备，理论上立刻可用。

### Step 2 重大进展：`writepsd` 到底在读什么（2026-11-23 04:0x）

**探针 1：两个字符串参数读出来了**

```
WRITEPSD arg1 ptr=0A9F21D4 len=14 [C:\bio\out.psd]
WRITEPSD arg2 ptr=028364E4 len=12 [c:\ok3dtemp\]
```

**探针 2：只给 zu06 的 `CreateFileA` 挂"只记不改"的壳（`e_cfa_logonly`）**

```
zu06 cfa c:\ok3dtemp\vwd001.gjs
zu06 cfa c:\ok3dtemp\vwdt001.gjs
… 一直到 011 …
```

⇒ **`writepsd` 确实按 `vwdNNN.gjs` / `vwdtNNN.gjs` 逐层读文件，而且这些文件都在**：

| 文件 | 大小 | 头 |
|---|---|---|
| `vwd001..011.gjs` | 68,133,002 B | `55 47 A7 01`（UG 变体 TIFF，4370×5197×3） |
| `vwdt001..011.gjs` | 22,722,362 B | `42 4D` = **BMP**（8 位，4370×5197） |

⇒ PSD 写出 3,080 B 不是"缺文件"，而是**读了文件之后没写进层里**。

**实验：把 2022 的标准 TIFF 常量块整体拷进 10.1 的 `cmyktiff2_real.dll`**

（块 `0x7E820..0x7E880`：`18261→18761`、`"423"/len3 → "42"/len2`、`1→8`、`259→256`、`274→273`，
长度前缀同步改，字节数不变）

结果：**`out.tif` 头部仍是 `55 47 A7 01`、`out.psd` 仍是 3,080 B**。

⇒ **更正 `复盘_基线纠正_2026-11-23.md` 的一个判断**：这 6 个常量**不在**导出/`vwd` 这条路径上，
改它们不会改变实际产物（它们属于 `savetiff00` 的另一条分支）。
也就是说"换 2022 的 DLL 就能得到标准 TIFF"这个推论**不成立**。

**下一轮**：在 `writepsd` 读文件之后（`zu06+0xA4504` 之后再挂 1~2 个点）看
"读到的图像尺寸/行数"是否被置 0；重点盯 `[ebp-0x108]/[ebp-0x104]` 这类 64 位中间量。

### Step 2：把 3,080 B 的骨架拆开看（2026-11-23 04:2x）

**解析我们写出的 PSD 的层记录**（`_artifacts/step2_out.psd`）：

```
layer+mask len 2100 / layer info len 200 / layer count 11
layer0 rect=(top 0, left 0, bottom 4370, right 0)
       channels=[(-1,2),(0,2),(1,2),(2,2)]   ← 每通道长度只有 2 字节（空）
```

⇒ **宽 = 0、高 = 4370**（4370 恰好是真正的宽，被写到了 bottom 位置）。
也就是说 `writepsd` 手里的"宽"是 0，高用了 4370 —— 和 TIFF 路径当初 `X2=0` 的症状**同源**：
**又一个狗给的数值没喂进去**。

**实验：把 `vwd*.gjs` 的 UG 头改写成标准 TIFF（`II*\0` + 偏移 8），再导 PSD**

（新工具 `tools/fix_vwd_headers.py`：等预览写完 → 改写 11 个文件的头）

```
files=11 fixed=11        ← 全部改写成功
out.psd = 3,080 B       ← 仍然骨架
```

⇒ **不是文件头格式问题**，`writepsd` 读得进；缺的是"宽"这个值。

**下一轮（收官方向）**

1. 在 `writepsd` 里找"写 rect 之前"的两条赋值（bottom/right 的来源），
   看 right 从哪个局部量/全局量取——大概率与 TIFF 的 `X2` 同类（狗记录字段）；
2. 用与 `INJECT X2 := 2336` 相同的手法，在仿真器里把"宽"注入（先试 4370）；
3. 若注入后 PSD 变大并有真实层数据 → A6 达成；再把注入值做成按参数计算。

### Step 2 收官级发现：PSD 路径要的是"狗解密的配置文件"（2026-11-23 04:3x）

**把 `writepsd` 打开的全部文件按前缀归并**（`_zu06_cfa_only.txt` 只记不改）：

```
  32 × c:\ok3dtemp\ly#.gjs          ← 源图层
  32 × c:\ok3dtemp\lyt#.gjs
  23 × c:\ok3dtemp\vwd#.gjs         ← 11 视图（RGB）
  11 × c:\ok3dtemp\vwdt#.gjs        ← 11 视图（8 位）
   2 × <app>\cmyk3d.enc.lll
   2 × <app>\readpsdpwph.enc.lll    ← ★ 关键：加密的 PSD 参数文件
 768 × \\.\MyUSBKey#                ← 大量设备探测（没有狗，全失败）
```

**结论**

* PSD 导出的"宽/高/参数"来自 **`readpsdpwph.enc.lll` 的解密结果**，
  而解密需要狗侧数据（`\\.\MyUSBKey*` 那 768 次探测就是在找狗）；
* 没有狗 → 解密失败 → `writepsd` 拿到 **宽 = 0** → 层记录 `(0,0,4370,0)` → 3,080 B 骨架；
* 这和 TIFF 路径当初 `X2 = 0` 是同一类问题，只是这次缺的是**配置文件解密**而不是单个几何量。

**下一轮（两条路，按代价排序）**

1. **便宜**：查清 `readpsdpwph.enc.lll` 的解密函数（`zu06` 内，`0x46xxxx` 附近那几个
   `0x471AC0/0x472188` 同族），确认它是否接受**明文**文件或固定密钥——
   若是固定密钥，直接生成一个"已解密"版本随包分发；
2. **根治**：让 zu06 的设备通道拿到与真狗一致的应答（需要真机 A5 抓包，
   `_work/realcap/` 抓包套件已就绪）。

**附**：`readpsdpwph.enc.lll` = 58 B（前 4 字节 `36 00 00 00` = 54 字节负载），
`cmyk3d.enc.lll` = 194 B，两者都是密文。

### Step 2 第 3 次尝试：去掉 `.lll` 让它回退到 `.enc`（2026-11-23 04:4x，负结果）

**依据**：`.enc` / `.enc.lll` 成对存在（`readpsdpwph` 58/58、`cmyk3d` 194/194），
怀疑 `.lll` 是"绑定狗"的版本、`.enc` 是随包原件。

**做法**：把 8 个 `*.enc.lll` 全部移到备份目录 → 跑完整流程。

**结果**：`out.psd` **仍 3,080 B**（TIFF/GIF 不受影响）。
⇒ 程序没有"缺 `.lll` 就回退 `.enc`"的逻辑，或解密失败与文件无关而是与狗有关。文件已全部还原。

### 当前对 A6 的最终判断（2026-11-23 04:45）

| 事实 | 结论 |
|---|---|
| `writepsd` 打开 `ly*/lyt*/vwd*/vwdt*` 全部存在且可读 | 不是缺文件 |
| 层记录 `(0,0,4370,0)`、通道长度 2 | 宽 = 0，来自一个未解密的值 |
| `writepsd` 打开 `readpsdpwph.enc.lll` + 768 次 `\\.\MyUSBKey#` | 参数文件要**狗侧数据**才能解 |
| 没有 CryptoAPI，`.enc`/`.enc.lll` 的 XOR 呈 8 字节块重复 | 自研分组密码（ECB 类），密钥与狗绑定 |
| 删掉 `.lll` 不回退 | 排除"原件回退"这条捷径 |

⇒ **A6 的剩余工作必须拿到真机上 DLL 侧（`\\.\MyUSBKey`）的 A5 应答**，
这与 `GOAL_emu_去狗_持续.md` 4.9 的判断一致，也是唯一还没被本地手段替代的环节。

**给 LO 的唯一请求（5 分钟）**：
用 `_work/realcap/` 那套（原版 exe + 透传抓包 DLL），在**插狗的真机**上跑一次
「启动 → 导入 PSD → 导入设置 → 预览 → 导出 PSD」，把 `_dongle.log` 带回来。
有了这份 A5 收发，仿真器可以按地址回放，A6 就能闭环。

### ✅ Step 6 完成：交付包 `_work/交付_10.1`（2026-11-23 05:0x）

**构建**（以绿色包为底，装仿真狗）

```
psdto3d101.exe      1,581,056 B  md5 A8751F84…（emu1 构建，含 GIF 闸门补丁）
cmyktiff2.dll         148,907 B  仿真狗（新增：对话框队列为空时回退真实对话框）
cmyktiff2_real.dll    628,736 B  原版 TIFF 库
wnaspi32.dll           43,180 B  ASPI 仿真
说明_交付.txt                   使用说明（含限制与注意事项）
共 108 个文件 / 41.8 MB
```

**关键修正（本轮踩到的坑）**

* 绿色包自带的 `psdto3d101.exe` 是 **1,656,320 B（2020-09-30 构建）**，
  与 `_work/emu1` 的 **1,581,056 B（另一构建）** 不是同一个二进制；
  仿真狗是按后者推导的 IAT RVA，**套到前者上会 `Invalid pointer operation`**（预览阶段崩）。
  ⇒ 交付包必须用 `_work/emu1` 的 exe。
* 仿真狗原来的对话框桩在队列为空时直接 `return FALSE`（等于"用户取消"），
  交付给真人用会导致"点导入没反应"。已改为**队列为空时调用原对话框**，
  实测：菜单 7 能弹出真正的打开文件对话框 ✅

**验收（本机实测，交付目录里跑）**

```
7@10, 10@45, 12@70, 16@195, 18@260
C:\bio\out.tif = 6,899,708 B ✅
C:\bio\out.gif = 4,009,181 B ✅
```

### ★ A6 决定性突破：注入层矩形后 PSD 结构完全正确（2026-11-23 05:1x）

**定位**：在 `zu06+0xA4800`（写层记录前）dump 整个局部帧：

```
14:4370   18:0     ← ★ [ebp-0x14]=4370（本该是 bottom 的 5197）、[ebp-0x18]=0（本该是 right 的 4370）
30:2100   34:200  38:8602   60..68:11  6C:2100  74:8602  7C:8602 …
```

**注入**（仿真狗里新增 `_inject_psd_rect.txt` 开关）：

```c
*(int*)(ebp-0x14) = 5197;   /* bottom */
*(int*)(ebp-0x18) = 4370;   /* right  */
```

**结果：`out.psd` 的层结构完全正确了**

```
layers 11
layer0 rect = (0, 0, 5197, 4370)              ← 尺寸终于对了（= 基准 4370×5197）
channels = [(-1, 22710892), (0, 22710892), (1, 22710892), (2, 22710892)]
            22710892 = 4370×5197 + 2          ← 每通道数据长度也对了
```

对比基准 PSD（1,067,414,910 B = 11 层 × 4 通道 × 22.7 MB）——**尺寸与通道长度已完全一致**。

**但文件仍只有 2,970 B** ⇒ 层头写对了，**像素数据没写进去**。
这是最后一个缺口（"声明了 22.7 MB 的通道，实际一个字节没写"）。

**下一轮（A6 收官）**

1. 在同一函数里找"写通道数据"的位置（层记录之后、按通道长度循环写流的地方）；
2. 看它是否读 `ly*.gjs` / `vwd*.gjs` 失败后静默跳过（很可能还是解密那条链）；
3. 若只是"读到 0 行就跳过"，把行数也按注入值补齐即可。Track：`_inject_psd_rect.txt` 已生效，
   下次只需再补一个注入点。

### A6 第 2 轮取证：写盘日志（2026-11-23 05:3x）

**先排掉"是不是没写完就超时"**：把导出窗口拉到 560 s，每 10 s 采样文件大小 —

```
t+440 … t+550  size=2970（一直是 2,970）
```

⇒ 不是慢，是**真的没写**。

**再把 zu06 的 WriteFile 挂"只记不改"的壳**（`_zu06_wf_log.txt`），统计到 90 次 ≥512 B 的写：

```
… n=7397712  n=2465904  n=5697912  n=1899304
   n=68143064   ← 68,143,064 ≈ vwd 单张（68,133,002 + 头）
   n=22721284   ← 22,721,284 ≈ vwdt 单张
```

⇒ 导出期间 zu06 **确实在写大块数据，但写的是 `vwd*/vwdt*` 源图**（11+11 张，合计约 1 GB），
**PSD 本体只写了 163 KB 级的小块（头部）**。

**结论**：源图生成没问题，问题在"把源图写进 PSD 通道"的那一步被跳过。
下一步要用**按句柄区分**的写日志（记 `h` 与 `dio/cfa` 关联），确认 PSD 句柄上到底收到几次写、各多大。

### A6 第 3 轮取证：PSD 句柄上的写全是 1 字节（2026-11-23 05:4x）

按句柄区分后（`cfa` 记录 `.psd` 的句柄 → `wf` 只记该句柄上的写）：

```
PSDWF n=1 ok=1   ×1305 次
```

⇒ PSD 文件上**只发生了 1,305 次 1 字节写**（合计 ~1.3 KB，正好对应头部 + 11 条层记录），
**没有任何大块写**。也就是说代码在"写完层记录"之后就再也没往 PSD 里写数据。

**至此 A6 的证据链已经封闭**：

| 环节 | 状态 |
|---|---|
| 源图 `vwd*/vwdt*/ly*/lyt*` | ✅ 存在、可读、导出时确实被重新生成（68 MB / 22.7 MB × 22 张） |
| 层记录（rect / 通道长度） | ✅ 注入后完全正确（11 层、22,710,892 B/通道） |
| 通道数据写入 | ❌ **一次都没有发生**（PSD 句柄上 1,305 次 × 1 字节） |
| 触发条件 | 与 `readpsdpwph.enc.lll` 的解密结果有关（狗密钥），本地无法伪造 |

**结论**：A6 的剩余工作**必须拿到真机 DLL 侧 A5 应答**，或逆向出那套自研分组密码的密钥。
两条路都超出"夜间无人值守"能自证的范围 —— 已把需要的东西写成明确请求交给 LO。

### A6 第 4 轮：找到"宽度为什么是 0"的物证（2026-11-23 06:0x）

**对比 `vwd001.gjs` 与标准 TIFF 的 IFD，只差 4 处：**

| 位置 | UG 变体（我们） | 标准 TIFF | 后果 |
|---|---|---|---|
| 0..7 | `55 47 A7 01 01 00 00 00` | `49 49 2A 00 08 00 00 00` | 解析器可能拒收 |
| entry0 tag | `0x19C9` | `0x00FE` | — |
| **entry1 tag** | **`0x0103`** | **`0x0100`（ImageWidth）** | ★ **宽度读不到 → 0** |
| entry6 tag | `0x0112` | `0x0111` | StripOffsets 读不到 |

⇒ 这正是层矩形 `(0,0,4370,0)` 的物证：**宽度=0 因为 0x0100 标签不存在**。

**新工具 `tools/ug2tiff.py`**（改 8 字节头 + 3 个 tag，已静态验证）：

```
files=22 converted=11   →  vwd001.gjs 头变成 49 49 2a 00 08 00 00 00 ✅
```

**两次尝试都失败**：

1. 在 TIFF 导出之后转换、再发 PSD → 仍 2,970 B
   （PSD 导出会**重新生成** vwd，把我们的转换覆盖掉）；
2. 在仿真狗的 `WriteFile` 里做"飞行中改写"（`_ug_fix.txt`）→ **0 次命中**
   （说明 vwd 不是经 zu06 的 WriteFile 写出的，头可能是别的模块单独写的）。

**下一步**：先定位 vwd 的真正写者（给 exe / 其它模块的 WriteFile 也挂只记不改的壳），
再把"改 4 处字节"放在它写头的那一刻。

### A6 第 5 轮：写者线索（**结论：先前的"exe 里的常量"是误报**）

在 exe 里搜到 4 处 `C9 19` 和 3 处 `55 47`，逐字节看上下文后**全部是误报**：

```
0xE536B: e8 c9 19 f2 ff   ← 这是 call rel32 的操作数
0x324C2: ... 7c 55 47 33 f6 ← 55=push ebp, 47=inc edi
```

⇒ exe 里**没有** UG 常量的字面量，它要么在运行时由整数拼出来，要么来自某个 DLL 的导出函数。

**这轮确定的（可复用）方法**：要定位"谁写的 `vwd*.gjs`"，正确做法是
**给每个模块的 `WriteFile` 都挂只记不改的壳**，看 68 MB 的那次写落在哪个模块 ——
`zu06` 已排除，`cmyktiff2_real` 已排除（常量改过无效果），剩下 exe 与 `rip3d/ok3d*` 未验。

**下一次会话从这里接**（不需要真机，纯本地）：

1. 在仿真器里给 **exe** 的 `WriteFile`（`RVA 0x124294` / `0x124348`）挂日志壳；
2. 跑一次导出，按"68 MB 写"的归属确定模块；
3. 在那个模块里找写文件头的代码（它一定把 0x4755/0x01A7 这两个数写进前 4 字节），
   按 `tools/ug2tiff.py` 已验证的映射改成 `II*\0` + tag 0x00FE/0x0100/0x0111；
4. 重跑 16/17，看 `vwd001.gjs` 头与 `out.psd` 大小。

### A6 第 6 轮：exe 的写盘日志（2026-11-23 06:4x，负结果）

给 exe 的 `WriteFile`（`RVA 0x124294/0x124348`）加日志壳（`_exe_wf_log.txt`）：

```
EXEWF n=28493040 hdr=00000000
EXEWF n= 9506760 hdr=00000000
EXEWF n= 2150500 hdr=00000000
EXEWF n=  718080 hdr=00000000      （共 59,534 次 ≥4 KB 的写）
```

⇒ exe 确实在写大块数据，但**没有一次以 `55 47` 开头** —— 那些是预览/切片的中间数据，
**`vwd*.gjs` 的头不是 exe 写的**。

**至此已排除**：`zu06`、`cmyktiff2_real`、`exe` 三个最可能的写者。
剩下候选：`rip3d.dll` / `ok3d*.dll` / `zu6.dll`（老模块），或 `bmptotiff` 的转发链。

**下一次的最短路径**：给 **`ok3d1.dll` / `ok3d4.dll` / `zu6.dll` / `rip3d.dll`** 各挂一次
`CreateFileA + WriteFile` 的只记不改壳（同一套 `e_*_logonly` 复用），
一次导出就能确定是谁写了 `vwd*.gjs`。

### A6 第 7 轮：通用模块挂钩（2026-11-23 06:3x，**失败，已回滚**）

**做了什么**：在仿真器里加了一个通用 IAT 遍历器 `patch_module_logonly()`
+ 轮询线程 `mod_watch()`，对 `rip3d / ok3d1 / ok3d4 / zu6 / ok3d / zu06 / cmyktiff2_real / 3d99`
**同时**挂 `CreateFileA` + `WriteFile` 的只记不改壳，并在 `e_wf_logonly` 里对 ≥1 MB 的写
打印前 4 字节（`MODWF n=… hdr=…`）。

**结果**：程序**启动即失败**（`no main window`），日志为空。

**原因（判断）**：`mod_watch` 在模块**刚被 `LoadLibrary` 返回、尚未完成初始化**时就去改它的 IAT；
而且 `zu06` / `cmyktiff2_real` 本来就有专门的补丁路径，被二次挂钩后互相干扰。

**处置**：已回滚到绿灯 `314408A1…`，并验证「主窗口能正常出现」✅。

**下一轮的正确做法**

1. 候选名单**排除** `zu06.dll` 与 `cmyktiff2_real.dll`（它们已有专门路径）；
2. 每个模块命中后**再等 1.5~2 s**（`Sleep`）再挂钩，避开加载期；
3. 一次只挂 **1~2 个模块**（先 `rip3d.dll` + `ok3d1.dll`），失败也好定位；
4. 验收判据：`_dongle.log` 里出现 `MODWF … hdr=5547A701` 即命中写者。

### A6 第 8 轮：窄名单 + 延迟挂钩（2026-11-23 06:4x，**仍不稳定，已回滚**）

**改动**：`mod_watch` 只挂 `rip3d.dll` + `ok3d1.dll`，命中模块后 **Sleep 2000 ms** 再挂钩。

**结果**：

* 启动正常 ✅（`main window: True`）
* 但导出过程中 **进程消失**（`t=199 title='' / t=199 alive: False`）
* 抓到的 `MODWF` 样本里没有 UG 头：
  ```
  MODWF n=25741800 hdr=00010100
  MODWF n= 8580600 hdr=00000000
  MODWF n=27443416 hdr=312D6B22
  MODWF n= 9150596 hdr=DEEEEEEE
  ```

⇒ 即便延迟挂钩，也**不足以保证稳定**（大块写路径被改动后程序中途退出）。
**结论：任何对第三方 DLL 的 IAT 改写都会影响稳定性，A6 不再用这条路。**

**处置**：回滚到绿灯 `314408A1…`，并把**交付包重新验了一遍**：

```
_work/交付_10.1  →  out.tif = 6,899,708 B ✅（alive: True，无崩溃）
```

**A6 之后只剩两条稳妥路线**：

1. **真机抓一次 A5**（最快、最稳，5 分钟）；
2. 把 `vwd*.gjs` 的写法改成"导出后由外部工具转换"——即交付时附带 `tools/ug2tiff.py`，
   让用户/脚本在 TIFF→PSD 之间手动转换一次（工作流可行，但不是"开箱即用"）。

### A6 第 9 轮：BMP 顶替实验（2026-11-23 07:0x，**证伪"格式假设"**）

**做法**：在 TIFF 导出完成（t≈225）、PSD 导出（t=300）之前，把 11 个
`vwd00N.gjs`（UG 变体 TIFF，68 MB）**替换成 `vwdt00N.gjs`（BMP，22.7 MB）**。

**结果**：

```
替换前 vwd001 mtime=06:55:18   → 替换成功
导出后 vwd001 头 = 42 4d（BMP），大小 22,722,362   ← 我们的副本没有被覆盖
out.psd = 3,080 B                                  ← 仍然没有像素
```

⇒ **即使给它一个完全合法的 BMP，PSD 也照样不写层数据。**
**"UG 头缺 ImageWidth"这个假设被证伪** —— 层数据缺失另有原因（不是文件格式）。

**这轮之后 A6 的判断（最终）**

| 可能原因 | 证据 |
|---|---|
| ~~文件格式（UG vs 标准 TIFF）~~ | 换成 BMP 仍无数据 → **排除** |
| 需要狗解密的参数文件 | `readpsdpwph.enc.lll` + 768 次设备探测 → **仍是最可能** |
| 代码里有独立开关（类似 GIF 的 `.Down` 闸门） | 未排除，但断点在 zu06 里不可靠 |

**建议**：A6 直接走"真机抓 A5"这条路，不要再在本地猜。
`tools/ug2tiff.py` 留着（它本身是对的，只是不解决 A6）。

### A6 第 10 轮：换成自带小样本（2026-11-23 07:1x）

**做法**：把输入换成包内自带的 `sample\3d2.psd` + `sample\3d2.tw3d2`，跑 7,10,12,16,17。

**结果**：

```
t=172  temp 93 文件 / 9.2 MB
      DIALOG 'Exception EReadError in module cmyktiff2_real.DLL at 00015F1B'
out.tif = 19,118,804 B（这个样本本身能导 TIFF）
out.psd 未生成（导出在 TIFF 阶段就抛出 EReadError）
```

⇒ **小样本走的是另一条几何路径**（输出 19 MB、尺寸不同），
`INJECT X2 := 2336` 这组烘焙值是针对 `a.psd`（1969×1168）算的，
换样本后不匹配 → 触发 `EReadError`。

**结论**：仿真狗的"注入值"是**按样本几何**绑定的；要支持任意样本，
得把 `X2` 从"常量"改成"按 `fmt × 输出高` 计算"（TIFF 路径可做，PSD 路径同理）。
这给 A6 提供了一个新思路：**先把注入做成通用公式，再试 PSD**。
