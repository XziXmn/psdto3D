# 故障诊断：`Invalid floating point operation` 与 `0x0050A001` 访问违例

你在 Win7 兼容模式下看到的三个弹框，背后是**同一段代码**：
先因为数据不合法算出 `NaN/∞`（浮点异常），再拿这个非法下标去读图层数组（空指针）。

下面用二进制证据逐个对上。

---

## 1. 三个弹框分别是什么

| 弹框 | 来源 | 性质 |
|---|---|---|
| `All layers must be simple layer, Can not have backgroup layer!` | 程序自身校验（导入 PSD 时） | **输入不合法**：PSD 里有背景层/图层结构不符合要求 |
| `Invalid floating point operation.` | Delphi `EInvalidOp`（RTL 文案） | 非法浮点运算：`0/0`、`∞`、`NaN` 参与 `Round()` |
| `Access violation at address 0050A001 … Read of address 00000000` | Delphi `EAccessViolation` | 代码读 `[eax + edi*4]`，此时 `eax = 0` |

第一条是原因，后两条是"带着坏数据继续算"的后果。

## 2. 反汇编证据

`psdto3d101.exe`（PSDTO3D 2022，映像基址 `0x400000`，CODE 段 `0x401000`）：

```
00509f83  mov   eax, [0x5230a0]      ; 每层的像素缓冲指针数组
00509f88  mov   eax, [eax + ebx*4]   ; 取第 ebx 层的块指针
00509f8b  call  0x4061c4
00509f90  mov   [esp+0xc], eax
00509f94  fild  dword [esp+0xc]
00509f98  fild  dword [0x5230fc]     ; ← 视图/角度数（UI 上的 "Angles"）
00509f9e  fdivp st(1)                ; ← 除以它：为 0 时得到 ∞
00509fa0  fmul  dword [0x50a028]
00509fa6  fistp qword [esp]          ; 这一步就会抛 EInvalidOp（NaN/∞ → 整数）
...
00509fdd  fild  dword [esp+0xc]
00509fe1  fadd  dword [0x50a02c]
00509fe7  fild  qword [esp]
00509fea  fmulp st(1)
00509fec  fdiv  dword [0x50a028]
00509ff2  call  0x402ca4             ; Delphi Round()
00509ff7  mov   edi, eax             ; ← 算出来的层内索引
00509ff9  mov   eax, [0x5230a0]
00509ffe  mov   eax, [eax + ebx*4]
0050a001  mov   eax, [eax + edi*4]   ; ← 崩溃点：eax=0（该层缓冲未分配）或 edi 越界
0050a004  mov   edx, [0x52309c]
0050a00a  mov   edx, [edx + ebx*4]
0050a00d  mov   [edx + esi*4], eax
```

要点：

1. `0x5230fc` 就是 UI/工程里的 **Angles**。它为 0 → `fdivp` 得 `∞` → `fistp` 触发
   "Invalid floating point operation"。
2. 浮点异常之后程序没有中止，`Round()` 返回整数不确定值（`0x80000000` 或 0），
   再由 `ebx`（层号）/`edi`（层内索引）去索引 `[0x5230a0][ebx]` 与 `[+edi*4]`：
   图层缓冲没分配（`NULL`）就报 `Read of address 00000000`。
3. 这段是"3D 视图生成"循环，只有**真的去生成/预览**时才会走到，
   所以现象是"PSD 加载了一部分，然后炸"。

## 3. 为什么"Win7 兼容 + 管理员"表现不同

* **兼容模式**会挂上 shim（版本谎言、堆/文件虚拟化差异），改变的是加载时机与失败顺序；
  先炸浮点还是先炸空指针随之改变。三种组合分别看到 1+2、或 3，属于同一 bug 的不同落点。
* **管理员**只会让写 `C:\ok3dtemp`、写自身目录等操作不再被拦，**不会**修复这个数据问题。

## 4. 真正的触发条件（已定位）

