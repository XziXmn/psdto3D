# AI 适配的逆向工具评估与实测

> 目标：为「代码底图」找一套**面向 AI agent** 的开源工具链，而不是只靠手写 Ghidra 脚本。
> 本文只记录**实际安装并跑通**的结果，未跑通的部分写明卡点。

---

## 1. 评估结论

| 工具 | 性质 | Delphi 7 适配 | 在本机可用性 | 结论 |
|---|---|---|---|---|
| **IDR**（Interactive Delphi Reconstructor） | GUI 专用反编译器 | ✅ 自带 `kb7.bin` | ✅ **已装并跑通** | **Delphi 知识来源**（见 `docs/反编译_IDR.md`） |
| **ghidra-headless-mcp**（含 `ghidra_cli`） | MCP 服务 + **CLI**（212 个工具） | 通用（Ghidra 分析） | ✅ **已装并跑通** | **AI 查询接口**（本文第 3 节） |
| ReVa（reverse-engineering-assistant） | MCP 服务（Ghidra 扩展） | 通用 | ⚠️ CLI 装上但缺扩展包 | 需再装其 Ghidra 扩展 |
| DelphiReSym | Ghidra 脚本（Python） | ❌ 仅 2009+ | — | 不适用 |
| REA（`rea@6.9.0`） | CLI + MCP | 通用 | ✅ 可用 | 只作独立对照（函数发现是子集） |

### 关键使能条件

这台机器的 Ghidra **12.2 没有打包 PyGhidra**（`Features/PyGhidra` 不存在），
但 `pip install pyghidra` 装到 3.2.0 后 **`pyghidra.start()` 成功**，
于是所有基于 pyghidra 的 AI 工具链都变得可用。这是本轮打通的关键一步。

---

## 2. 环境（实测版本）

```
Ghidra        12.2   （application.java.min=25，python.supported 3.9–3.15）
Python        3.12.10
pyghidra      3.2.0   （pip 安装，start() 通过）
uv / uvx      可用
git           可用
```

---

## 3. ghidra-headless-mcp：把 212 个逆向工具变成命令行

出处：`mrphrazer/ghidra-headless-mcp`。它的卖点是「面向 agent、无 GUI、无需 MCP 协议」——
自带 `ghidra_cli`，把全部 MCP 工具暴露成普通命令。

### 3.1 安装

```bash
git clone --depth 1 https://github.com/mrphrazer/ghidra-headless-mcp.git _analysis/vendor/ghidra-headless-mcp
cd _analysis/vendor/ghidra-headless-mcp && pip install .
```

安装后得到 `ghidra_cli.exe` / `ghidra-headless-mcp.exe`。需要 `GHIDRA_INSTALL_DIR`。

### 3.2 实测用法

```bash
ghidra_cli list                                  # 212 个工具清单
ghidra_cli describe function.report              # 查某个工具的参数
ghidra_cli call program.open --path <PE>         # 打开程序（返回 session_id）
```

**注意：`call` 是进程内会话，下一次调用就失效。**多步操作要用 `batch`
（JSONL，自动把上一行的 `session_id` 串到下一行）：

```bash
printf '%s\n' \
 '{"tool":"program.open","arguments":{"path":"C:\\...\\cmyktiff2.dll"}}' \
 '{"tool":"function.report","arguments":{"function_start":"0x47f720"}}' \
 | ghidra_cli batch -
```

### 3.3 实测结果（cmyktiff2.dll / `mergtotiff`）

`program.open` 返回：

```json
{ "compiler_spec_id": "borlanddelphi", "language_id": "x86:LE:32:default",
  "image_base": "00400000", "session_id": "3d90d3ec…" }
```

**Ghidra 自动识别出 `borlanddelphi`** —— 与本会话基线里的「Delphi 7 / VCL」判断一致。

`function.report`（`0x47F720`）返回结构化结果：

| 字段 | 值 |
|---|---|
| `body` | `0047f720` – `004832ae` |
| `calling_convention` | **`__register`**（Borland 寄存器约定，独立确认） |
| `xref_count` | 2 |
| `callees` | **39 个**，每个带 `entry_point` / `body_start` / `body_end` / `calling_convention` |
| `callers` | `[]`（调用方在主程序里，属另一个 program，符合预期） |
| `c` | 完整反编译 C |

`callees` 里每一条都是完整签名对象，例如：

```json
{"body_start":"004026d4","body_end":"004026f3","calling_convention":"__register",
 "entry_point":"004026d4","external":false,"name":"FUN_004026d4"}
```

### 3.4 相比本会话手写流水线的增量

| 能力 | 手写 Ghidra 脚本 | `ghidra_cli` |
|---|---|---|
| 函数发现（Delphi 专用） | ✅ 7,100（含 VMT/SEH/序言扫尾） | ❌ 用 Ghidra 默认分析 |
| 结构化 callees/callers | ❌ 只有反编译文本 | ✅ JSON |
| 调用约定识别 | ❌ | ✅ `__register` |
| 语义化查询接口 | ❌ | ✅ 212 个工具、一条命令 |
| 批量导出 `.c` | ✅ | 需逐函数调用 |

**结论：两者互补。**发现量靠本会话脚本，**结构化查询与 AI 交互靠 `ghidra_cli`**。

---

## 4. ReVa：装到一半

```bash
pip install reverse-engineering-assistant   # 7.3.2，得到 mcp-reva.exe
mcp-reva --list
```

启动报错：

```
Error starting ReVa server: No module named 'reva'
ModuleNotFoundError: No module named 'reva'
```

原因：PyPI 包只带 CLI 启动器，真正的 `reva` 模块在**它自己的 Ghidra 扩展包**里，
需要额外下载扩展并装进 Ghidra。本轮未继续，因为
`ghidra-headless-mcp` 已满足「AI 可调用」的需求，且不依赖扩展安装。

若要补完：从 `cyberkaida/reverse-engineering-assistant` 的 releases 取扩展包，
装入 Ghidra 的 `Extensions/Ghidra`，再 `pip install` 对应 python 包。

---

## 5. 本会话自建的 MCP 客户端（备用）

`_analysis/mcp_client.py`：一个最小的 MCP stdio 客户端（JSON-RPC 2.0，换行分隔），
可对任何 stdio MCP 服务做 `initialize → tools/list → tools/call`。
ReVa 修好后可直接用它驱动，不依赖宿主是否支持 MCP。

```bash
python -I _analysis/mcp_client.py --list
python -I _analysis/mcp_client.py --call function.report --args '{"session_id":"…","function_start":"0x47f720"}'
```

---

## 6. 复现

```powershell
$env:GHIDRA_INSTALL_DIR='C:\Users\moo\AppData\Local\ghidra\ghidra_12.2_PUBLIC'
pip install pyghidra                        # 打通 pyghidra
git clone --depth 1 https://github.com/mrphrazer/ghidra-headless-mcp.git _analysis\vendor\ghidra-headless-mcp
cd _analysis\vendor\ghidra-headless-mcp; pip install .
ghidra_cli list                             # 212 个工具
```

产物：
```
_analysis/vendor/ghidra-headless-mcp/        工具源码
_analysis/rea/ghidra_cli_mergtotiff.json     mergtotiff 的结构化报告（含 39 个 callees）
_analysis/vendor/batch_mergtotiff.jsonl      使用的 batch 输入
_analysis/mcp_client.py                      备用 MCP 客户端
```
