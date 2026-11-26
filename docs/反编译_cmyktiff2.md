# cmyktiff2.dll 反编译说明

> 依据 `docs/反编译规划.md` 阶段 D。
> 语料：`_analysis/dump_cmyktiff2_g/`（3,804 个函数，0 失败，Sweep2+尺寸下限扫尾）
> 证据等级：A = 二进制结构直接可见；B = 静态可见的调用点/数据；C = 推导自洽；D = 假设。

---

## 1. 模块概况

| 项 | 值 |
|---|---|
| 文件 | `Psdto3d/cmyktiff2.dll` |
| SHA-256 前缀 | `1c785203` |
| 代码段 | 534,016 B |
| 导出 | 7 个 |
| 函数语料 | 3,804 个（代码口径覆盖 92.0%） |
| PACKAGEINFO 业务单元 | 26 个（含 `YStrUtils`） |

导出（A 级，见 `docs/反编译_ABI.md`）：
`JpgToBmp`、`bmptotiff`、`gettiffinfo`、`mergtotiff`、`rgbtocmykbmp`、`savetiff00`、`tifftobmp`。

**主程序只静态导入了其中两个**：`bmptotiff`、`mergtotiff`（B 级，IAT 见 ABI 文档）。

---

## 2. `mergtotiff`（`0x47F720`，14,862 B / 1,814 行）

> **两处度量差异，供交叉核对时参考**：
>
> | 度量 | 本会话语料 | 另一工具（`ghidra_cli` / ghidra-headless-mcp） |
> |---|---|---|
> | 函数体字节 | **14,862**（`index.tsv` 的 `size`） | 15,246（`body_end 0x4832AE` − `body_start 0x47F720`） |
> | 反编译行数 | **1,814**（`dump_cmyktiff2_h/0047f720.c`，`_g` 与 `_h` 两个语料一致） | 3,646（含其特有的类型/注释排版） |
>
> 字节差 384 B 应是 `body_end` 把尾部对齐填充算进来了；行数差来自反编译器的排版策略不同。
> **起始地址 `0x47F720` 两者一致**，引用行号时以本文的 1,814 行口径为准。

### 2.1 一句话

把四张 CMYK 分色 TIFF（`g_c/g_M/g_Y/g_K.tif` 与 `_c/_M/_Y/_K.tif`）交给外部
`rip3d.dll` 的 `stai` 函数合并，本函数只负责准备句柄、控制两种模式、驱动进度条与消息泵。

**这是本次反编译最重要的发现之一（B 级）**：`cmyktiff2` 的合并核心并不在自己体内，
而是运行时加载 `rip3d.dll` 并 `GetProcAddress(..., "stai")`。重写时必须一并实现 `stai`。

### 2.2 字符串证据（A 级，来自函数体字面量）

```
行 327   "\cmyk.dll"     行 329   "\3d.dll"      行 331   "\ok3d4.dll"
行 356   "rip3d.dll"     行 359   "stai"
行 625   "g_c.tif"       行 628   "g_M.tif"      行 631   "g_Y.tif"   行 634   "g_K.tif"
行 1302  "_c.tif"        行 1305  "_M.tif"       行 1308  "_Y.tif"    行 1311  "_K.tif"
```

### 2.3 结构地图（行号对应 `_analysis/dump_cmyktiff2_g/0047f720.c`）

