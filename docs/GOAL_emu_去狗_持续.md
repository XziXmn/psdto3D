# GOAL · PSDTO3D 去狗（仿真狗路线）持续任务

> 本文件是**无人值守推进的工作单**。每次被调度时：先读本文件 →
> 执行「下一步」→ 用实测数据更新「进度日志」→ 保存。不要跳过验证。

---

## 一、终极目标（Definition of Done）

**原版 exe（允许最小必要补丁）+ 仿真狗 DLL，在无狗机器上完整运行：**

1. 启动、狗检测原生通过
2. 导入 PSD（32 层）
3. 导入工程设置
4. 预览（生成完整 ok3dtemp）
5. **导出 TIFF** → 与真狗 `test/0《生化危机：爆发夜》第一人称海报汉化/0《生化危机：爆发夜》第一人称海报汉化.tif`（6,899,708 B）逐字节/逐像素对比
6. **导出 PSD** → 与 `..._3D输出.psd`（1,067,414,910 B）逐层对比

任一项不通过就不算完成。

---

## 二、当前版本与文件位置

> **2026-11-23 起：主版本 = 2022（`psdto3d104` 同代），10.1 仅作对照。**
> 原因见 `复盘_基线纠正_2026-11-23.md`：2022 套件的 `cmyktiff2.dll` 里 TIFF 头常量是
> 标准 `II*\0` + 标签 0x100/0x101/0x111，与真机基准一致；10.1 套件是 `UG` 变体。

```
主工作版本：_work/2022emu/            ← 2022 包 + 仿真狗
   psdto3d101.exe        2022 绿色版 exe（1,584,140 B，已含历次补丁）
   cmyktiff2.dll         = cmykdrop/cmyktiff2_emu.dll（仿真狗 + 导出转发）
   cmyktiff2_real.dll    2022 原版 TIFF 库改名副本（转发目标）
   cmyktiff2.dll.orig2   原始 DLL 备份
   ok3d4.dll             ★ 必须用 10.1 那一份（原 2022 那份会让 0x7A82A46F 校验失败）
   ok3d4.dll.2022orig    2022 原版备份（校验和不匹配，仅留档）
   wnaspi32.dll          ASPI 仿真
   _dlgopen.txt / _dlgsave.txt   对话框应答（C:\bio\a.psd、C:\bio\a.tw3d2、C:\bio\out2022.tif）
   _dongle.log           仿真器日志（replay / zero-write / cfa / DIFF）

对照（仅供 diff）：_work/emu1/        ← 10.1 线，导出已跑通 6,899,708 B，但头部是 UG 变体
                   _work/v15/         ← 纯补丁路线
交付包（待重做）：  _work/2022程序/    ← 已拷入 2022 包 + ok3d4 修正，尚未装仿真器
```

仿真器源码：`cmykdrop/dongle_emu.c`
回放表：`cmykdrop/replay_table.h`（63 事件，由 `_work/real3/_capture.log` 生成）
真狗抓包：`_work/real3/_capture.log`（11.4 MB / 73965 行）

编译（32 位）：
```
MINGW="C:/Users/moo/AppData/Local/Temp/zcode-tools/i686-mingw/mingw32/bin/i686-w64-mingw32-gcc.exe"
"$MINGW" -O2 -shared -static-libgcc -o cmykdrop/cmyktiff2_emu.dll \
    cmykdrop/dongle_emu.c cmykdrop/replay_table.h cmykdrop/cmyktiff2_emu.def \
    -luser32 -lkernel32
cp cmykdrop/cmyktiff2_emu.dll _work/emu1/cmyktiff2.dll
```
探针工具：`cmykdrop/hwbp32p.exe`（源码 hwbp32p.c，含 P502/GATE/GATE2/DOEXEC/506132 等探针）

---

## 三、已通过（不要重复验证）

| 项 | 证据 |
|---|---|
| 狗检测原生通过 | `E32FCRET eax=0, s8/sc/s10/s14 = 0x7B ×4` |
| 导入 PSD | 标题变 `Psdto3d 10.1  a.psd` |
| 导入设置 | 标题变 `a.psd a.tw3d2` |
| 预览 | ok3dtemp 1275 个文件 |
| 回放对齐 | replay idx 0-18 全命中（18 组事件） |
| GATE1（0x50B070） | TSpeedButton +0x58 = 1 |

---

## 四、当前卡点

**导出流程已完整走通到保存对话框，卡在浮点除零。**

### 4.1 关键机制（LO 2026-11-22 提供，已实测确认）

**导出菜单（16/17/18）在预览之前是 GRAYED+DISABLED，预览开始约 20 秒后才启用。**
实测 `GetMenuState(16)`：导入前 3 → 导入后 3 → 导入设置后 3 → 预览 t+10 仍 3 →
**t+25 变成 0（可用）**，之后保持 0。
之前的测试要么跳过预览、要么先发菜单13（停止）——所以 WM_COMMAND 从未发出。

**正确操作序列：导入 PSD → 导入设置 → 预览(菜单12) → 等 m16==0 → 导出(菜单16)，不要先发 13。**

### 4.2 已打通的全链路（VEH 软件断点实测，可靠）

```
EMU EnableMenu id=16 en=0                 ← 预览约 20s 后启用
SBp HIT 0050B070 #1                        ← GATE1 入口
SBp HIT 0050B073                           ← 装载按钮对象
SBp HIT 0050B07E eax=025B6501              ← al=1，闸门通过
SBp HIT 0050B086                           ← call 0x505A44
SBp HIT 00505A66                           ← GATE2（0x505A44 内）
SBp HIT 0043265E #3 edx=004316E0           ← Execute，GetSaveFileNameA 跳板
EMU gsfn -> C:\bio\out.tif                 ← 保存对话框被调用并应答成功
```

