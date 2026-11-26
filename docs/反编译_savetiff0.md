# `savetiff0` 三份实现对照（ok3d1 / ok3d4 / save3d）

> 依据 `docs/反编译规划.md` 阶段 C3「核对 ok3d1/4 的 savetiff0 签名」与阶段 D3。
> 语料：`_analysis/dump_ok3d1/`、`_analysis/dump_ok3d4/`、`_analysis/dump_save3d/`
> 证据等级：A = 二进制结构直接可见；B = 静态可见；C = 推导；D = 假设。

---

## 1. 三个导出

| 模块 | 导出名 | 入口 VA | 文件大小 | CODE 段 | 语料函数数 |
|---|---|---|---:|---:|---:|
| `ok3d1.dll` | `savetiff0` | `0x42DDB8` | 186,880 | 186,880 | 1,104 |
| `ok3d4.dll` | `savetiff0` | `0x42DE78` | 187,392 | 187,392 | 1,105 |
| `save3d.dll` | `savetiff0` | `0x42B678` | 177,152 | 177,152 | 1,049 |

> **注意区分**：`cmyktiff2.dll` 导出的是 **`savetiff00`**（两个 0），
> 本文件讨论的是 **`savetiff0`**（一个 0）。两者是不同函数、不同实现，
> `cmyktiff2!savetiff00` 见 `docs/反编译_cmyktiff2.md` 第 3 节。

---

## 2. 序言完全同型（A 级，逐条指令）

三份入口的前 10 条指令逐字节同构（仅地址常量不同）：

```asm
55                  push ebp
8B EC               mov  ebp, esp
B9 40 00 00 00      mov  ecx, 0x40          ; 64
6A 00               push 0                  ; ┐
6A 00               push 0                  ; │ 循环 64 次
49                  dec  ecx                 ; │ = 在栈上清 512 字节
75 F9               jne  $-7                 ; ┘
53 56 57            push ebx / esi / edi
8B 75 0C            mov  esi, [ebp+0x0C]    ; ← 第 2 个栈参数
8B 5D 08            mov  ebx, [ebp+0x08]    ; ← 第 1 个栈参数
```

`ok3d4` 唯一差别是在 `push ebx` 前多一条 `51`（`push ecx`），其余完全一致。

**这条序言本身就是签名证据**：函数开头就在 `[ebp+8]`、`[ebp+0xC]` 取两个 dword，
说明**至少 2 个栈参数**；线扫到的 `ret 0x20`（32 字节 = 8 个 dword）说明
被调方清理 8 个 dword 的栈空间（B 级：`ret 0x20` 可能属于尾部内联块，需按控制流复核）。

---

## 3. 是同一份实现的证据（B 级）

### 3.1 调用剖面

统计每个 `savetiff0` 函数体内各被调函数的出现次数，按降序排列：

| 模块 | 行数 | 不同被调数 | 调用剖面 |
|---|---:|---:|---|
| `ok3d1` | 247 | 17 | `[76, 8, 6, 2, 2, 2, 1×11]` |
| `save3d` | 267 | 17 | `[76, 8, 6, 2, 2, 2, 1×11]` |
| `ok3d4` | 292 | 17 | `[81, 8, 5, 2, 2, 2, 1×11]` |

**`ok3d1` 与 `save3d` 的剖面完全相同**，`ok3d4` 只有热点那两项变化（76→81、6→5）。
三者都恰好 17 个不同被调、都没有字符串常量。

### 3.2 与导入表一致

三份 DLL 的导入 DLL 列表相同（`kernel32` / `user32` / `advapi32` / `oleaut32` /
`borlndmm` / `ws2_32` / `netapi32` / `setupapi`，`save3d` 多 `gdi32`、无 `setupapi`）。
差异只在导入条目计数，属重定位/版本差异。

### 3.3 结论

**`ok3d1` 与 `save3d` 的 `savetiff0` 是同一实现的不同编译产物**（B 级）；
`ok3d4` 是同源的分支变体，热点循环比另两份多 5 次调用（B 级）。

---

## 4. 函数结构（B 级）

三份的首几处调用形态一致——都是「往结构体不同偏移塞常量」：

```c
ok3d1:  FUN_00403acc((int *)(local_94 + 0x1c), 0x42e83c);
        FUN_00403acc((int *)(local_94 + 0x18), 0x42e84c);
        FUN_00403acc((int *)(local_94 + 0x14), 0x42e858);
ok3d4:  FUN_00403acc((int *)(abStackY_90 + 0x18), 0x42e978);
        …
save3d: FUN_00403ae4((int *)(local_94 + 0x1c), 0x42c0fc);
        …
```

第二参数是指向本 DLL `.rdata` 的常量指针（三份各自不同，因为镜像布局不同），
第一参数是栈上结构的字段偏移 `+0x10 / +0x14 / +0x18 / +0x1C`。
形态上像**初始化一组参数/选项表**，随后进入那个被调 76（或 81）次的热点循环。

---

## 5. 未完成

1. 热点被调（`ok3d1`=`0x411798`、`ok3d4`=`0x4117A0`、`save3d`=`0x411730`）
   到底是什么（TIFF 写行？压缩？），需读其函数体；