| 行段 | 内容 | 等级 |
|---|---|---|
| 2–218 | 局部变量声明（含大量 `extraout_ECX/EDX_*`，Ghidra 对寄存器传参的还原产物） | A |
| 219 | 第一条可执行语句 `iVar11 = 0x5c;`（92 = `'\'`，用作路径分隔符） | A |
| 322–325 | 用 `PTR_LAB_0041246c` 类创建 3 个实例；`FUN_00435bd4` 取当前模块路径 | B |
| 327–332 | 依次拼出 `\cmyk.dll`、`\3d.dll`、`\ok3d4.dll` 并 `FUN_0041641c(实例, 路径)` 载入 | B |
| 333–335 | 对三个实例做**虚表首项调用** `(**code)**(*piVar3)()` —— 各自的初始化入口 | B |
| 336–340 | `local_124` 取负时加 3 再 `>> 2`，即 `(n+3)/4` 向上取整 | C |
| 342–349 | 循环 `(n+3)/4` 次，每次从 ok3d4 实例取 4 字节累加到 `local_120` | B |
| 350–351 | `local_114 -= local_120`；`local_118 -= local_124` | B |
| 356–359 | `LoadLibrary("rip3d.dll")` + `GetProcAddress(..., "stai")` → `local_1ec` | **B** |
| 361–362 | `local_114 += 0xC6249808`；`local_118 += 0x39C18`（常量补偿，语义待定） | C |
| 365–369 | 4 次 `FUN_0040521c(dst, &DAT_0047f64c, 1, local_114)` —— 常量表填充 | C |
| 620–635 | 打开 `g_c/g_M/g_Y/g_K.tif`（`FUN_00416170` = TIFF 对象构造） | B |
| 640–657 | **第一轮合并**：4 次调用 `(*local_1ec)()`，参数 `uStackY_a4 = 1` | **B** |
| 652 | `local_160 = (*local_1ec)()` —— `stai` 返回值即本轮结果码 | B |
| 654 | `FUN_00427c04(callback, i*5 + 0x19)` —— 进度条（步长 5，起点 25） | B |
| 658–659 | 消息泵 `FUN_0043559c` + 窗口刷新 `FUN_004337c0` | B |
| 1300–1312 | 打开 `_c/_M/_Y/_K.tif` | B |
| 1317–1331 | **第二轮合并**：同样 4 次 `(*local_1ec)()`，参数 `uStackY_a4 = 0` | **B** |
| 1334–1339 | 再按 `in_stack_00000028` 次循环填充缓冲 | C |

### 2.4 `stai` 的实参（B 级，逐行可见）

第一轮（`g_*`，`uStackY_a4 = 1`）：

```
uStackY_90 = ROUND(in_stack_0000000C:in_stack_00000008 / local_2ac)   ; 尺寸/比例
uStackY_9c = local_110                                                ; 偏移或行数
uStackY_a0 = local_114                                                ; 宽（或高）
uStackY_a4 = 1                                                        ; 模式 1
ppiStackY_a8 = local_22c                                              ; 指向 4 个 TIFF 句柄数组
```

第二轮（`_*`，`uStackY_a4 = 0`）参数同形，只是 `uStackY_90` 不做除法、`uStackY_9c = local_118`、
`a4 = 0`。

**推断（C 级）**：`a4` 是「是否按 `local_2ac` 缩放」的开关；`a8` 指向的四元素数组
就是 C/M/Y/K 四个通道的 TIFF 对象。`stai` 在 `rip3d.dll` 内，签名与实现尚未分析。

### 2.5 被调函数性质（B 级，逐个看过函数体）

| 地址 | 调用次数 | 性质 |
|---|---:|---|
| `0x40521C` | 34 | 5 行薄封装，转 `0x405090`（常量/缓冲填充） |
| `0x416170` | 12 | TIFF 对象构造（23 行，含 SEH） |
| `0x427C04` | 18 | 进度条更新（`HWND` + `SendMessage`） |
| `0x4337C0` | 6 | 窗口/坐标操作（`POINT`、`GetCursorPos` 类） |
| `0x43559C` | 16 | 消息泵（`tagMSG` 循环） |
| `0x415F20` | — | TIFF 对象虚方法薄封装（13 行） |

---

## 3. `savetiff00`（`0x47E9D0`，2,626 B / 258 行）

### 3.1 签名（B 级）

```c
void savetiff00(int *param_1, ushort param_2)
```

`param_1` 是**流/文件对象**——258 行里 76 次调用都把它作为第一个实参传给
`FUN_00415F20(obj, buf, len)`；`param_2` 是**模式值**，见 3.3。

### 3.2 它就是 TIFF 写入器（B 级）

`FUN_00415F20` 是对象的虚方法薄封装（13 行，走虚表槽），语义为「写入 len 字节」。
函数体内的写入序列呈现典型的 **IFD 目录项**节奏：