### 4.3 当前阻塞：浮点除零（已定位到 TIFF 库内部）

```
DIVZERO code=C000008E eip=00DAFDB9 esp=001AF1A8
DIVZERO stack: 001AF4F0 00DB32AF ...
DIVZERO mod_eip=...\cmyktiff2_real.DLL base=00D30000
DIVZERO mod_ret=...\cmyktiff2_real.DLL base=00D30000
```

**除零点在 `cmyktiff2_real.dll`（原版 TIFF 编码库）的 `mergtotiff` 里：**

- `mergtotiff` RVA `0x7F720`（VA 0x47F720）
- 除零指令 VA `0xDAFDD5` = RVA **0x7FDD5**，`fdivp st(1)`
- **exe 侧 `0x4FF1E4` 本身就是 `jmp [0x524a74]`（mergtotiff 跳板）**，
  `0x4FF1EC` = `jmp [0x524a70]`（bmptotiff）

**除数的计算（DLL 内 0x47FA37-0x47FA63）：**

```
call 0x402AE4                  → int64（BMP 尺寸/像素数）
fild qword [ebp+0x2b0]         ← 该 int64
fild qword [ebp+0xC]           ← 参数2 = [0x52306C] = 2973425
fild qword [ebp+0x14]          ← 参数4 = [0x523170] = 424775
fdivp st(1)                    ← 2973425 / 424775 ≈ 7.0
fmulp st(1)                    ← × 像素数
fadd [0x4832D0]
call 0x402AE4                  ← ROUND
mov [ebp-0x110], eax           ← 除数
...
sub [ebp-0x110], eax           ← 0x47FD2D 循环内累计扣减
sub [ebp-0x110], 0x39DB67F8    ← 0x47FD97
fild [ebp-0x110]
fdivp st(1)                    ← 0x47FDD5 除零
```

**exe 传入的 15 个参数（0x5060AD-0x506131，栈布局）：**

```
[ebp+08] [esi+0x510]   TStrings（BMP 文件列表）
[ebp+0C] [0x52306C] = 2973425      （低）
[ebp+10] [0x523070] = 0            （高）
[ebp+14] [0x523170] = 424775       （低）
[ebp+18] [0x523174] = 0            （高）
[ebp+1C] int64（由 0x523074 计算）
[ebp+24] int64（由 0x52307C 计算）
[ebp+2C] [0x523069]（byte，输出格式）
[ebp+30] [0x5230CD] = 0x9C
[ebp+34] [0x5230CB] = 0x64
[ebp+38] [0x52315E]
[ebp+3C] [0x5230E4]
[ebp+40] [esi+0x394]
[ebp+44] [0x523068]
[ebp+48] [ebp-4]
```

**结论：宽高比参数正常（2973425 / 424775 ≈ 7.0），除数为 0 说明
`0x402AE4` 返回的 BMP 像素数为 0，或 `[ebp-0x110]` 在 0x47FD2D/0x47FD97
的扣减后归零 —— 即 BMP 数据未正确读入。**

### 4.4 除数的完整计算链（DLL 内，反汇编已核对）

```
0047FA31  fdiv dword [0x4832CC]        ; [0x4832CC] = 100000000.0
0047FA37  call 0x402AE4                ; ROUND(Extended) -> int64
0047FA3C  mov  [ebp-0x2B0], eax/edx    ; 中间量 X
0047FA4E  fild qword [ebp+0xC]         ; 参数2 = [0x52306C] = 2973425
0047FA51  fild qword [ebp+0x14]        ; 参数4 = [0x523170] = 424775
0047FA54  fdivp st(1)                  ; 2973425 / 424775 ≈ 7.0
0047FA56  fmulp st(1)                  ; × X
0047FA58  fadd dword [0x4832D0]        ; + 8602.0
0047FA5E  call 0x402AE4                ; ROUND
0047FA63  mov  [ebp-0x110], eax        ; ★除数
...
0047FD19  add  [ebp-0x11C], eax        ; 循环累计
0047FD27  mov  eax, [ebp-0x11C]
0047FD2D  sub  [ebp-0x110], eax        ; 第一次扣减
0047FD91  sub  [ebp-0x110], 0x39DB67F8 ; 第二次扣减（0x47FD97 是错位边界）
0047FDCF  fild dword [ebp-0x110]
0047FDD5  fdivp st(1)                  ; ★除零
```

常量：`0x4832CC=1e8`、`0x4832D0=8602.0`（与 exe 侧 `0x505B1C` 的立即数
`0x219A=8602` 一致）、`0x4832C8=10000.0`、第二次扣减 `0x39DB67F8=971,073,528`。

**除数 = ROUND( X/1e8 × 7.0 + 8602 ) − 循环累计 − 971,073,528**

三者相抵为 0 时除零。X 由 `0x47FA31` 之前的浮点栈给出（尚未追到底）。

### 4.5 除零根因（实测锁定，2026-11-22）

VEH 在除零现场读到的局部量：

```
-110=1969        （不是 0，且恰好等于真狗 TIFF 宽度 1969 —— 管线参数正确）
-124=0           ★ 分子为 0
-11c=-970671710
-1e4=8716288
DIVZERO curstr ptr=0B072094 len=22 [c:\ok3dtemp\vwd001.gjs]   ★★ 关键
```

**根因：传给 `mergtotiff` 的 TStrings 列表里放的是 `.gjs` 文件路径，不是 BMP。**

DLL 侧逻辑（已完整反汇编）：

