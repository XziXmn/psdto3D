# 导出 ABI 说明

> 依据 `docs/反编译规划.md` 阶段 C3。
> 证据等级：A = 二进制结构直接可见；B = 静态可见的调用点/数据；C = 推导自洽；D = 假设。

---

## 1. 导出总表（A 级）

### 1.1 `cmyktiff2.dll`（7 个，与规划一致）

| 序号 | 名称 | RVA→VA | 函数体字节 | 语料 |
|---:|---|---|---:|---|
| 1 | `JpgToBmp` | `0x47E4B0` | 115 | `_analysis/dump_cmyktiff2_h/0047e4b0.c` |
| 2 | `bmptotiff` | `0x47E270` | 532 | `…/0047e270.c` |
| 3 | `gettiffinfo` | `0x47E10C` | 296 | `…/0047e10c.c` |
| 4 | `mergtotiff` | `0x47F720` | **14,862** | `…/0047f720.c` |
| 5 | `rgbtocmykbmp` | `0x47E530` | 483 | `…/0047e530.c` |
| 6 | `savetiff00` | `0x47E9D0` | 2,626 | `…/0047e9d0.c` |
| 7 | `tifftobmp` | `0x47E744` | 634 | `…/0047e744.c` |

### 1.2 `8602.dll`（2 个）

| 名称 | VA | 说明 |
|---|---|---|
| `readpsd` | `0x4B9528` | PSD 读取入口 |
| `writepsd` | `0x4BAA64` | PSD 写出入口 |

### 1.3 `savetiff0`（保存链，各 DLL 各一个）

| 模块 | VA | 语料 |
|---|---|---|
| `ok3d1.dll` | `0x42DDB8` | `_analysis/dump_ok3d1_c/0042ddb8.c` |
| `ok3d4.dll` | `0x42DE78` | `_analysis/dump_ok3d4_c/0042de78.c` |
| `save3d.dll` | `0x42B678` | `_analysis/dump_save3d_b/0042b678.c` |

三份的序言逐字节同构（`mov ecx,0x40` + 循环清 512 B 栈，随后 `mov esi,[ebp+0xC]`、
`mov ebx,[ebp+8]`），因此**至少有 2 个 dword 栈参数**；`ok3d4` 仅在 `push ebx` 前多一条 `push ecx`。
调用剖面 `ok3d1` 与 `save3d` 完全相同（`[76,8,6,2,2,2,1×11]`），`ok3d4` 为 `[81,8,5,…]`，
判定为**同一实现的不同编译产物（B 级）**。详见 `docs/反编译_savetiff0.md`。

> 与 `cmyktiff2.dll` 的 `savetiff00`（两个 0）是不同函数，不要混淆。

---

## 2. 调用约定（B 级）

### 2.1 静态导入的传送方式

主程序对 `cmyktiff2.dll` 只有两个静态导入：

```
bmptotiff   IAT = 0x00524A70   传送桩 = 0x004FF1EC   （ff 25 70 4a 52 00）
mergtotiff  IAT = 0x00524A74   传送桩 = 0x004FF1E4   （ff 25 74 4a 52 00）
```

调用方先 `call 0x004FF1EC` / `call 0x004FF1E4`，桩再 `jmp [IAT]`。
其余 5 个导出（`JpgToBmp`、`gettiffinfo`、`rgbtocmykbmp`、`savetiff00`、`tifftobmp`）
在主程序里**没有静态导入点**，属于被其它模块动态取用或根本不由主程序调用。

### 2.2 实参准备（B 级：调用点原文）

**`bmptotiff`** —— 唯一调用点 `0x00505F5C`：

```
00505F5C                          call 0x004FF1EC        ; -> bmptotiff
       入参准备（前 3 条）：
         push dword ptr [0x523160]
         push dword ptr [0x5231a8]
         push dword ptr [0x5231ac]
```

**补充（第 29 轮）**：`bmptotiff` 位于图层循环内逐层调用，
`mergtotiff` 在循环结束后只调一次；后者收到的两个长度参数由
`ROUND((值 / 25400.0) * 10000.0)` 换算而来（微米 → 英寸 → 万分比）。
详见 `docs/反编译_psdto3d101.md` 5.2c 节。

**`mergtotiff`** —— 唯一调用点 `0x00506132`：

