# psdto3d101.exe（2022）反编译说明

> 依据 `docs/反编译规划.md` 阶段 D3「每个 P0/P1 模块一页文档」。
> 语料：`_analysis/dump_psdto3d101_e/`（7,053 个函数，0 失败，代码口径覆盖 91.5%）
> 证据等级：A = 二进制结构直接可见；B = 静态可见的调用点/数据；C = 推导自洽；D = 假设。

---

## 1. 模块概况

| 项 | 值 |
|---|---|
| 文件 | `Psdto3d/psdto3d101.exe` |
| SHA-256 前缀 | `9521816a` |
| 文件大小 | 1,581,056 |
| CODE 段 | 1,127,424 B（覆盖 91.5% 代码口径） |
| 编译器 | Delphi 7 / VCL，PE32，无壳 |
| 导出 | 0（主程序） |
| 窗体 | 7 个（`_analysis/dfm/`） |
| PACKAGEINFO 业务单元 | 55 个 |
| 静态导入的自家 DLL | `cmyktiff2.dll` 的 `bmptotiff`、`mergtotiff` |

---

## 2. 类与方法（B 级，来自 VMT）

VMT 扫描到 **358 个类**，其中 **10 个带 published 方法表，共 125 个方法**，
按事件名规则筛出 **120 个事件处理器**。完整清单：
`_analysis/names/psdto3d101.json`，原始明细 `_analysis/logs/vmt_psdto3d101.tsv`。

带 published 方法的 10 个类：`TSaveDialog`、`TShape`、`TLoginDialog`、`TPasswordDialog`、
`TForm2`、`TAboutBox`、`TRegform`、`TForm1`（其余为库类）。

> 事件即 DFM 里 `OnClick = XxxClick` 的绑定目标。**这是把界面命令接到代码地址的唯一可靠桥梁。**

---

## 3. 界面结构（A 级，来自 DFM 解析）

| 窗体 | 行数 | 说明 |
|---|---:|---|
| `TForm1` | 1,897 | 主界面，48 个 `TMenuItem` |
| `TForm3` | 99 | — |
| `TRegform` | 121 | 注册 |
| `TLoginDialog` | 107 | 数据库登录（`Caption='Database Login'`） |
| `TPasswordDialog` | 81 | 密码 |
| `TAboutBox` / `TForm2` | 46 / 45 | 关于框 / 次级窗 |

主界面三个按钮（A 级，Caption 与 Hint 原文）：

```
BitBtn1  Caption='开图'    Hint='只能打开PSD图档'      OnClick=BitBtn1Click
BitBtn2  Caption='预览'    Hint='预览立体效果/停止'    OnClick=BitBtn2Click
BitBtn3  Caption='存盘'    Hint='合成并存盘'          OnClick=BitBtn3Click
```

---

## 4. 菜单命令 → 处理函数地址（B 级，34 条全部命中）

48 个 `TMenuItem` 中 34 个带 `OnClick`，全部在 VMT 名称表里找到地址：

| 菜单标题 | 事件 | 地址 |
|---|---|---|
| `Open project` | `SpeedButton12Click` | `0x00512798` |
| `&Save project` | `Saveproject1Click` | `0x00510BA0` |
| `Save as project` | `N4Click` | `0x0050A79C` |
| `&Import *.psd` | `SpeedButton1Click` | `0x00512B80` |
| `Import default settings` | `Opensettingsdefault1Click` | `0x005103C0` |
| `I&mport settings` | `N3Click` | `0x0050A718` |
| `Pre&View 3D animation` | `N18Click` | `0x0050B010` |
| `S&top preview` | `N25Click` | `0x0050B030` |
| `&Red/Blue Glasses preview` | `N26Click` | `0x0050B050` |
| `&Export *.tiff` | `N7Click` | `0x0050B070` |
| `E&xport PSD` | `PSD1Click` | `0x0050B090` |
| `Export &Gif` | `ExportGif1Click` | `0x0050E990` |
| `Export &Lines PSD` | `PSD2Click` | `0x0050B20C` |
| `&Quit` | `N9Click` | `0x0050A820` |
| `&Begin draw line` | `SpeedButton13Click` | `0x0050A678` |
| `&Undo` | `SpeedButton10Click` | `0x0050A3E4` |
| `&Delete line` | `SpeedButton6Click` | `0x0050A4EC` |
| `Delete &Layer` | `SpeedButton7Click` | `0x0050A4F0` |
| `Delete A&ll` | `SpeedButton8Click` | `0x0050A52C` |
| `&Delete Select` | `DeleteSelect1Click` | `0x0050FF44` |
| `Select &All` | `SelectAll1Click` | `0x0050FB58` |
| `Free &Transition` | `FreeTransform1Click` | `0x0050FDA0` |
| `C&ut` | `ToolButton9Click` | `0x0051087C` |
| `&Copy` | `Copy1Click` | `0x00512A38` |
| `Pastup` | `ToolButton10Click` | `0x00510A44` |
| `Zoom &In` | `SpeedButton3Click` | `0x0050A058` |
| `Zoom &Out` | `SpeedButton4Click` | `0x0050A204` |
| `&Show work folder` | `Showgrouptiff1Click` | `0x0050D984` |
| `&Help` | `Button5Click` | `0x005043C8` |
| `&Register` | `Label14Click` | `0x0050A030` |
| `&About` | `N22Click` | `0x0050A828` |
| `http://www.3&d99.com` | `httpww3d99com1Click` | `0x0050CCC4` |
| `&Clear Registered information` | `ClearRegister1Click` | `0x00512C50` |
| `&Languages English/Chinese` | `Languages1Click` | `0x00512C2C` |