```
0047FAC0  mov al,[ebp-0x133]      ; TStrings.Count
0047FAD8  call 0x40521C           ; SetLength(array, Count)
0047FB0D  call [esi+0xC]          ; TStrings[i] → 路径字符串
0047FB23  call 0x47DCD4           ; 按 BMP 打开并读头
0047FB32  mov eax,[array[i]+4]    ; field4 = 解析结果（失败=0）
0047FB62  mov [ebp-0x124], eax    ; 覆盖 300000
0047FDC9  fild [ebp-0x124]
0047FDD5  fdivp                   ; 0 / … → 后续除零
```

`0x47DCD4` = BMP 读取器（打开文件 → 读 8 字节头 → 读 2 字节 → `test esi,esi /
jle 0x47DDD9` 失败分支）。对 `.gjs` 文件必然走失败分支 → field4=0。

**对照真狗抓包：真狗预览写的是 `D:\ok3dtemp\vw1.bmp`（BMP），
emu1 写的是 `c:\ok3dtemp\vwd001.gjs`。**

### 4.6 输出格式的来源（exe 侧，已定位）

```asm
00506064  mov eax,[esi+0x560]
0050606C  call [edx+0xCC]        ; 取某属性
00506072  mov [0x523068],al
00506077  mov [0x523068],2       ; 硬编码 2
00506084  mov eax,[esi+0x568]    ; ★ 输出设置控件（格式选择）
0050608A  call 0x45FA84          ; 取控件文本
00506095  call 0x409B08          ; StrToInt
0050609A  mov [0x523069],al      ; → 传给 DLL 的 [ebp+0x2C]
```

**`[esi+0x568]` 控件的值决定生成 BMP 还是 GJS。真狗上它是 BMP 模式。**

### 4.7 导出链路已完整反汇编（2026-11-22 深夜，推翻 4.5/4.6 的部分结论）

**结论先说：不是狗的问题。回放给程序的应答与真狗字节一致；失败在 `cmyktiff2.dll`
内部的几何解码。** 证据链：

**(a) `.gjs` 就是 BMP，列表里放 `.gjs` 完全正常**
真狗抓包 line 14839：写 `D:\ok3dtemp\15gxt9.gjs`，头是 `424D...`（"BM"）+
BITMAPINFOHEADER（2638×2468, 8bpp）。所以 `vwd*.gjs` 是 BMP 类容器，不是错误。

**(b) 导出函数（exe `0x505A44`）的完整流程**

```
0x505A66  [esi+0x4F4].vtbl+0x3C()      ; 闸门1（假则整段跳过）
0x505A79  Application.ProcessMessages
0x505A8F  lines := StrToInt([esi+0x528].Text)      → [0x5230FC]
0x505AB0  [0x523170] := StrToFloat([esi+0x524].Text)*10000
0x505AD3  if [0x523154] <> 0x63 then lines:=7, [0x523170]:=0xAB310   ; 版本闸门
0x505B85  构造 7 个字符串（sales@ok3d.com / www.3d99.com / ok3d /
          +86-755-61282468 / 01st.ini / "\360\1" / d:\downloads）
0x505BF3  压 22 个参数 + 3 寄存器参数
0x505C58  call 0x4D2C48                ; ★ 构造并发送 496 字节记录到狗 0x01F0
0x505CCB  [esi+0x510].Clear
0x505CDE  计算每层偏移 → [0x5231E4][i]
0x505D2E  for n := lines downto 1:
0x505E17      name := 'vwd' + 三位序号              (0x5062B4/0x50629C/0x5062A8)
0x505F5C      bmptotiff([0x523160], …, name+'.gjs')  ; ★ 生成 vwdNNN.gjs
0x505FAC      [esi+0x510]+0x218 → Add(name)
0x5060AD  压 15 个参数
0x506132  call mergtotiff(list, …)                  ; ★ 合并
```

**(c) 真狗也走同一条路** —— 抓包里导出会话（`SPTWR addr=01F0`，
数据开头 `00000000 16000000 00000000 43300000 17300000 C9190000 D7850100 9A210000`）
正是 `0x4D2C48` 构造的那块，`0x3043/0x3017/0x19C9/0x185D7/0x219A` 五个常量
与 exe `[ebp-0x18..-0x28]` 完全对应。

**(d) 回放应答正确**：emu1 导出时 replay idx 19-24，返回的 501 字节与
抓包 `0200000016000000000000004330000017300000C9190005E610097377BBC4…` 一致。

**(e) `mergtotiff` 内部（RVA 0x7F720）**
- 遍历 TStrings，每个文件 `call 0x47DCD4` 解析成 16 字节记录
- 类型映射（跳表已解出）：**0x100 → rec+4，0x101 → rec+8，0x111 → rec+0xC**
- 取 min(rec+4)、min(rec+8)，初值 0x493E0
- 再 `call 0x4626B4`（**与 exe `0x4D2C48` 是同一段代码**，81/96 字节一致）
  得到 X1、X2；`[ebp-0x104] = ROUND(X2 / fmt)`，fmt = `[ebp+0x2c] = [0x523069]`
- `0x47FDB1  fild [ebp-0x128] / fild [ebp-0x10c] / fdivp` ← **0x47FDB7 是真凶**
  （x87 异常在后续 `fmul` 0x47FDB9 才上报；`-0x10c` = ROUND(X2/fmt) = 0）

**(f) 实测（VEH 断点，`cmyktiff2_real+0x7F9BF`）**