```
写 2 字节（tag）
写 2 字节（type）
写 4 字节（count）
写 4 字节（value）
… 重复 12 次 …
for (i = 0xf; i != 0; i--) { … }        // 行 228，循环 15 次
写 0x3c = 60 字节                        // 行 233
写 0x14 = 20 字节                        // 行 250
```

### 3.3 `param_2` 的语义（B 级）

行 93–98：

```c
if (param_2 == 3) { local_c = CONCAT22(local_c._2_2_, 3); }
else              { local_c = CONCAT22(local_c._2_2_, 4); }
```

即 `param_2 == 3` 时写 3，否则写 4。结合本 DLL 的用途（CMYK），
**推断 `param_2` 是每像素采样数：3 = RGB，4 = CMYK**（C 级）。

### 3.4 标签号是「字符串形式的十进制数」（A 级）

行 53–60 把 8 个常量地址装进结构；读这些地址的实际字节：

```
0x47F42C  "18261"   0x47F43C  "423"    0x47F448  "1"     0x47F454  "259"
0x47F460  "19"      0x47F46C  "274"    0x47F478  "3d99"  0x47F488  "ok3d"
```

- `259` = **Compression**、`274` = **Orientation**，是标准 TIFF 标签号；
- `3d99` / `ok3d` 是**软件标识字符串**（通常写进 Software 标签 305）；
- 标签号以**十进制字符串**形式存在于二进制里，说明原码用了 `StrToInt('259')` 之类写法。

配合 `FUN_00408480`（14 行，调用 `FUN_00402d28` 做字符串→整数转换并在失败时抛异常），
可以确认这条「字符串→标签号→写入」的路径。

---

## 4. `gettiffinfo`（`0x47E10C`，296 B / 65 行）

> **第 51 轮用独立工具复核过（A 级）**：`ghidra_cli` 的反编译与本节的逐行描述**完全一致**——
> `TFileStream.Create` → `SetPosition(8)` → 读 2 字节得 IFD 条目数 → 默认值 `0/0/4/1/0` →
> 循环读 `tag(2)/type(2)/count(4)/value(4)` → 只认 `0x100/0x101/0x102/0x103/0x111` 五个标签。
> 其中 `0x102` 取的是 count 字段的低 16 位（`local_8[0]`），本节写作 `value(16)` 也吻合。

### 4.1 完整逻辑（B 级，65 行已逐行读完）

```c
FUN_00404574(filename);                                   // 文件名校验/转换
obj = FUN_00416170(&PTR_LAB_0041237c, 1, filename, 0);    // 打开 TIFF 对象
FUN_00415cdc(obj, …, 8, 0);                               // 定位到偏移 8（跳过 TIFF 头）
FUN_00415ee8(obj, &n, 2);                                 // 读 2 字节 = IFD 条目数
*out1 = 0; *out2 = 0; *out3 = 4; *out4 = 1; *out5 = 0;
for (i = n; i != 0; i--) {
    读 2 字节 → tag
    读 2 字节 → type
    读 4 字节 → count
    读 4 字节 → value
    switch (tag) {
      case 0x100: *out1 = value;      break;
      case 0x101: *out2 = value;      break;
      case 0x102: *out3 = value(16);  break;
      case 0x103: *out4 = value;      break;
      case 0x111: *out5 = value;      break;
    }
}
```

### 4.2 五个输出参数的含义（B 级）

| 标签 | 标准名 | 输出到 |
|---|---|---|
| `0x100` | ImageWidth | 第 1 个栈参数 |
| `0x101` | ImageLength（高） | 第 2 个 |
| `0x102` | BitsPerSample | 第 3 个（初值 4） |
| `0x103` | Compression | 第 4 个（初值 1） |
| `0x111` | StripOffsets | 第 5 个 |

因此 `gettiffinfo` 的真实签名应为：

```c
void gettiffinfo(const char *filename,
                 int *width, int *height, int *bitsPerSample,
                 int *compression, int *stripOffsets)
```

（前 4 个初值 `0/0/4/1/0` 说明 `bits=4`、`compression=1` 是缺省值，
与 CMYK 4 通道、无压缩一致 —— 这与 `savetiff00` 里 `param_2` 的 3/4 取值互相印证。）