```
00506132                          call 0x004FF1E4        ; -> mergtotiff
       入参准备（前 3 条）：
         push dword ptr [esi + 0x510]
         push dword ptr [0x52306c]
         push dword ptr [0x523070]
```

### 2.3 结论

- 两者都至少接受 **3 个栈参数**；按 Delphi/Borland 寄存器约定，前若干个参数走
  `eax/edx/ecx`，其余压栈，栈由被调方清理（`ret n`）。
- 这与 `cmyktiff2` 里大量出现的 `ret 0x10` / `ret 0x14` 型收尾一致，
  但**具体每个参数的类型尚未核定**（见第 4 节）。

---

## 3. `savetiff00` 与 `gettiffinfo` 的参数（本轮已读到逐行）

### 3.1 `savetiff00(int *param_1, ushort param_2)`（B 级）

- `param_1` 是**流对象**：全函数 76 次调用都把它作为第一实参传给
  `FUN_00415F20(obj, buf, len)`（写入 len 字节）。
- `param_2` 是**每像素采样数**：行 93–98 为 `if (param_2 == 3) write 3 else write 4`，
  结合本 DLL 的 CMYK 用途，判定 3 = RGB、4 = CMYK（语义部分 C 级）。

### 3.2 `gettiffinfo`（B 级，逐行解析完成）

```c
void gettiffinfo(const char *filename,
                 int *width, int *height, int *bitsPerSample,
                 int *compression, int *stripOffsets)
```

依据：函数打开 TIFF 后 `Seek(8)`，读 2 字节得 IFD 条目数，再循环读
`tag(2) + type(2) + count(4) + value(4)`，按标签分派：

| 标签 | 标准名 | 输出 |
|---|---|---|
| `0x100` | ImageWidth | 参数 2 |
| `0x101` | ImageLength | 参数 3 |
| `0x102` | BitsPerSample | 参数 4（初值 4） |
| `0x103` | Compression | 参数 5（初值 1） |
| `0x111` | StripOffsets | 参数 6 |

初值 `bits=4 / compression=1` 与 CMYK 四通道、无压缩吻合。

详见 `docs/反编译_cmyktiff2.md` 第 3、4 节。

---

## 3.5 IDR 核出的关键事实（第 38 轮，重要更正）

用 IDR 分析 `cmyktiff2.dll` 后，其 Map 视图给出完全限定签名，**更正了本文先前两处判断**：

### 3.5.1 导出是 `stdcall`，不是 Borland 寄存器约定

```
0047E10C:{cmyktiff2} gettiffinfo;  stdcall;
0047E270:{cmyktiff2} bmptotiff;    stdcall;
0047E4B0:{cmyktiff2} JpgToBmp;     stdcall;
0047E530:{cmyktiff2} rgbtocmykbmp; stdcall;
0047E744:{cmyktiff2} tifftobmp;    stdcall;
0047E9D0:{cmyktiff2} savetiff00;   stdcall;
0047F720:{cmyktiff2} mergtotiff;   stdcall;
```

**七个导出全部 `stdcall`**（参数在栈上、被调方清栈）。
本文早期写「按 Delphi/Borland 寄存器约定，前若干参数走 eax/edx/ecx」——
那是**内部函数**的约定，**导出边界上不适用**。重写时声明导出必须用 `stdcall`。

### 3.5.1b 跨模块统一：**所有导出都是 `stdcall`**

三个 DLL 的导出逐个核对（IDR 的 Map 视图）：

| 模块 | 导出 | 约定 |
|---|---|---|
| `cmyktiff2.dll` | 7 个全部 | `stdcall` |
| `zu06.dll` | `readpsd`、`writepsd` | `stdcall` |
| `8602.dll` | `readpsd`、`writepsd` | `stdcall` |
| `ok3d1.dll` | `savetiff0` | `stdcall` |

**可以当作规则用：本项目的 DLL 导出边界一律 `stdcall`**（不是 Delphi 内部默认的
`register`）。重写时声明导出必须显式写 `stdcall`。

### 3.5.2 那几个反复出现的辅助函数有了实名