```
REALGEO X1=0.000000 X2=0.000000 A=0 B=0 fmt=2 count=11
REALSTR [-448]=<null> [-452]=277.2 [-456]=25.2 [-460]=7.0866
        [-464]=8.4274 [-468]=8.4274 [-472]=<null> [-476]=<null>
REALGLOB 523154=99 5230FC=11 5230C6/0x523108=22 52310C=0 523074=180000
         52307C=214056 52306C=2772000 523170=252000 52315C=32 5230F4=13
```

- 授权相关全部正常：`[0x523154]=99`（完整版）、`[0x5230FC]=11`（线数）
- 失败点：`0x4626B4` 打包记录后 `call 0x472D68`，返回码不在 {0, -0x2B, -0x43}
  时就跳过全部输出 → **X1=X2=0**
- 5 个输入字符串是参数本身（277.2 / 25.2 / 7.0866 / 8.4274 / 8.4274），
  3 个 `<null>` 是 `LStrClr` 过的**输出**串，不是缺失输入

**(g) 与真狗仍存在的唯一差异**

```
导出时 0x01F0 请求 offset 4：真狗 0x16(22)，emu 0（其余差异全是栈指针噪声）
0x000A 命令字节：真狗 0x20，emu 0x62/0x52（每次不同 → 疑似指针低字节，非命令码）
```

**(h) 顺带确认的坑**
- `vwd*.gjs` **是导出时由 `bmptotiff` 生成**的（mtime 落在导出窗口内，每秒一个，
  68,133,002 B），不是预览产物；不要用预览时间去判断。
- emu1 的 exe 补丁 `0x4D2BF2`（`31 DB / E9 0B`）只在「四个 0x7B 校验失败」时才会
  走到，正常路径在 `0x4D2BEE` 就跳出去了 → **该补丁对正常流程无副作用**，
  但也不会补偿任何缺失状态。

### 4.8 真凶找到了：`cmyktiff2.dll` 自己有一套狗访问（2026-11-23 凌晨）

**LO 的直觉是对的：确实有隐藏的狗检测，但不在 exe 里，在导出库里。**

#### (a) 证据链

`mergtotiff` → `0x4626B4`（与 exe `0x4D2C48` **同一段代码**，81/96 字节一致）
→ `0x472D68` → 读 `rip3d.enc.lll` → `0x471AC0` → `0x472188`

`cmyktiff2.dll` 的导入表就是狗驱动那套：

```
kernel32 CreateFileA        IAT 0x903D8
kernel32 DeviceIoControl    IAT 0x903C8
kernel32 ReadFile           IAT 0x902D0
kernel32 WriteFile          IAT 0x901F0 / 0x90290
kernel32 SetFilePointer     IAT 0x902B0
kernel32 GetFileSize        IAT 0x90374
kernel32 CloseHandle        IAT 0x903E4
setupapi SetupDiGetClassDevsA / EnumDeviceInterfaces / GetDeviceInterfaceDetailA / DestroyDeviceInfoList
        0x90858 / 0x90854 / 0x90850 / 0x9084C
winsock  WSAStartup / socket / gethostbyname / connect / htons / closesocket（备用"网络狗"路径）
```

DLL 里的字符串常量：
```
0x48BFEC  "\\?\usbstor#disk&ven_usbkey&prod_usbkeyco._&rev_2.00"
0x48C021  "\\?\hid#vid_1670&pid_8763"
0x48BEC0  "my32"
0x462970  "rip3d.enc.lll"
```

`[0x488124]` = DLL 自己的"狗可用"标志：
- `0x466A5C` 初始化函数（winsock 连授权服务）把它置 1
- `0x4676E3` 重置为 0
- **该初始化函数在 DLL 里没有任何引用（死代码）** ⇒ 真机上也走"设备/文件"回退路径

#### (b) 关键修复（已完成，已验证）

**给 `cmyktiff2_real.dll` 也挂上同一套 IAT 钩子**（此前只挂了 exe 的）。
12 个槽位：`CreateFileA/DeviceIoControl/ReadFile/WriteFile×2/SetFilePointer/GetFileSize/CloseHandle/SetupAPI×4`。

效果：
```
EMU patched real dll IAT base=00D30000
EMU open device <- \\?\usbstor#disk&ven_usbkey... -> 0000051C
DECODE ecx/ret=00000000(0)     ← 从 -51/-63 变成 0，DLL 的许可证校验通过了
```

#### (c) DLL 自己的协议（新发现，与 exe 的 SPT 完全不同）

```
LICCALL txt=[\\.\MyUSBKey255]
EMU wf n=16  cmd=A5 00 F0 01 00 00 80 17 00...   ; 写 496B 到 0x01F0
EMU wf n=496 cmd=0C000000F81C20090C0000000300802D
EMU rf n=16  -> 全 0xFB 回执                       ; ← 我们的回执内容不对
EMU wf n=16  cmd=A5 00 1A 00 00 00 80 09 00...   ; 写 26B 到 0x001A
EMU wf n=26  cmd=18003D6AC23B847D219705E5D276B351
EMU rf n=16  -> 全 0xFB 回执
EMU wf n=16  cmd=A5 00 0A 00 F0 01 80 16 00...   ; 执行 0x000A，读 496B
EMU wf n=10  cmd=00000000000000000000
EMU rf n=496 data=0C000000F81C20090C0000000300802D ; ← 读回自己写的请求
```

命令帧格式：`A5 00 <addr:16> <???> <len:16>`，`A5` = 命令头。

**问题：DLL 读到的是自己写进去的请求，不是狗算出来的结果** →
`RECORD` 里的派生字段全 0 → `X1=X2=0` → `0x47FDB7` 的 `fdivp` 除零。

DLL 请求里的参数（= mergtotiff 的几何量）：
```
0B 00 00 00  02 00 00 00  06 00 00 00  05 00 00 00
B0 04 00 00 (=1200)  E6 00 00 00 (=230)  23 00 00 00 (=35)  07 00 00 00 (=7)
```