> 这一节推翻了本文早期版本对 `gettiffinfo` 的「D 级推测」：当时只说「5 次调用疑为读头字段」，
> 现在是**逐行的完整解析**，且与 TIFF 标准标签号一一对应。

---

## 4.5 其余四个导出（B 级，逐个读完）

### 4.5.1 先确立四个辅助函数的身份

这四类调用在四个导出里反复出现，先把它们钉死：

| 地址 | 行数 | 判定 | 依据 |
|---|---:|---|---|
| `FUN_00421848` | 30 | **`TBitmap.Create`** | 构造函数形态，返回位图对象 |
| `FUN_00422dc0` | 89 | **设 `PixelFormat`**（重建 DIB） | 内部操作 `HDC` / `HBITMAP`，参数是 `byte` |
| `FUN_00421f80` | 17 | **`TBitmap.ScanLine[y]`** | 取 `param_1[10]` 作扫描线数组并做越界检查 |
| `FUN_00415F20` / `FUN_00415EE8` | 13 / 13 | **流写入 / 流读取** | 虚表薄封装，`(obj, buf, len)` |

`FUN_00422dc0` 的第二个参数取值只有 3、6、7，与 Delphi 的 `TPixelFormat` 完全对应：

| 值 | `TPixelFormat` |
|---:|---|
| 3 | `pf8bit` |
| 6 | `pf24bit` |
| 7 | `pf32bit` |

### 4.5.2 `JpgToBmp`（`0x47E4B0`，31 行，115 B）

```c
void JpgToBmp(const char *filename, TBitmap **out)
```

流程：文件名校验 → `TBitmap.Create` → 结果写入 `*out` → `PixelFormat = 6 (pf24bit)`
→ 建 JPEG 对象 → 虚表 `+8` 调用（`bitmap.Assign(jpeg)`）→ 释放 JPEG。

即 **JPEG 解码到位图**，24 位。

### 4.5.3 `rgbtocmykbmp`（`0x47E530`，122 行，483 B）

```c
void rgbtocmykbmp(const char *filename, TBitmap **out)
```

流程：文件名校验 → 用 `FUN_00408964` / `FUN_00408064` / `FUN_004044d0` 把输入名**改成
`.jpeg` 后缀**（字面量 `".jpeg"` 在函数体内）→ 建 JPEG 源（`PixelFormat = 6`）
→ 再 `TBitmap.Create` 输出图（`PixelFormat = 7 = pf32bit`）→ 虚表 `+0x40`、`+0x34`
两次调用设宽高 → 两次 `ScanLine` 逐行搬运。

**`pf32bit` 正对应 CMYK 四通道**，与 `savetiff00` 里 `param_2 == 4` 的取值互相印证。

### 4.5.4 `bmptotiff`（`0x47E270`，119 行，532 B）

```c
void bmptotiff(const char *in_bmp, const char *out_tiff, int mode)
```

流程：

```
FUN_00404574(filename)                                   // 文件名校验
FUN_00416170(&PTR_LAB_0041237c, 1, filename, 0xFFFF)     // 打开 TIFF 用于写出
LoadLibrary("rip3d.dll") + GetProcAddress("stai")        // ← 与 mergtotiff 同一委派
三段：ScanLine 取行 → 分别写出  1× / 3× / 4× 字节量
```

三段写入的字节数是 `iVar7`、`iVar6 * 3`、`iVar7 << 2`（= ×4）——正好对应
**单通道 / RGB / CMYK** 三种平面数。真正的格式转换仍落在 `rip3d.dll!stai`。

### 4.5.5 `tifftobmp`（`0x47E744`，125 行，634 B）

```c
void tifftobmp(const char *in_tiff, TBitmap **out)
```

流程：打开 TIFF（读模式）→ `TBitmap.Create` → 三段结构相同的处理：

| 段 | 设的像素格式 | 每次读取字节数 |
|---|---|---|
| 1 | `3`（`pf8bit`） | `local_8` |
| 2 | `7`（`pf32bit`） | `local_8 << 2` |
| 3 | `6`（`pf24bit`） | `local_8 * 3` |