崩溃点在 `0x0050A001`：`mov eax,[eax+edi*4]`，`Read of address 00000000`。
把它和上文的"建表"代码对上，触发条件可以唯一确定：

1. 程序按**最大分组号**给两张表开数组（`SetLength(table, maxGroup)`，
   `0x509EBA`/`0x509ED3`），只有真实存在的分组才在 `0x509F1A`–`0x509F5E` 被填成非空；
2. **没有分组的槽位保持 `nil`**；
3. 生成循环从 `ebx = 0`（= 第 1 组）开始遍历所有槽位，先取 `Length(nil) → 0`，
   于是 `P = 0`、`edi = Round(0) = 0`，接着执行 `[nil + 0]` —— 正好是 `0x0050A001`
   的"读地址 0"。

也就是说：**工程里的图层分组号不连续**（例如所有层都在第 5 组，于是第 1–4 组是空槽）
时，第一次进入生成就必崩。官方 sample 全是这种写法（实测 12 个工程的分布：

```
3d2 / 3danimation / flip3x / gray / kelex / psdsampleCMYK / donghua …  groups={5: 全部}
MorphZoomRatation …                                                   groups={0:13, 5:13}
```

`max=5` 而只有第 5 组有层 → 第 1 组就是空槽 → 崩。这解释了你看到的"PSD 加载了一部分，
然后 AV"。

> 为什么不是"数组还没建"：那种情况下 `[0x5230A0]` 本身为 0，崩溃地址会是 `0x509FFE`
> 而不是 `0x50A001`。崩溃点更高一行，说明表在、槽位是空的。

## 5. 修复（已实施）

### 5.1 数据层：分组号致密化（根治，输出正确）

```powershell
python tools\tw3d2.py regroup "你的工程.tw3d2"      # {5} → {1}，{7,9} → {1,2}
```

分组语义只依赖"相等/不相等"，致密重编号保留分组划分与相对顺序，同时消除空槽。
两个绿色包内的 12 个 sample 工程已经全部处理（原文件备份在 `sample_orig\`）。

### 5.2 二进制层：空槽守卫（兜底，防再崩）

`psdto3d2022绿色版` 的主程序已加守卫：把 `0x509FF9` 起 11 字节改成跳转，
在 CODE 段尾部空余（`0x514324`）执行：

```
00514324  mov  eax,[0x5230A0]
00514329  test eax,eax          ; 表本身为空？
0051432B  je   0x51433C
0051432D  mov  eax,[eax+ebx*4]  ; 该分组的层列表
00514330  test eax,eax          ; 空槽？
00514332  je   0x51433C
00514334  mov  eax,[eax+edi*4]  ; 原指令
00514337  jmp  0x50A004         ; 正常继续
0051433C  jmp  0x50A010         ; 跳过本次内层迭代（inc esi / 下一视图）
```

正常路径与原指令等价；空槽不再解引用 NULL。补丁记录见
`构建报告_psdto3d2022_崩溃守卫.json`，可用 `tools\patch_crash_guard.py` 复核/重放。
10.1 版的生成器是另一种实现（没有这处 `[eax+edi*4]` 索引），无需该守卫。

### 5.3 顺带的两条纪律

* `Angles`（工程第 2 行第 2 个字段）保持 > 0，否则 `0x509F9E` 的 `fdivp` 会先抛
  `Invalid floating point operation`。
* PSD 不要有背景层（程序自身校验会弹第一条弹框，并带着未初始化数据继续跑）。

## 6. 验证方式

```powershell
python tools\verify_green.py --dir "psdto3d2022绿色版" --launch     # 10/10 PASS
python tools\tw3d2.py check "工程.tw3d2" --psd                      # 分组/图层数/尺寸一致性
python tools\patch_crash_guard.py "psdto3d2022绿色版\psdto3d101.exe" --dry-run   # 复核补丁点
```

`--dry-run` 会重新定位站点（`0x509FF9`）、洞穴（`0x514324`）、回跳目标（`0x50A004`）
与跳过目标（`0x50A010`），与已写入的字节逐项比对。