**34/34 命中，无一条落空。** 复现方式见第 8 节。

---

## 5. 关键链路

### 5.1 「存盘」—— CMYK 合成链（B 级，跨模块）

```
BitBtn3(Caption='存盘', Hint='合成并存盘')
  → TForm1_BitBtn3Click     0x00505A44   1,954 B
      → bmptotiff   (cmyktiff2.dll)  调用点 0x00505F5C
      → mergtotiff  (cmyktiff2.dll)  调用点 0x00506132
          → rip3d.dll!stai            运行时 LoadLibrary + GetProcAddress
```

**这两个调用点是全程序对 `cmyktiff2.dll` 仅有的静态导入使用处**，
且都落在同一个函数体内。重写「存盘」时必须同时覆盖 `cmyktiff2` 与 `rip3d!stai`。

### 5.2 菜单「&Export *.tiff」只是确认后转调（A 级，9 行函数）

```c
void TForm1_N7Click(int param_1)              // 0x0050B070
{
  cVar1 = (**(code **)(**(int **)(param_1 + 0x3f4) + 0x50))();   // 虚调用，疑为确认对话框
  if (cVar1 == '\x01') {
    TForm1_BitBtn3Click(param_1, param_1);    // 确认后走同一条链
  }
}
```

即「导出 TIFF」与「存盘」**共用同一实现**，前者多一个确认。

### 5.2b PSD 读写链（B 级，本轮新查清）

**读**：启动函数 `FUN_005043F0`（`0x5043F0`，3,773 B）

```
行 210   DAT_00523268 = LoadLibrary("zu06.dll")
行 213   DAT_00523274 = GetProcAddress(DAT_00523268, "readpsd")
行 238   WVar4 = (*DAT_00523274)();
```

同一函数里还拼出 `\g1.bmp`、`\ok3d1.dll`、`\ok3d4.dll`、`\zu6.dll` 等路径，
以及 `YD.tif`、`_3D.psd`、`.tw3d2` 三个文件掩码，和版本串 `"Psdto3d 10.1   "`。

**写**：`TForm1_PSD1Click`（`0x50B090`，58 行）

```
行 38    LoadLibrary("zu06.dll")            ← 字符串在 0x0050B1F4 处内联
行 40    GetProcAddress(..., "writepsd")
行 42    (*_DAT_00523278)();
```

**结论**：2022 的 PSD 读写全部走 **`zu06.dll`**，且都是运行时绑定；
主程序里**没有** `8602.dll` 的任何引用（全语料零命中）。

### 5.2c 「存盘」内部：逐层 `bmptotiff` + 一次 `mergtotiff`（B 级）

`TForm1_BitBtn3Click`（306 行）里两个导入的真实位置：

| 行 | 内容 |
|---:|---|
| **223** | `func_0x004ff1ec()` —— **`bmptotiff`**，位于**图层循环内部** |
| **276** | `func_0x004ff1e4()` —— **`mergtotiff`**，循环结束后**只调一次** |

循环体（行 190–245）每层做三件事：拼 `.gjs` 名、调 `bmptotiff`、把结果设到一个图像对象上。

**`.gjs` 名的拼法**（行 194–241）：常量 `"vwd"` + `"00"` + 层号，
即 `vwd` + 三位数字 —— 与 `zu06!writepsd` 里写出的 **`vwd001.gjs`** 完全对应。

**传给 `mergtotiff` 的两个关键值**（行 268–269）：