每段都是「改像素格式 → 按对应通道数读一行 → 写进 ScanLine」。

---

## 4.6 IDR 复核结果（第 38 轮）：函数实名与一处更正

用 IDR 分析本 DLL，得到 3,438 条完全限定签名。与本文对照：

| 地址 | 本文判定 | IDR 实名 | 结论 |
|---|---|---|---|
| `0x415F20` | 流写入 | `TStream.WriteBuffer` | ✅ |
| `0x415EE8` | 流读取 | `TStream.ReadBuffer` | ✅ |
| `0x415CDC` | 定位/Seek | `TStream.SetPosition` | ✅ |
| `0x408480` | 字符串→整数 | `StrToInt` | ✅ |
| `0x416170` | **TIFF 对象构造** | **`TFileStream.Create`** | ❌ **更正** |

**更正说明**：第 2 节把 `FUN_00416170` 当成「TIFF 对象构造」，实际是 **`TFileStream.Create`**。
所以 `mergtotiff` / `gettiffinfo` / `savetiff00` 打开的都是**普通文件流**，
后续 `TStream.ReadBuffer` / `WriteBuffer` 直接作用其上——**没有独立的 TIFF 对象层**。

这不改变本文对流程的描述（读写字节、按 TIFF 结构组装），
但重写时应实现成「文件流 + 手写 TIFF 头/目录项」，而不是「TIFF 库对象」。

### 4.6.1 导出约定

七个导出在 IDR 里都是 **`stdcall`**：

```
{cmyktiff2} mergtotiff; stdcall;   {cmyktiff2} savetiff00; stdcall;  …
```

重写时导出声明必须是 `stdcall`（不是 Delphi 内部默认的 `register`）。

### 4.6.2 命名覆盖

| 口径 | 覆盖 | 占比 |
|---|---|---:|
| A 全部函数 | 2,591 / 3,850 | 67.3% |
| **B 排除跳转桩** | 2,591 / 3,328 | **77.9%** |

---

## 4.7 `savetiff00` 实际写入的标签字符串（第 51 轮，A 级）

第 51 轮把 `savetiff00`（`0x47E9D0`）体内载入的字符串常量**逐个从二进制里读了出来**。
函数开头 L59–L66 用 `FUN_0040415c(dst, 常量地址)` 载入 8 个字符串，随后交给
`StrToInt`（`FUN_00408480`，共 6 次调用）转成整数写入流：

| 常量地址 | 字符串 | 转成整数 | 对应 TIFF 标签 |
|---|---|---|---|
| `0x47F454` | `"259"` | 259 = `0x0103` | **Compression** |
| `0x47F46C` | `"274"` | 274 = `0x0112` | **Orientation** |
| `0x47F42C` | `"18261"` | 18261 = `0x4755` | 自定义/私有标签 |
| `0x47F43C` | `"423"` | 423 = `0x01A7` | 自定义 |
| `0x47F448` | `"1"` | 1 | 取值（非标签号） |
| `0x47F460` | `"19"` | 19 = `0x0013` | 自定义 |
| `0x47F478` | `"3d99"` | —（非数字） | **以字符串写入**，产品标识 |
| `0x47F488` | `"ok3d"` | —（非数字） | **以字符串写入**，产品标识 |

### 4.7.1 三条结论

1. **`"259"`/`"274"` 确实存在**，位置 `0x47F454` / `0x47F46C`——
   本文早先说「字符串 `"259"`/`"274"` 交给 `StrToInt`」是对的，但当时没给出地址，
   现在补齐了；
2. `"ok3d"` 确实以字符串写进 **Software 标签**——已由真实产物端到端证实（见 §4.8）；
3. `"18261"`（`0x4755`）落在 TIFF 的私有标签区间，说明作者写了自定义元数据。

> **勘误**：早先本文把这批字符串笼统写成「`"259"`/`"274"` 这些」，
> 让人以为只有两个。实际是 **8 个**，其中 6 个数值型、2 个字符串型。
>
> **工具说明**：`ghidra_cli` 的反编译把这个函数的两个字符串参数误渲染成代码地址
> （`0x47EBC7` 实际在函数自身代码范围内）。判断「是不是字符串」必须以
> **二进制字节 + 地址映射**为准，不能只看反编译文本。