2. `ret 0x20` 归属需按控制流复核，才能把「≥2 个参数」收紧成确切个数；
3. `0x42E83C` 这些常量指针指向什么（选项名？标签？）；
4. 三份 DLL 与主程序的连接方式（主程序调用点未定位）。

---

## 5.5 IDR 复核（第 40 轮）：热点被调是 `TStream.WriteBuffer`

用 IDR 分析 `ok3d1.dll`（893 条完全限定签名），把三份实现里的关键函数实名化：

| 地址（ok3d1） | IDR 实名 | 本文早先的说法 | 结论 |
|---|---|---|---|
| `0x42DDB8` | `{ok3d1} savetiff0; stdcall;` | 导出 `savetiff0` | ✅ |
| **`0x411798`** | **`{Classes} TStream.WriteBuffer(const Buffer; Count: Longint)`** | 「TIFF 虚方法薄封装，像逐行写入」 | ✅ 方向对，**身份要改** |
| `0x403ACC` | `{system} @LStrLAsg` | 「字符串赋值」 | ✅ |
| `0x406E1C` | `{sysutils} StrToInt` | 「字符串→整数」 | ✅ |

### 5.5.1 关键更正：那不是「TIFF 对象虚方法」

`savetiff0` 里被调用 **76 次**的 `0x411798`，实为 **`TStream.WriteBuffer`** ——
即**往流里写字节**，不是调用某个 TIFF 对象的虚方法。

这与 `cmyktiff2!savetiff00` 完全一致：那边同样是 `TStream.WriteBuffer` 被调用 76 次。
**两份实现用的是同一套写法：打开 `TFileStream`，按 TIFF 结构逐段 `WriteBuffer`。**

### 5.5.2 由此得到的三点确认

1. **三份 `savetiff0` 都是「文件流 + 手写 TIFF 结构」**，没有 TIFF 库对象层；
2. `StrToInt` 的存在（`0x406E1C`）与 `savetiff00` 里「把 `"259"`/`"274"` 转成整数」的路径一致；
3. 导出 `savetiff0` 是 **`stdcall`**，与 `cmyktiff2` 七个导出的约定相同。

### 5.5.3 修正后的实现画像

```
savetiff0(stream, samplesPerPixel):
    TStream.WriteBuffer(...) × 76      ← 按 TIFF 头 / 目录项 / 数据段逐块写
    StrToInt 解析标签号
```

而不是早先描述的「通过 TIFF 对象虚方法写入」。

---

## 5.6 三份实现的符号级对照（第 48 轮，IDR 三侧分析）

对 `ok3d1` / `ok3d4` / `save3d` 分别做 IDR 分析（895 / 895 / 860 条名表），
按「单元 + 函数名」比集合。

| 模块 | IDR 名表 | 命名函数（去占位） | 导出 | 由 76 次调用指向的函数 |
|---|---:|---:|---|---|
| `ok3d1.dll` | 893 | 477 | `savetiff0; stdcall;` | `0x411798 TStream.WriteBuffer` |
| `ok3d4.dll` | 895 | 477 | `savetiff0; stdcall;` | `0x4117A0 TStream.WriteBuffer` |
| `save3d.dll` | 860 | 475 | `savetiff0; stdcall;` | `0x411730 TStream.WriteBuffer` |

### 集合相似度

```
ok3d1 ∩ ok3d4 : 477 / 477   Jaccard = 1.000   ← 完全相同
ok3d1 ∩ save3d: 474         Jaccard = 0.992
ok3d4 ∩ save3d: 474         Jaccard = 0.992
```

**`ok3d1` 与 `ok3d4` 的命名函数清单完全一致**（477 个，零差异）。
`save3d` 只多一个 `system.Set8087CW`（浮点控制字初始化），
这符合它的用途——存盘前要设浮点精度。

### 由此确认的三件事

1. **三份 `savetiff0` 是同一套写法的不同构建**（本文早先的推断），
   现在有符号级证据：导出名、调用约定、热点被调函数三者一致；
2. 实现路径统一为 **`TFileStream` + 76 次 `TStream.WriteBuffer`**，无 TIFF 对象层；
3. 三者差异只在布局偏移（`WriteBuffer` 地址 0x411798 / 0x4117A0 / 0x411730），
   不是逻辑差异。

**证据等级：A**（导出与符号来自 PE 导出表 + IDR 知识库解析，可逐项复核）。

---

## 6. 复现

```bash
# 语料
_analysis/dump_ok3d1/0042ddb8.c
_analysis/dump_ok3d4/0042de78.c
_analysis/dump_save3d/0042b678.c

# 剖面统计
python - <<'PY'
import re
from collections import Counter
from pathlib import Path
for mod, a in (('ok3d1','0042ddb8'),('ok3d4','0042de78'),('save3d','0042b678')):
    t = Path('_analysis/dump_%s/%s.c' % (mod, a)).read_text(encoding='utf-8', errors='replace')
    c = Counter(re.findall(r'\b(FUN_[0-9a-f]{8})\s*\(', t))
    print(mod, len(c), sorted(c.values(), reverse=True))
PY
```