```c
uStackY_a0 = ROUND((_DAT_0052307c / 25400.0) * 10000.0);
uStackY_a8 = ROUND((_DAT_00523074 / 25400.0) * 10000.0);
```

`25400` 是 **1 英寸的微米数**，所以这两行是「微米 → 英寸 → 万分比」的换算。
已知的 cm 公式里也有同一个常数（`25400/3000000`），两处用的是同一套长度单位约定。

### 5.2d 工程文件的读与写（`0x511408` / `0x510C54`）

用「工程第 3 行的标记 `99100`（= `0x1831C`）」当锚点，在主程序语料里检索，
只有两个函数命中：

| 地址 | 行数 | 判定 | 依据 |
|---|---:|---|---|
| **`0x510C54`** | 335 | **工程写入** | 逐行发射 PSD 路径、`99100` 行、三条厂商横幅、时间戳 |
| **`0x511408`** | 666 | **工程读取** | 含 `"The file not found!"`、`"The total number of layers is wrong!"`、`"(Auto)"` |

写入函数的行序（行 114–165）与我用真实文件读出的布局**完全一致**：

```
114–118  第 1 行  PSD 路径
120–135  第 2 行  <LPI> <Angles> <X> <Depth>      （五个字段，空格分隔）
137–145  第 3 行  99100 <层数> <宽> <高>
147–149  第 4 行  www.ok3d.com  Email:sales@ok3d.com
151–153  第 5 行  Mobile phone:13530461514
154–156  第 6 行  Author: Hongmin Guo
157–165  第 7 行  时间戳
```

配套的字符串构造辅助（B 级）：

| 地址 | 语义 |
|---|---|
| `FUN_004037f0` | 追加整数 |
| `FUN_00403860` | 追加浮点 |
| `FUN_00403774` | 追加一个字符（常用于追加空格 `0x20`） |
| `FUN_0040562c` | 追加字符串 |
| `FUN_00403870` | 追加行终止符：按标志二选一，`LF` 或 `CRLF` |

### 5.2e 工程读取函数的校验契约（`0x511408`，666 行）

### 三层校验（A/B 级）

**1. 文件存在性**（行 122–125）

```c
uVar3 = FUN_00409fb8(path);        // 存在性检查
if ((char)uVar3 == '\0') {
    FUN_0043397c("The file not found!");   // 抛异常并中止
}
```

**2. 标记必须等于 `99100`**（行 188–195）

```c
uVar4 = FUN_00403334(reader);   // 读第 1 个整数
…
if (uVar4 == 0x1831c) { … }     // 0x1831C = 99100
```

**3. 层数必须与 PSD 一致**（行 196–198）—— 最关键的一条

```c
if ((uVar5 != 0) && (uVar5 != DAT_0052315c)) {
    FUN_0043397c("The total number of layers is wrong!");
}
```

`DAT_0052315c` 就是**从 PSD 读到的层数**（`readpsd` 启动时探到的值）。
`uVar5` 是工程第 3 行里的层数。

**这就把 `docs/工程文件格式.md` 里「工程与 PSD 成对绑定」那条从经验观察
升级成了代码级的确定行为（A 级：字符串常量 + 分支条件都可见）。**

### 解析顺序（B 级）

| 行 | 动作 |
|---:|---|
| 188–191 | 连读 4 个整数（标记、层数、宽、高） |
| 192 | 换行 |
| 195 | 校验标记 |
| 196–198 | 校验层数 |
| 199–213 | 尺寸与 `0x5DD`（1501）阈值比较 |
| 214–225 | 连读 4 个字段 + 换行 |
| 226–233 | 连读 3 个浮点 → **×10000 存成万分比** |
| 234–237 | 读 2 个整数 → 两个 flag（`DAT_00523068/69`） |

### 一个界面约定（B 级）

行 253–256：

```c
if ((double)… == 10000.0) {
    FUN_0045fab4(*(int *)(local_8 + 0x56c), "(Auto)");
}
```

某个参数**恰好等于 10000.0（万分比下的 1.0）时，界面显示 `(Auto)`**。
即「1.0」在 UI 上是「自动」的哨兵值。

---

### 5.2f 图层数据在内存里的形状（B 级）

#### 三层嵌套数组 `layer[图][组][序号]`

读取函数用一个全局数组 `DAT_00523230` 承载手绘曲线（行 177–187 建、行 612–649 遍历）：

```c
行 177  FUN_00406380(&DAT_00523230, …, 1, 0);                 // 建空数组
行 178  FUN_00406380(&DAT_00523230, …, 1, DAT_0052315c);      // 按层数扩容
行 183  每层再建一个容量 15 的列表                            // = [图][组]
行 521/564/603  组内再建一层                                  // = [序号]
行 523/566/605  FUN_004064dc(...)                             // 追加点
```