| 地址 | IDR 判定 | 本文早期说法 | 正误 |
|---|---|---|---|
| `0x415F20` | `{Classes} TStream.WriteBuffer(const Buffer; Count: Longint)` | 「流写入」 | ✅ 对 |
| `0x415EE8` | `{Classes} TStream.ReadBuffer(var Buffer; Count: Longint)` | 「流读取」 | ✅ 对 |
| `0x415CDC` | `{Classes} TStream.SetPosition(const Pos: Int64)` | 「定位/Seek」 | ✅ 对 |
| `0x416170` | **`{Classes} constructor TFileStream.Create(const FileName; Mode)`** | 「TIFF 对象构造」 | ❌ **错** |
| `0x408480` | `{sysutils} StrToInt(const S: AnsiString): Integer` | 「字符串→整数」 | ✅ 对 |
| `0x40415C` | `{system} @LStrLAsg` | 「字符串赋值」 | ✅ 对 |

**更正**：`FUN_00416170` 不是「TIFF 对象」，而是 **`TFileStream.Create`**。
因此 `gettiffinfo` / `savetiff00` / `bmptotiff` 打开的是**文件流**，
`TStream.ReadBuffer` / `WriteBuffer` 作用在它上面——整条链是「文件流 + 字节读写」，
不存在独立的「TIFF 对象」。

**顺带印证**：`savetiff00` 把一批数字字符串交给 `StrToInt` 再写进目录项。
第 51 轮已从二进制里把这批字符串逐个读出（地址 → 值）：

| 地址 | 字符串 | 转整数 | 含义 |
|---|---|---|---|
| `0x47F454` | `"259"` | `0x0103` | Compression |
| `0x47F46C` | `"274"` | `0x0112` | Orientation |
| `0x47F42C` | `"18261"` | `0x4755` | 私有标签 |
| `0x47F43C` | `"423"` | `0x01A7` | 私有标签 |
| `0x47F448` | `"1"` | 1 | 取值 |
| `0x47F460` | `"19"` | `0x0013` | 私有标签 |
| `0x47F478` | `"3d99"` | —（非数字） | **未定**（真实 TIFF 里 0 次出现，C 级） |
| `0x47F488` | `"ok3d"` | —（非数字） | 写进 **Software 标签**（已由真实产物证实） |

所以「字符串 → 标签号 → 写入」这条路径成立，且**共 8 个字符串、其中 6 个走 `StrToInt`**。

真实产物的 Software 标签（tag 305）内容为
`ok3d.com email:sales@ok3d.com hongmin guo +86-755-36843399`，
四个样本一致——`"ok3d"` 就是这一串的成分。`"3d99"` 在真实 TIFF 里 0 次出现，用途未定。
详见 `docs/反编译_cmyktiff2.md` §4.7。

---

## 4. 尚未完成的部分（下一轮）

1. ~~其余导出的参数类型~~ —— **已完成**，七个导出全部读过：

   | 导出 | 推断签名 | 等级 |
   |---|---|---|
   | `JpgToBmp` | `void JpgToBmp(const char *filename, TBitmap **out)` | B |
   | `bmptotiff` | `void bmptotiff(const char *in_bmp, const char *out_tiff, int mode)` | B |
   | `gettiffinfo` | `void gettiffinfo(const char *file, int *w, int *h, int *bits, int *comp, int *strip)` | B |
   | `mergtotiff` | 3 个栈参数（调用点已定位） | B |
   | `rgbtocmykbmp` | `void rgbtocmykbmp(const char *filename, TBitmap **out)` | B |
   | `savetiff00` | `void savetiff00(int *stream, ushort samples_per_pixel)` | B |
   | `tifftobmp` | `void tifftobmp(const char *in_tiff, TBitmap **out)` | B |

   详见 `docs/反编译_cmyktiff2.md` 第 4.5 节；
2. **`8602.dll` 的 `readpsd`/`writepsd`**：目前只确认地址与导出名，
   参数与返回尚未分析；
3. ~~**`savetiff0` 三份 DLL 的差异**~~ —— **已完成**，见 `docs/反编译_savetiff0.md`：
   三份是同一实现的不同编译产物，`ok3d4` 为分歧变体。

---

## 5. 复现方法

```bash
# 导出表
python -c "import pefile; pe=pefile.PE('Psdto3d/cmyktiff2.dll'); \
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']]); \
print([(e.name.decode(), hex(pe.OPTIONAL_HEADER.ImageBase+e.address)) for e in pe.DIRECTORY_ENTRY_EXPORT.symbols])"

# 反编译产物
_analysis/dump_cmyktiff2_h/<地址小写无前缀>.c      例如 0047f720.c = mergtotiff
```
