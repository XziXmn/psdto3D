# psdto3d.exe（99 版） 反编译说明

> 99 年版主程序，是 2022 版的直接前身。

> 本文的数字全部取自 `_analysis/baseline.json`（阶段 A 基线），与 `_analysis/coverage.tsv` 同源，可用 `python -I _analysis/gen_module_pages.py` 重新生成。

---

## 1. 模块标识（A 级）

| 项 | 值 |
|---|---|
| 源路径 | `psdto3d99绿色版/psdto3d99绿色版/psdto3d.exe` |
| SHA-256 | `450092ba349780e4b923f2ca998cbfdb60e34356f734885ebfc21b2cc11d4579` |
| 文件大小 | 1,740,800 B |
| CODE 段 | 1,257,472 B |
| 级别 | P1 |

## 2. 导出与窗体（A 级，PE 资源直接读出）

- 导出数：**0**
- DFM 窗体数：**6**

| 窗体 | 类 | 资源大小 |
|---|---|---:|
| `TABOUTBOX` | `TAboutBox` | 121,542 |
| `TFORM1` | `TForm1` | 71,041 |
| `TFORM2` | `TForm2` | 37,525 |
| `TLOGINDIALOG` | `TLoginDialog` | 1,172 |
| `TPASSWORDDIALOG` | `TPasswordDialog` | 964 |
| `TREG` | `TReg` | 37,219 |

## 3. 单元结构（B/C 级，来自 PACKAGEINFO 扫描）

| 项 | 值 |
|---|---|
| 候选单元条目 | 77 |
| 业务单元 | **53** |
| 库单元 | 24 |
| 置信度 | C |

业务单元：`PsdTo3D99_CMYK`、`DBGrids`、`SysConst`、`SysInit`、`KWindows`、`UTypes`、`wDBConsts`、`VDBConsts`、`Consts`、`WinSpool`、`FlatSB`、`StdActns`、`YStrUtils`、`MultiMon`、`Contnrs`、`Imm`、`WinHelpViewer`、`RHelpIntfs`、`ComStrs`、`ExtActns`、`RegStr`、`UrlMon`、`Dlgs`、`SyncObjs`、`RichEdit`、`ListActns`、`DBCtrls`、`nDBLogDlg`、`DB`、`FComObj`、`ComConst`、`rSqlTimSt`、`dFMTBcd`、`DBPWDlg`、`Rjpeg`、`XVCF1`、`OleServer`、`OleConst`、`OleCtrls`、`AxCtrls`、`StdVCL`、`LSoftKey`、`fregit`、`Unit1`、`GraphicColor`、`GraphicStrings`、`GraphicCompression`、`GraphicEx`、`MZLib`、`lJPG`、`help`、`about`、`ShareMem`

## 4. 语料与覆盖率

**本模块未建语料。** 原因：未建语料（该版本只做 PE/资源级比对，或非 P0/P1 分析目标）

因此本文没有函数级反编译正文（D 阶段要求的那种精读）。但第 4.5 节给出 IDR 恢复的**符号级**数据（导出、单元、命名函数）。

## 4.5 IDR 符号级数据（B 级，知识库恢复）

| 项 | 值 |
|---|---|
| IDR 名表条目 | 5,921 |
| 其中有真名 | 5,284 |
| 涉及单元 | 93 |
| 单元表条目 | 94 |

命名函数数（去占位）：**5284**。
完整的族内关系见 `docs/反编译_PSD读写.md` §3.9 与 `docs/反编译_其余模块.md` §1.2c。

## 5. 证据等级说明

| 等级 | 含义 | 本文用到的部分 |
|---|---|---|
| A | 直接从二进制/PE 结构读出，可逐字节复核 | 第 1、2 节 |
| B | 经工具解析 + 交叉验证 | 第 3 节（单元）、第 4 节（覆盖率） |
| C | 单一路径推断，未交叉验证 | 第 3 节里的库/业务划分 |
| D | 猜测，不得作为补丁依据 | 本文未使用 |

## 6. 复现

```bash
python -I _analysis/gen_baseline.py      # 重算哈希/导出/DFM/覆盖率
python -I _analysis/gen_corpora.py --check
python -I _analysis/gen_module_pages.py  # 重新生成本页
```