#### (d) 还差什么

**真狗对这条 A5/几何请求"计算出来的 496 字节"**。真机抓包（`_work/real3`）只抓到了 exe 的 SPT
通道（因为我们当时的 cap DLL 只挂了 exe 的 IAT），**DLL 侧的 `\\.\MyUSBKey255` A5 流量一条都没有**。

#### (e) 这一轮又排掉的三条路（别再重复）

1. **`cmyktiff2Noreg.dll` 不是免注册版**：它的 `mergtotiff` 在 RVA `0x7F4FC`（原版 `0x7F720`），
   但同样调用 `0x4626B4`，`X1/X2`（Noreg 里是 `[ebp-0x1a8]/[ebp-0x1b0]`）同样为 0，
   最后在 `0x7FBF0` 的 `fdivp` 用 `[ebp-0x104]=ROUND(X2/fmt)=0` 除零。换它没用。
2. **X1/X2 不是 DLL 自己算的**：`mergtotiff` 只 `lea` 取地址压栈，`0x4626B4`/`0x471AC0`
   全程没有 `fstp`；全 DLL 的 `fstp qword ptr [reg]` 只有对象字段写和 `0x44EE7C`（Round 辅助）。
   ⇒ 这两个 double 只能由**外部（狗/授权服务）通过指针写入**。
3. **强置 `[0x488124]=1` 走"授权服务"分支是死路**：置 1 后导出会话照常完成，但
   **没有任何 Winsock 调用**（`WSK *` 一条都没有），随后 `EnableMenu id=18` 直接静默退出，
   连 `vwd*.gjs` 都不生成。`0x466A5C` 那个初始化函数在 DLL 内无任何引用（死代码），
   所以这条分支永远拿不到数据。

#### (f) 结论

导出几何 `X1/X2` 是**狗算出来后回写**的，DLL 本身不含算法。
唯一干净的解法：**在真机上抓一次 DLL 侧协议**（A5 帧或 SPT 的 `addr=0012` 会话），
把 496/501 字节应答做进仿真器。

#### (g) 用另一会话的反编译语料对上了（2026-11-22 23:40）

`docs/反编译_cmyktiff2.md` + `_analysis/dump_cmyktiff2_g/0047f720.c` 给出关键事实：

1. **`mergtotiff` 只是壳**，真正合并在 **`rip3d.dll!stai`**（运行时
   `LoadLibrary("rip3d.dll")` + `GetProcAddress(..., "stai")`，指针存 `[ebp-0x1e8]`）。
   → 我此前把 `call [ebp-0x1e8]` 当成 savetiff00，判错了；`0x7E9D0` 从不被直接调用。
2. `mergtotiff` **自己创建** `g_c.tif / g_M.tif / g_Y.tif / g_K.tif`
   （`TIFF.Create(mode=1)`，目录 = 临时路径去掉末尾 4 字符），然后 4 次 `stai(..., a4=1)`；
   再对 `_c/_M/_Y/_K` 做第二轮（`a4=0`）。
3. `savetiff00(int *stream, ushort samples)`：`samples==3` → RGB，否则 4 → CMYK。
   标签号以十进制字符串存在（"259"/"274"/"3d3d9"/"ok3d"）。
4. `gettiffinfo` 解析 **0x100=宽 / 0x101=高 / 0x102=Bits / 0x103=Compression / 0x111=StripOffsets**
   —— 这正好解释了我解出的 16 字节记录 `{+4,+8,+0xC}` 就是 **宽/高/StripOffsets**。
5. **几何被刻意拆到狗里**：
   ```c
   local_110 = 1969;                       // 宽（参数算出来的）
   local_114 = ROUND(X2);                  // ← 狗给
   local_114 = local_114 + 0xC6249808;     // ≈ −970,671,608
   local_118 = in_stack_00000028*local_110 + 1000
             + 0x39C18 - local_124;
   stai(ROUND(size/local_2ac), local_110, local_114, 1, &ti[4]);
   ```
   常量偏移把真实尺寸和狗返回值绑死，**不插狗无法解析出尺寸**。
   实测印证：`local_114` 在无狗时为 `−970,671,710`（即 0 + 1000 + 常量）。

#### (h) 交付包

`_work/完整程序/`（20 MB，69 个文件）：原版 exe + 2 补丁 + 仿真狗 + wnaspi32。
本机验证：启动 / 狗检测 / 导入 PSD / 导入设置 / 预览（1275 文件）/ 导出菜单启用 全部通过。
导出见 (f) 的限制。抓包套件见 `_work/capkit/`。


#### (i) 导出已跑通（2026-11-23 00:07）

两个替换值烘焙进 cmyktiff2.dll 后，导出完整产出 **6,899,708 字节**：

```
INJECT X2 := 2336
PATCH100 cnt=11 min124 0 -> 4370
STAICALL args=(buf, 3, 1969, 1168, 2772000, 0, 1386000, 0)
C:\bio\out.tif = 6,899,708
```

- **X2 = fmt × 输出高** = 2 × 1168 = 2336（狗记录里的尺度字段）
- **rec+4 = rec+8**（源图宽度；原版靠狗记录里的 TIFF 标签 0x100，而 bmptotiff
  写出的容器没有该标签，所以取 0 → stai 拿到 0 尺寸 → 只写头部）

与基准的剩余差异（**版本差异，不是流程错误**）：