访问形式是 `*(*(DAT_00523230 + i*4) + j*4) + k*4`，即**三层**。

**这正好对上了 `.tw3d2` 曲线块头的 `<图层> <分组> <子序号> <点数>`**——
三个索引字段各对应一级，`点数` 是第四层（点数组）的长度。

#### 每层记录 56 字节，`+0x2C` 是「有数据」标志

行 607：

```c
*(undefined1 *)(DAT_005230b4 + 0x2c + uVar4 * 0x38) = 0xff;
```

`0x38` = **56 字节步长**（与 `zu06!readpsd` 装配段看到的 `0x38` 一致），
`+0x2C` 偏移被置为 **`0xFF`**。

这与既有记录相吻合：`docs/复查报告_2026-11-18_晚.md` 里写过「导入 PSD 之后 32 条图层记录的
`+0x2C` 全是 `00`」——因为那时还没有曲线数据；一旦读入曲线，该字节被置 `0xFF`。

#### 读写之间的坐标偏移是**精确互逆**

| 侧 | 代码 | 位置 |
|---|---|---|
| **写** | `append_int(X − DAT_005232ec)`、`Y − DAT_005232f0` | 写入函数行 290–300 |
| **读** | `*p += DAT_005232ec`、`*(p+4) += DAT_005232f0` | 读取函数行 632–639 |

即：**文件里存的是相对原点的偏移，内存里存的是绝对坐标**；
写入时减、读取时加，用的是**同一对全局** `DAT_005232ec` / `DAT_005232f0`。

这一条把「文件格式」与「内存模型」两个视角接上了：文件省空间（相对坐标），
内存图方便（绝对坐标），转换点就在读写两个函数里各一处。

### 5.3 其它已定位的处理器

| 功能 | 函数 | 地址 | 大小 |
|---|---|---|---:|
| 预览立体效果/停止 | `TForm1_BitBtn2Click` | `0x0050544C` | 1,427 B |
| 导入 PSD（按钮与菜单共用） | `TForm1_SpeedButton1Click` | `0x00512B80` | 138 B |
| 导出 PSD | `TForm1_PSD1Click` | `0x0050B090` | 323 B |
| 导出 GIF | `TForm1_ExportGif1Click` | `0x0050E990` | 156 B |

`BitBtn1Click`（开图）在语料中**没有对应名字**——它的处理器不在 published 方法表里，
需按 `BitBtn1` 的 `OnClick` 名字在 RTTI 里另找，或从 `TForm1` 的 VMT 之外定位。

---

## 5.4 启动与环境初始化：`FUN_005043F0`（`0x5043F0`，3,773 B / 494 行）

这是主程序里除窗体事件外最集中的一处「把整套运行环境搭起来」的函数。

### 5.4.1 对话框过滤器与默认文件名（A 级字符串）

行 113–123 把一组字符串装进各对话框的 `Filter`（对象偏移 `+0x78`），
行 124 起再拼路径。读这些常量的原始字节：

```
0x5052D8  ".tif"       0x505308  ".gif"
          "YD.tif"               ".tw3d2"
          "_3D.psd"              "\g1.bmp"
```

**结论**：默认输出 TIFF 名是 **`YD.tif`**，输出 PSD 的后缀是 **`_3D.psd`**，
工程扩展名 **`.tw3d2`**，中间位图 **`\g1.bmp`**。

### 5.4.2 三个业务 DLL 的实例化（B 级）

行 130–142：

```c
piVar1 = FUN_0040414c(&PTR_LAB_0041a3dc, 1, …);   // 三个实例
路径: <appdir> + "\ok3d1.dll" / "\ok3d4.dll" / "\zu6.dll"
FUN_0041eba8(piVarN, 路径);                        // 交给实例
DAT_0052327c = (**code)(*piVar1)();                // 虚表首项 → 返回字节数
DAT_00523280 = (**code)(*piVar2)();
DAT_00523284 = (**code)(*piVar3)();
iVar6 = (DAT_0052327c + 3) >> 2;                   // = (n+3)/4，转成 dword 数
```

`(n+3)/4` 这个换算与 `cmyktiff2!mergtotiff` 里的写法**完全一致**，是同一套约定。

### 5.4.3 启动时调用一次 `readpsd`（B 级）

行 210–231：

```c
DAT_00523268 = LoadLibrary("zu06.dll");
if (DAT_00523268) DAT_00523274 = GetProcAddress(DAT_00523268, "readpsd");
… 压入 14 个全局地址作为参数 …
WVar4 = (*DAT_00523274)();          // 行 231
```

