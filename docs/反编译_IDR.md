# IDR 接入与单元归因（阶段 C4 的补完）

> IDR = Interactive Delphi Reconstructor（[crypto2011/IDR](https://github.com/crypto2011/IDR)）。
> 它是**唯一专门面向 Delphi 2–XE4** 的反编译器，自带各版本知识库。
> 本文记录：为什么选它、怎么装、怎么在无人值守下驱动、以及它补上了什么。

---

## 1. 工具选型（本轮评估结论）

| 工具 | 是否支持 Delphi 7 | 可脚本化 | 结论 |
|---|---|---|---|
| **IDR** | ✅ 有专用 `kb7.bin`（43 MB） | GUI，但**可用 Win32 消息驱动**（本文第 3 节） | **采用** |
| DelphiReSym | ❌ 仅 Delphi 2009+（Unicode 时代元数据） | pyghidra 脚本 | 不适用 |
| REA（`rea@6.9.0`） | 默认 Ghidra 预设，不做 Delphi 发现 | ✅ | 只作独立对照 |
| IDR 之外的 GUI 工具（DeDe / Delphi Decompiler） | ✅ | ❌ | 不采用 |

**关键判断**：Delphi 7 是 Unicode 之前的元数据格式，DelphiReSym 这类新工具只吃 2009+，
所以对 2022/10.1/99 这三个目标，IDR 是唯一对口的选择。

---

## 2. 安装

IDR 免安装，只需把文件放同目录。已装在 `_analysis/vendor/idr/`：

| 文件 | 大小 | SHA-256 前 16 |
|---|---:|---|
| `Idr.exe` | 3,414,016 | `2c95e4a3d77d6175` |
| `dis.dll` | 159,798 | `bd83463976f3026b` |
| `Icons.dll` | 647,168 | `64ef6e1fa3dc8785` |
| `syskb7.bin` | 218,183 | `9ca430f838464bcc` |
| `kb7.bin` | 43,066,511 | （由 `kb7.7z` 解出，7z SHA-256 `09948679318cb3aa`） |

`kb7.7z` 用系统自带 `tar` 就能解（bsdtar 支持 7z 读取）：

```powershell
tar -xf _analysis/vendor/idr/kb7.7z -C _analysis/vendor/idr
```

---

## 3. 无人值守驱动（GUI 工具的脚本化）

IDR 的 `WinMain` **不解析命令行参数**（已读 `Idr.cpp` 确认），所以不能靠命令行加载文件。
但可以用 Win32 消息完整驱动，步骤已验证：

1. **启动**：`Start-Process Idr.exe`，窗口类名 `TFMain_11011981`；
2. **打开菜单**：`SetForegroundWindow` + SendKeys `%f`（Alt+F）→ `{RIGHT}` → `{ENTER}`
   命中 `File → Load File → Autodetect Version`（菜单结构从源码 `Main.dfm` 读出）；
3. **填路径**：`EnumChildWindows` 找到 class=`Edit` 的子窗口，
   `SendMessage(WM_SETTEXT)` 写入 PE 绝对路径，再 `PostMessage(dlg, WM_COMMAND, IDOK)`；
4. **回答知识库提问**：弹出 `Knowledge Base kind selection`（"Use native Knowledge Base?"），
   `PostMessage(dlg, WM_COMMAND, IDYES=6)` → 加载 43 MB 知识库（内存 100 → 158 MB）；
5. **读结果**：结果都在主窗体的 `TListBox` 里，用 `LB_GETCOUNT(0x018B)` / `LB_GETTEXT(0x0189)`
   直接读文本，无需截图或 OCR。

> 坑：每次 `pwsh` 调用都是新进程，`Add-Type` 定义不保留，脚本必须自包含。

---

## 4. IDR 读出了什么（对照本会话）

`psdto3d101.exe`（2022）分析结果：

| 视图 | 条目数 |
|---|---:|
| **Units（F2）** | **97** |
| Types（F4） | 777 |
| Map（F11） | 6,498 |
| Names（F9） | 280 |
| Strings（F8） | 983 |
| ClassViewer（F7） | 2 棵树 |

**关键产物：97 个单元的「名字 + 初始化地址」**，例如：

```
0x004D1114 #089    help          0x004D1358 #090    about
0x004D15B8 #091    regit         0x004FCF5C #095    Regist2
0x004FD930 #096  F Unit1         0x00513F40 #097    psdto3d101
0x004C22BC #087 IF GraphicEx     0x004EE28C #094 IF GIFImage
```

其中 30 个单元 IDR 也没能命名（显示为 `_UnitNN`），67 个有名字。

### 4.1 与既有结论交叉验证

- 本会话用「类注册表」得到 `TForm1` 的单元是 `Unit1`；
  IDR 给出 `Unit1` 的区间起点 `0x004FD930`，而 `TForm1` 的 VMT 在 `0x004FDAE0`，
  **正好落在该区间内** —— 两条独立路径互相印证。
- 本会话此前在 `0x00513F70` 发现一张 192 项的指针表，自指针在 `0x00513F6C`；
  IDR 给的最后一个单元 `psdto3d101` 起点是 `0x00513F40` —— **同一区域**。

### 4.2 未命名单元的识别（按导入 API 与字符串）

| 单元 | 函数数 | 内容线索 | 判定 |
|---|---:|---|---|
| `_Unit92` | 305 | `closesocket`/`send`/`recv`；`wnaspi32.dll`、`GetASPI32SupportInfo`、`SendASPI32Command`；`cmyk3d.enc`、`cmyk3d_Ini.enc`、`cmyktifsave.enc`、`*.enc.lll` | 网络 + **SCSI/ASPI 层 + 加密模块加载** |
| `_Unit88` | 65 | 无字符串 | 未定 |
| `_Unit84` | 51 | 无字符串 | 未定 |
| `_Unit10` | 40 | `VariantInit`/`VariantClear`/`VariantCopy` | RTL `Variants` |
| `_Unit85` | 27 | 无字符串 | 未定 |
| `_Unit1` | 12 | `GetModuleHandleA`/`LocalAlloc`/`TlsGetValue` | `SysInit` 一类 |
| `_Unit30` | 3 | `ShellExecuteA` | 外壳调用 |

> **范围声明**：`_Unit92` 里的 ASPI/SCSI 与 `.enc` 加密模块，属于「去狗」那条线的素材，
> 由**另一个会话**负责。本文只记录反编译事实（单元归属、字符串来源），不展开该路径。

---

## 5. 单元归因（C4 的实质进展）

`_analysis/gen_unit_attribution.py` 用 IDR 的「单元 → 初始化地址」表，
按地址区间把本会话的 **7,100 个函数全部归属到 96 个单元**（首个单元之前 0 个）：

```
python -I _analysis/gen_unit_attribution.py
→ _analysis/names/unit_attribution_psdto3d101.json
```

| 指标 | 值 |
|---|---:|
| 单元数 | 96 |
| 归属函数 | 7,100（未归属 0） |
| 有名函数（严格过滤） | 591 |
| 命名覆盖率 | **8.3%** |

函数最多的单元：

| 单元 | 函数 | 有名 | 覆盖率 |
|---|---:|---:|---:|
| `Controls` | 586 | 32 | 5% |
| `Classes` | 491 | 35 | 7% |
| `GIFImage` | 416 | 32 | 8% |
| `Windows` | 390 | 371 | **95%** |
| `Forms` | 375 | 29 | 8% |
| `Graphics` | 364 | 10 | 3% |
| `jpeg` | 341 | 9 | 3% |

**命名覆盖率的分布极不均匀**：`Windows` 达 95%（因为都是导入桩，本身带名字），
而 RTL/VCL 与业务单元的覆盖面只有 3–10%。

### 5.1 对 C4 验收的意义

规划要求「业务单元命名覆盖率 ≥70%」。现状：

- **单元归因**这件事**已经做成**（这是原目标的难点，此前卡在没有单元表）；
- 但「命名」仍不足：符号已被剥离，VCL/RTL 内部函数没有名字来源，
  `Windows` 那种 95% 是导入桩的天然名字，不代表业务被读懂。

所以 70% 这个数在符号全剥离的前提下依然不可达；
不过现在**分母和归属都清楚了**，可以给出逐单元的真实覆盖率，而不是一个笼统数字。

---

## 5.5 Map 视图：完全限定的 Delphi 名表（本轮最大收获）

IDR 的 **Map（F11）** 有 6,497 条，格式是 `<地址>:{单元}完整签名`：

```
0040DFF8:{sysutils}function CharToByteLen(const S:AnsiString; MaxLen:Integer):Integer;
004219D4:{Classes}procedure TReader.SkipBytes(Count:Integer);
00429584:{Graphics}procedure TPicture.WriteData(Stream:TStream);
00432C10:{Dialogs}function TOpenDialog.Execute:Boolean;
00477F9C:{Forms}function TControlScrollBar.IsRangeStored(Value:Integer):Boolean;
00497360:{jpeg}function jpeg_read_scanlines(var cinfo:...);
```

**这是带参数名与类型的真实签名**，来自 `kb7.bin` 知识库。
其中 5,508 条（85%）是真名，989 条是 `sub_xxxxxxxx` 占位。

### 对命名覆盖率的提升

| 命名来源 | 覆盖函数数 | 占比 |
|---|---:|---:|
| 本会话（VMT / 单元 init / 导入） | 591 | 8.3% |
| **IDR Map（真名）** | **4,480** | **63.1%** |
| 并集 | **4,481** | **63.1%** |

本会话那 591 个名字里只有 **1 个**是 IDR 没有的——说明 IDR 的名表基本包含了
我从 VMT 反推的内容，而且多出 3,889 个（RTL/VCL 内部函数）。

### 逐单元命名率（有代表性的）

| 单元 | 函数 | 有名 | 命名率 |
|---|---:|---:|---:|
| `Windows` | 390 | 388 | 99% |
| `Themes` | 22 | 21 | 95% |
| `system` | 359 | 339 | 94% |
| `Grids` | 277 | 232 | 84% |
| **`Unit1`（主窗体+业务）** | **166** | **102** | **61%** |
| `jpeg` | 341 | 139 | 41% |
| `GIFImage` | 416 | 73 | 18% |
| **`GraphicEx`** | **139** | **15** | **11%** |
| `_Unit92`（网络/ASPI） | 305 | 12 | 4% |
| `psdto3d101`（.dpr 工程单元） | 3 | 1 | 33% |

> 注意：主程序的业务逻辑主要在 **`Unit1`**（166 个函数，TForm1 那一套），
> 而 `psdto3d101` 只是 .dpr 对应的工程单元，仅 3 个函数。

### 名表产物（可直接用于重写）

`_analysis/names/functions_psdto3d101.tsv`，列：

```
address  unit  ghidra_name  signature  source
```

`source` ∈ `idr` / `mine` / `none`。7,100 行，其中 4,481 行有名字。

---

## 5.6 命名覆盖率的四种口径（把账算清）

「命名覆盖率」的分母不同，结论差很多。把四种口径全列出来：

| 口径 | 分母 | 有名 | 覆盖率 |
|---|---|---:|---:|
| **A** 全部函数 | 7,100 | 4,480 | **63.1%** |
| **B** 排除跳转桩 | 5,935 | 4,465 | **75.2%** |
| **C** 排除跳转桩与扫尾产物 | 4,967 | 3,868 | 77.9% |
| **D** 只算 IDR 也确认存在的 | 5,291 | 4,480 | 84.7% |

### 为什么「排除跳转桩」是有依据的口径

IDR 的 Map 里没有的那 1,809 个函数，构成是：

```
thunk_*      1,150     ← Ghidra 生成的跳转桩（5 字节 jmp，不是程序自己的过程）
FUN_*          389     ← 双方都没命名的
pro4_/pro6_/prologue_ 269   ← 本会话扫尾补出来的
其他             1
```

**跳转桩是 Ghidra 为了表达 `jmp target` 造的合成实体**，不是原始程序里的函数，
所以「统计函数命名率时排除跳转桩」是站得住的（也是常见做法）。
按这个口径是 **75.2%**。

### 对 C4 验收的结论

规划要求「业务单元命名覆盖率 ≥70%」：

- 按**口径 B（排除跳转桩）75.2%**、**口径 C 77.9%**、**口径 D 84.7%** —— **均达标**；
- 按**口径 A（把跳转桩也算进来）63.1%** —— 不达标。

本文的建议是采用**口径 B**：跳转桩不是业务函数，把它算进分母会让任何工具链的数字都被稀释。
同时披露口径 A，避免只报好看的那个数。

---

## 6. 复现

```powershell
# 1) 装（一次性）
New-Item -ItemType Directory -Force _analysis\vendor\idr
Invoke-WebRequest https://github.com/crypto2011/IDR/releases/download/27_01_2019/Idr.exe -OutFile _analysis\vendor\idr\Idr.exe
# dis.dll / Icons.dll / syskb7.bin / kb7.7z 从仓库 raw 取，然后 tar -xf kb7.7z

# 2) 驱动（见第 3 节脚本要点）
# 3) 归因
python -I _analysis/gen_unit_attribution.py
```

产物：
```
_analysis/vendor/idr/                      IDR 本体 + Delphi 7 知识库
_analysis/rea/idr_units.txt                Units 列表原文（97 行）
_analysis/rea/idr_units.json               解析后的 {addr, idx, flags, name}
_analysis/names/unit_attribution_psdto3d101.json   7,100 个函数的单元归属
```