| 项 | 我们（10.1 套件） | 基准（10.4 机器） |
|---|---|---|
| 文件头 8 字节 | `55 47 A7 01 01 00 00 00`（"UG" 变体） | `49 49 2A 00 08 00 00 00`（标准 TIFF） |
| 标签[0] | 0x19C9 | 0x00FE |
| 标签[1]/[2] | 0x0103=1168 / 0x0101=1969 | 0x0100=1969 / 0x0101=1168 |
| 标签[6] | 0x0112 | 0x0111 |
| 像素 | 同尺寸同构图，数值不同 | — |

⇒ 要逐字节一致，需用 **10.4 的 cmyktiff2.dll / rip3d.dll** 跑；
仿真器已改成**按 API 地址匹配 IAT**（不绑版本），直接替换即可。

### 4.9 下一步

1. **去真机抓一次 DLL 侧 A5 协议**：把 `cmyktiff2_cap` 改成一并挂 **自己模块** 的
   IAT（和现在 emu 里的 `patch_real_module` 同一套 12 个槽位），真机插狗跑一次
   "预览 → 导出 TIFF"，把 `\\.\MyUSBKey255` 的 A5 收发全录下来。

   **抓包包已做好：`_work/realcap/`**（原版 exe md5 `5407b48…` + 仿真器"透传抓包模式"）
   - 目录里放一个空文件 `_capture.txt` → 仿真器自动切成 pass-through 并记录
     `CAP cfa / CAP dio / CAP wf / CAP rf`（含数据前 32~64 字节）
   - 本机空跑已验证：`EMU capture mode = 1`，能看到 exe 依次探测
     `\\?\usbstor#disk&ven_usbkey…`、`\\.\MyUSBKey0/1/2…`
   - 真机上：插狗 → 跑 `psdto3d101.exe` → 预览 → 导出 TIFF → 把 `_dongle.log` 拿回来
2. 把录到的 496 字节应答做进仿真器：按 A5 命令帧 + 地址匹配回放。
3. 再验 `REALGEO X1/X2` 是否非 0、除零是否消失、TIFF 是否等于基准
   （6,899,708 B / 1969×1168）。
4. 备查：真机装的是 **psdto3d104**（抓包里读 `psdto3d104.inf`），我们跑的是 10.1。

---

## 五、下一步（按顺序做，每次调度做 1 步并记录）

### 步骤 1：定位 Execute 内的实际退出点

用探针在下列地址分别下断点，跑同一命令表，记录命中与否：

```
命令表: '7@8,10@30,16@60'   时长 110s
地址:
  0x432663   Execute 首调（[dlg+0x7C] 虚方法）
  0x4326BF   call 0x4325E8 前
  0x43288F   call DoExecute 前
```

判据：**菜单16 时刻（t≈60s 之后）是否命中**。
第一个「命中 → 下一个不命中」的区间就是退出点。

跑法：
```
./cmykdrop/hwbp32p.exe _work/emu1/psdto3d101.exe _work/emu1 \
    exec@<ADDR> 110 '7@8,10@30,16@60' _work/emu1/_<ADDR>.txt
grep -a "eip=<ADDR>" _work/emu1/_<ADDR>.txt
```

注意区分 t 值：菜单7 ≈8s、菜单10 ≈30s、菜单16 ≈60s。
**只关心 60s 之后的命中。**

### 步骤 2：读退出点的判断条件

定位到区间后，反汇编该区间（capstone，VA→offset 公式：`off = VA-0x400000-0xC00`），
找出条件跳转与它读的字段（大概率是 `[dlg+0xXX]` 的某个字节/位）。
把该字段的运行时值与真狗/菜单7 场景对比。

### 步骤 3：修

优先级：
1. **如果是 emu 缺应答/状态** → 补仿真器（首选，保持原版 exe）
2. **如果是程序依赖真实用户动作**（如必须先选一次"输出设置"页）→ 在测试脚本里先做那个动作
3. **最后才考虑 patch exe**（并记录到本文档「补丁清单」）

### 步骤 4：验证导出

```
- 菜单 12 预览 → 等 75s → 菜单 13 停止
- 菜单 16 导出 → 等 60s
- 检查 C:\bio\out.tif 是否生成
- 生成后：
  python tools/compare_tiff.py C:\bio\out.tif "test/0.../*.tif"
  （或 tools/tifpixdiff.py / tools/psdinfo.py）
```

真狗基准：TIFF 6,899,708 B，RGB 1969×1168。

### 步骤 5：导出 PSD（菜单 17）

真狗基准：1,067,414,910 B，4370×5197，11 层 `ghm01..ghm11`，5 通道/层。

---

## 六、禁忌 / 已知坑

1. **不要用 `cmykdrop/cmyktiff2_cap.dll` 替换 emu DLL** —— cap 只记录不应答，狗检测会失败。
2. **不要重复已验证的路径**（狗检测/导入/预览/回放对齐）。
3. **不要删除 `_work/emu1/_dongle.log` 之外的证据**；每次实验前清 log 便于判读。
4. **改 exe 前先备份**（`cp exe exe.bak-<时间>`），并确认目标字节。
5. **VA 与文件偏移换算**：CODE 段 `off = VA - 0x400000 - 0xC00`；
   DATA 段 `off = VA - 0x400000 - 0x115000 + 0x113800`。
6. **hwbp32p 的探针寄存器读数可能滞后**（GATE2 曾读到 al=1 实际为 0）——
   以「后续地址是否命中」作为判据，不要只信单点寄存器。
7. **零长度写（dtl=0）必须 ACK 但不消耗 replay 索引**——已修，不要回退。
8. 进程残留：每次实验前
   `powershell -NoProfile -Command 'Get-Process psdto3d101 -ErrorAction SilentlyContinue | Stop-Process -Force'`