即**程序一启动就用 `readpsd` 探一次 PSD**，拿到的值直接回填界面（行 232）。

### 5.4.4 颜色模式分支：GRAY / RGB / CMYK（A 级）

行 234–248 按 `DAT_0052315e` 分支，对应字符串常量：

```
0x5053E8  "GRAY"   "RGB"   "CMYK"
mode == 1  →  GRAY
mode == 3  →  RGB
mode == 4  →  CMYK
```

**1 / 3 / 4 正是 PSD 规范里的颜色模式编号**（1=Grayscale、3=RGB、4=CMYK），
所以 `DAT_0052315e` 就是**从 PSD 读到的颜色模式**。

这条与 `writepsd` 写出的 PSD 头 `mode = 4`（实测）互相印证：
**整条链是 CMYK 四通道的**。

### 5.4.5 万分比 → 实际值的界面回填（B 级）

行 255–295 反复出现同一形态：

```c
fVar9 = (float10)_DAT_005231a8 / (float10)10000.0;
FUN_0040b134(&local_44, …, fVar9);              // 转字符串
FUN_0045fab4(*(int *)(local_8 + 0x3b4), local_44);   // 设到控件
```

**`/ 10000.0` 出现 5 次**，分别取 `_DAT_005231a8`、`_DAT_005231b0`、`_DAT_005231b8` 等全局。
这确认了「内部以 1/10000 为单位存储、显示时除以 10000」的口径——
与 `readpsd` 里那条缩放规则（高度 >1500 时按万分比缩放）是同一个约定。

---

## 6. 与其它模块的关系

| 模块 | 关系 | 等级 |
|---|---|---|
| `cmyktiff2.dll` | 静态导入 `bmptotiff`、`mergtotiff`，仅 `TForm1_BitBtn3Click` 使用 | **B** |
| `8602.dll` | 导出 `readpsd`(`0x4B9528`)、`writepsd`(`0x4BAA64`)；主程序侧调用点未定位 | C |
| `rip3d.dll` | 由 `cmyktiff2!mergtotiff` 运行时加载，主程序不直接引用 | **B** |
| `ok3d1/ok3d4/save3d` | 各导出 `savetiff0`；主程序调用点未定位 | C |
| `3d.dll` / `cmyk.dll` | 由 `mergtotiff` 通过门面类实例加载 | **B** |

---

## 7. 未完成

1. `BitBtn1Click`（开图）的地址——语料无此名，需从 RTTI 或 VMT 外定位；
2. `PSD1Click`（导出 PSD，323 B）内部实际写盘路径，是否走 `.psd` 模板拼接；
3. ~~`.tw3d2` 读写函数在语料中的落点~~ —— 已定位到 `FUN_005043F0`（`0x5043F0`）
   与 `FUN_0050A850`（`0x50A850`）、`FUN_005103C0`（`0x5103C0`）三处引用 `.tw3d2`
   字面量；具体读/写分工仍需细读；
4. 10.1 版本的函数级差异（需先把 `Psdto3d (2)/psdto3d101.exe` 跑一遍 B 阶段流水线）。

---

## 8. 复现

```bash
# 窗体文本（含菜单与按钮）
python -I _analysis/dfm_to_text.py Psdto3d/psdto3d101.exe
# → _analysis/dfm/02_TFORM1.dfm

# 事件名 → 地址
python -I _analysis/gen_names.py
# → _analysis/names/psdto3d101.json

# 菜单到地址的对应（本文第 4 节表格的生成方式）
python - <<'PY'
import json, re
from pathlib import Path
dfm = Path('_analysis/dfm/02_TFORM1.dfm').read_text(encoding='utf-8').splitlines()
ev = {e['event']: e['address'] for e in
      json.loads(Path('_analysis/names/psdto3d101.json').read_text(encoding='utf-8'))['events']}
for i, l in enumerate(dfm):
    m = re.match(r'^(\s*)object (\w*): TMenuItem', l)
    if not m: continue
    ind = len(m.group(1)); cap = click = None
    for j in range(i + 1, len(dfm)):
        s = dfm[j]
        if not s.strip(): continue
        k = len(s) - len(s.lstrip())
        if k <= ind and s.strip().startswith('object'): break
        if k == ind + 2:
            t = s.strip()
            if t.startswith('Caption = ') and cap is None: cap = t[10:]
            if t.startswith('OnClick = ') and click is None: click = t[10:]
    if click: print(cap, click, ev.get(click))
PY
```