---

## 4.8 真实产物端到端证实（第 52 轮，A 级）

拿 4 个由本程序实际写出的 TIFF 做验证（`归档/实验/_export_test/` 下）：

| 文件 | IFD 条目 | 宽×高 | BitsPerSample | Photometric | SamplesPerPixel |
|---|---:|---|---|---|---|
| `accept.tif` | 15 | 1222×1474 | 8,8,8,8 | **5** | **4** |
| `base.tif` | 15 | 588×390 | 8,8,8,8 | **5** | **4** |
| `rfull/out.tif` | 15 | 1222×1474 | 8,8,8,8 | **5** | **4** |
| `r1114/out.tif` | 15 | 588×390 | 8,8,8,8 | **5** | **4** |

`PhotometricInterpretation = 5` 即 **CMYK**，`SamplesPerPixel = 4`，`BitsPerSample = 8×4`——
与本文对 `savetiff00` 的分析完全吻合。

### 4.8.1 Software 标签的实际内容

四个文件的 **tag 305（Software）** 完全一致：

```
ok3d.com email:sales@ok3d.com hongmin guo +86-755-36843399
```

**这就解释了 `savetiff00` 里 `"ok3d"` 这个字符串的用途**——它是厂商/作者信息串的一部分
（作者名 **hongmin guo（郭宏敏）**、销售邮箱、深圳电话 `+86-755`）。
另外 tag 315（Artist）= `www.ok3d.com`，tag 306（DateTime）= 生成时间。

### 4.8.2 一处更正：`"3d99"` 并没有写进 TIFF

第 51 轮我写的是「`"3d99"` / `"ok3d"` 都以字符串写入」。实测四个产物里：

| 串 | 出现次数 |
|---|---:|
| `ok3d` | 3（Software 1 次 + Artist 1 次 + 邮箱里 1 次） |
| **`3d99`** | **0** |

**`"3d99"` 不出现在任何 TIFF 里。** 它在 `savetiff00` 里被载入，但用途未定
（可能是拼接其他路径/产品名时的成分，或在特定分支才使用）。
本文把它标为 **C 级未决**，不作断言。

---

## 5. 与主程序的接口

| 结论 | 等级 |
|---|---|
| 主程序仅静态导入 `bmptotiff`、`mergtotiff` | B（IAT + 传送桩） |
| `bmptotiff` 调用点 `0x505F5C`，3 个栈参数 | B |
| `mergtotiff` 调用点 `0x506132`，3 个栈参数 | B |
| 其余 5 个导出被其它模块或动态方式使用 | C（未找到调用点） |

---

## 6. 未完成 / 需要下一轮

1. **`rip3d.dll!stai` 的签名与实现** —— 这是合并的真正核心，本模块只是壳；
2. `0x415F20` / `0x415EE8` 各自对应哪个虚表槽位（`vmt+0x18` 等），需读虚表布局；
3. `mergtotiff` 的 361–362 行两个常量（`0xC6249808`、`0x39C18`）语义；
4. `savetiff00` 的 `param_1` 到底是不是 TIFF 对象、`param_2` 是不是页数。

---

## 7. 复现

```bash
# 反编译语料
_analysis/dump_cmyktiff2_g/0047f720.c     # mergtotiff，1811 行
_analysis/dump_cmyktiff2_g/0047e9d0.c     # savetiff00，258 行
_analysis/dump_cmyktiff2_g/0047e10c.c     # gettiffinfo，65 行

# 重新生成语料（阶段 B 流水线）
analyzeHeadless _analysis/ghidra_proj b_xxx -import Psdto3d/cmyktiff2.dll \
  -postScript DelphiSEH.java -postScript DelphiInit.java \
  -postScript DelphiVMT.java <vmt.tsv> -postScript DelphiSweep2.java \
  -postScript DelphiSweep4.java -postScript DumpAll.java <outdir> -deleteProject
```