9. **【重要】hwbp32p 的执行断点会失效**：同一轮里某个地址命中 2 次后，
   第 3 次可能不再触发（单步异常被 Delphi SEH 吞掉，DR 状态无法恢复）。
   判据：`0x43265E`（Execute 入口）在命令表 `7@8,10@30,16@60` 下命中 **2 次
   （t=8/30）**，而 GATE2（`0x505A71`）在 t=158 确认调用了 Execute —— 说明
   菜单16 的那次 Execute 已执行但断点未触发。
   **因此：所有"零命中"结论都不可信**（`0x505A79`/`0x506132`/`0x506000` 的
   零命中可能只是断点失效）。
   **替代验证手段（按可靠性排序）**：
   a. **IO 日志**：emu1 的 `_dongle.log` 记录 replay/zero-write/cfa/dlg；
      cap 版 DLL（`cmykdrop/cmyktiff2_cap.dll`）记录全部文件/SPT IO
      ——行为不变，且不依赖断点。
   b. **内存标记探针**：探针命中时写一个全局字节（`0x5232F8` 之类未用区），
      跑完用 ReadProcessMemory/日志检查；即使后续断点失效，已写入的标记仍在。
   c. 软件断点（`CC` + 恢复）——hwbp32 未实现，需要自己写。
10. **GATE2 探针的返回值不可信**：曾读到 `al=1`，但后续地址零命中。
    判据应以"行为证据"（对话框是否弹出/文件是否生成/日志）为准，
    不以单点寄存器为准。

---

## 七、进度日志（每次调度追加一行）

| 时间 | 做了什么 | 结果 | 下一步 |
|---|---|---|---|
| 2026-11-21 深夜 | 建立本工作单 | 卡点：Execute 提前退出 | 步骤 1 探针 0x432663 |
| 2026-11-23 00:5x | **主版本切到 2022**；修 `ok3d4.dll`；跑 2022 全流程 | ff-dd 消失；2022 导入仍 AV `0x4FFCB7` | 守卫 `0x4FFCB7` / 真机抓 A5 |

---

## 九、2026-11-23 00:5x 本轮（2022 定为主版本）

### 9.1 目标修正

`docs/GOAL_emu_去狗_持续.md` 的「当前版本」已改为 **`_work/2022emu/` 为主**，
10.1 线（`_work/emu1`）只作对照。理由见 `复盘_基线纠正_2026-11-23.md`。

### 9.2 已完成：`ok3d4.dll` 必须用 10.1 那一份（已烘焙进三个目录）

2022 exe 的 `0x504729` 起有一段自校验：`ok3d1+ok3d4+zu6` 的 dword 之和必须 = `0x7A82A46F`。
2022 自带的 `ok3d4.dll` 算出来是 `7A50A475`（差 `0x3201FA`），换 10.1 的 `ok3d4.dll` 后命中。

已落地（原文件备份为 `ok3d4.dll.2022orig`）：

```
psdto3d2022绿色版/ok3d4.dll
_work/2022emu/ok3d4.dll
_work/2022程序/ok3d4.dll
```

验证：2022 导入 PSD 时不再弹 `ff-dd`，只剩 `0x4FFCB7` 的 AV。

### 9.3 2022 剩下的卡点：`0x4FFCB7`（非狗）

```
004FF8AD  mov dl,1
004FF8AF  mov eax,[0x424C88]      ; 类 VMT
004FF8B4  call 0x42B6E4           ; 构造
004FF8B9  mov [ebp-0x40],eax      ; 对象
...
004FFCB4  mov eax,[ebp-0x40]      ; NULL
004FFCB7  mov ecx,[eax]           ; AV
```

函数内还有 `\g1.bmp`、`ly`、`lyt`、`gx`、`gxt`、`xgx`、`xgxt`、`.gjs` 等常量，
是图层/预览文件那一套。10.1 里没有这段路径，所以 10.1 不崩。

### 9.4 试过但无效/需另法

| 尝试 | 结果 |
|---|---|
| 把临时目录名改成 `C:\ok3dtmp\`（避免 `C:\ok3dtemp\\` 双分隔符） | 仍 AV `0x4FFCB7`，与本问题无关（可用 `tools/retarget_temp.py` 复现） |
| 把 2022 的 `cmyktiff2.dll` 当作 `cmyktiff2_real.dll` 塞进 10.1 的 emu1 再导出 | 产出 **332 字节**（仅头部，且仍是 `55 47 A7 01` UG 变体），说明"烘焙值"是按 10.1 的调用序列算的，换库不通用；已归档 `_work/emu1/_probe_2022dll_out.tif` |

### 9.5 结论与下一步

1. **狗侧（2022）已经通**：启动 → 狗检测 → 三个 replay 会话（idx 0…12）→ 校验和 → 菜单可用。
2. 导出几何 `X1/X2` 仍缺真机 DLL 侧 A5 应答 —— 这是**唯一必须真机**的环节
   （`_work/realcap/` 抓包套件已就绪：插狗 → 跑 exe → 预览 → 导出 TIFF → 回传 `_dongle.log`）。
3. 本地可继续的两件事：
   a. 在 `0x4FFCB4` 前加 `eax==0 → 跳过` 的守卫，让 2022 导入先跑通（不改正常路径）；
   b. 把仿真器的几何注入改成"按真实 DLL 的版本选常量"，而不是硬编码 10.1 的一组。

---

## 八、2026-11-23 夜间跟进（lead 会话）

### 8.1 本轮做了什么

- 复核基线纠正：`_work/2022emu/` 已按 `复盘_基线纠正_2026-11-23.md` 搭好
  （2022 的 `psdto3d101.exe` 1,584,140 B + 仿真器 `cmyktiff2.dll` + 真库改名 `cmyktiff2_real.dll`）。
- 用 `tools/emu_flow.py`、新写的 `tools/flow_timeline.py` 跑 2022 的完整流程
  （导入 PSD → 导入设置 → 预览 → 导出），并抓了每个对话框。

### 8.2 实测结果（2022 基线）

```
t=10  SEND menu 7  (导入 PSD)
t=11  DIALOG TMessageForm  "ff-dd"                    ← 2022 独有校验
t=12  DIALOG TMessageForm  （第二个，未截到文本）
t=14  #32770  Access violation at 004FFCB7 … Read of address 00000000
导出：C:\bio\out2022.tif 不存在
```

启动 / 狗检测 / 回放都正常（`EMU replay W/R idx=0..12`），
`EMU DIFF addr=01F0` 有 20+ 个 dword 与抓包不同（多数是栈指针噪声）。

### 8.3 `ff-dd` 是什么（已定位）

2022 exe 的 `0x504729`–`0x504750`：

```
00504729  cmp  [0x52328C], 0          ; 三个计数器都必须非 0
00504730  je   0x50475A
00504732  cmp  [0x523290], 0
00504739  je   0x50475A
0050473B  cmp  [0x523294], 0
00504742  je   0x50475A
00504744  cmp  [0x523288], 0x7A82A46F ; ★ 三者之和必须等于这个魔数
0050474E  je   0x50475A
00504750  mov  eax, 0x505374           ; "ff-dd"
00504755  call ShowMessage
0050475A  mov  byte [0x5230CA], 1      ; 无论过不过都置 1
```

* `ff-dd` 在 **10.1 的 exe 里根本不存在**（`find(b'ff-dd')` 未命中），是 2022 新增的完整性校验；
* 校验失败后程序**继续执行**，但 `[ebp-0x40]` 没有被赋值，
  下次使用时 `004FFCB7  mov ecx,[eax]`（eax = NULL）→ AV。

### 8.4 结论与下一步

1. 2022 的"导入失败"不是 PSD 读不了，而是**这条新校验没过**，随后带着空对象继续跑。
2. 解法（按推荐顺序）：
   a. **让仿真器满足校验**：查清 `[0x52328C]/[0x523290]/[0x523294]` 的来源（大概率仍来自狗记录），
      让三者之和 = `0x7A82A46F`；
   b. **守卫补丁**：`0x504744` 的比较改成恒等（或 `0x50474E` 的 `je` 改 `jmp`），
      并在 `0x4FFCB7` 前加 `eax==0` 跳过，先把流程跑通；
   c. 按 b 跑通导出、比对基准 TIFF 的头与像素，再回头做 a（保持"原版 exe 最小补丁"）。
3. 附带记录：`tools/flow_timeline.py` 是本轮新增的时间线工具（标题 / 对话框 / 临时目录变化），
   后续所有长流程调试都用它，比单点断点可靠。

### 8.5 已修好一半：`ff-dd` 的真实含义是**三个 DLL 的 dword 校验和**

`0x5045D0`–`0x5046F5` 的三段循环把 `ok3d1.dll`、`ok3d4.dll`、`zu6.dll` 逐 dword 累加：

```
count = size / 4
for i := count-1 downto 0:  read 4 bytes;  sum += dword
[0x52328C] + [0x523290] + [0x523294]  必须等于 0x7A82A46F
```

**实算（Python 复现该算法）**：

| 目录 | ok3d1 | ok3d4 | zu6 | 合计 | 与魔数 |
|---|---|---|---|---|---|
| `psdto3d10.1绿色版` | 575908568 | 3324295586 | 2450145269 | **7A82A46F** | ✅ 命中 |
| `psdto3d2022绿色版` | 575908568 | 3321018792 | 2450145269 | 7A50A475 | ❌ 差 0x3201FA |

⇒ **2022 的 exe 期望的是 10.1 那套 DLL**（`ok3d4.dll` 内容不同、大小相同）。
把 10.1 的 `ok3d4.dll` 拷进 `_work/2022emu/` 后：

* 三个计数器的和 = `7A82A46F` ✅
* **"ff-dd" 弹框消失**（不再出现那两个 TMessageForm）

### 8.6 仍剩一个非狗问题：`0x4FFCB7`

```
t≈14  #32770  Access violation at 004FFCB7 … Read of address 00000000
```

```
004FF8AF  mov dl,1
004FF8B4  mov eax,[0x424C88]        ; 某全局组件
004FF8B7  call 0x42B6E4             ; ← 返回对象，存到 [ebp-0x40]
004FF8B9  mov [ebp-0x40], eax
...
004FFCB4  mov eax,[ebp-0x40]        ; ← 这里 eax = NULL
004FFCB7  mov ecx,[eax]             ; AV
004FFCB9  call [ecx+0x4C]           ; 虚方法
```

即 `0x42B6E4` 返回了 NULL。10.1 的执行同样的导入流程不崩，
说明这是 **2022 构建独有**的一条路径（很可能是那个被扩展过的 DFM/组件没初始化）。

**下一步（按顺序）**：

1. 反汇编 `0x42B6E4`（`[0x424C88]` 的取值 + 它返回哪个对象），确认这个组件是什么；
2. 对比 `psdto3d101.exe.pre_dfm`（1,584,128 B）与当前 1,584,140 B 的 DFM 差异，
   看是否有新增/缺失的窗体或控件依赖；
3. 若不是组件问题，则在 `0x4FFCB4` 前加 `eax==0 → 跳过整段` 的守卫，
   让导入继续（并记录到补丁清单）。
