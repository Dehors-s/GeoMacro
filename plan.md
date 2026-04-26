# Plan: GeoMacro MVP Architecture Blueprint

> 更新日期：2026-04-25
> 状态：**MVP 全部 4 个 Commit 已完成**，可演示

---

## 项目目标

一键静默抓取用户最近的 ArcGIS Pro / Desktop Geoprocessing 历史，自动抽取可变输入与固定参数，生成可批量遍历目录的 Python 脚本。

---

## 当前状态总览

| 里程碑 | 阶段 | 状态 | 验证结果 |
|--------|------|------|---------|
| Gate A | 事件监听稳定捕获 | ✅ | .NET Add-in 反射订阅 GPExecuteToolEvent，XML 日志容错读取 |
| Gate B | 历史合并与去重 | ✅ | ID 优先 + 时间窗兜底，无重复，顺序正确 |
| Gate C | 真实流程脚本可运行 | ✅ | Clip / CalculateField / RepairGeometry 三条流程已验证 |
| Gate D | 中文路径与失败项提示 | ✅ | 非ASCII路径警告、失败项标记、缺参检测、语法检查 |

---

## Commit 完成详情

### ✅ Commit 1 — 监听最小闭环

**交付物：**
- `GpEventSubscriber.cs` — 通过反射订阅 `GPExecuteToolEvent` / `GPToolExecuteEvent`
- `GpEventRecord.cs` — 事件 DTO（ExecuteId, ToolPath, ToolName, IsStarting, IsSuccess, TimestampUtc）
- `EventJsonWriter.cs` — JSONL 文件写入器（线程安全）
- `EventLogService.cs` — 日志服务（Ring buffer，最大 500 条）
- `EventLogDockpaneViewModel.cs` — 日志面板（最初的最小 UI）

**已知限制：** ArcGIS Pro 3.0 的 `GPToolExecuteEvent` 负载不含完整的 tool path/id，记录显示为 "UnknownTool"。数据主要来自 XML 日志回填。

---

### ✅ Commit 2 — 历史最小闭环

**交付物：**
- `history_xml_reader.py` — XML 历史读取器
  - 自动发现 `%APPDATA%\ESRI\ArcGISPro\` 和 `Desktop*` 目录
  - 解析两种 XML 格式（Pro 3.0 中文日期 + Desktop 10.8 英文日期）
  - 容错处理截断 XML（`_recover_truncated_xml`）
  - 参数 types 识别（`_PATH_PARAM_TYPES` / `_NON_PATH_PARAM_TYPES`)
- `history_parser.py` — 历史数据规范化
- `event_normalizer.py` — 事件标准化（StandardEvent）
- `history_collector.py` — 增量采集、合并去重、事件评分
- `models.py` — 核心数据模型（Parameter, StandardEvent, VariableSlot, StepNode）
  - 新增 `ProductSource` 枚举（DESKTOP / PRO / UNKNOWN）
  - 新增 `detect_product_source()` 从 tool_path / HistorySource 自动识别版本

**版本识别逻辑：**
- tool_path 含 `desktop10.` → `arcgis_desktop`
- 含 `arcgispro` / `pro\` → `arcgis_pro`
- 含 `arctoolbox\toolboxes` 但不含 pro → `arcgis_desktop`

---

### ✅ Commit 3 — 生成最小闭环

**交付物：**
- `template_registry.py` — 工具注册表（12 个白名单工具）
  - 从 `tool_path` 提取内部工具名（中英文都支持）
  - 如：中文"计算字段" → `CalculateField` → `arcpy.management.CalculateField`
- `variable_extractor.py` — 变量提取器
  - 路径参数自动参数化（`input_path_N` / `output_path_N`）
  - 非路径参数冻结为常量
- `code_generator.py` — 脚本生成引擎
  - 生成完整批量 Python 脚本（含 argparse、遍历目录、异常处理）
  - **In-place 保护**：检测输入=输出的工具，自动生成 `_copy_features_for_inplace()`
  - **智能参数名**：英文用关键字（`in_features=working`），中文用位置参数
  - **动态输出命名**：`{input_stem}_{step_label}.shp`，避免迭代覆盖
  - **文件发现**：基于原始输入扩展名自动选择 glob 模式
- `dependency_analyzer.py` — 简易 DAG（路径匹配依赖）
- `cli.py` — 命令行入口（`python -m geomacro`）
- 新增 3 个测试（英文键名、固定输入、in-place 工具）

**生成脚本示例：**
```python
def run_pipeline(input_file, output_dir=None):
    working = str(Path(input_file).resolve())
    out_clip = str(output_dir / f'{stem}_clip.shp')
    arcpy.analysis.Clip(working, FIXED_CLIP_FEATURES, out_clip)
```

---

### ✅ Commit 4 — 校验与可演示

**交付物：**
- `script_validator.py`（重写）— 增强预检验证器
  - 语法检查（`compile()`）
  - 中文路径警告（非ASCII字符检测）
  - 缺参检测（路径参数未被提取）
  - 失败事件标记
  - 输入/输出路径分类（输入不存在→WARN，输出未创建→INFO）
  - 分级报告输出（`summary_text()`）
- `ui_presenter.py` — 面板状态管理（无变动）
- `GeoMacroPanelViewModel.cs` — Pro 面板（新增）
  - 源过滤（Pro / Desktop / All）
  - Generate / Run / Save 按钮
  - `PythonRunner.cs` — C# 调用 Python CLI 桥接
- `GeoMacroPanel.xaml` — 完整面板 UI（事件列表+勾选、脚本预览、GridSplitter）
- 新增 5 个测试（正常/缺参/中文路径/失败项/报告格式）

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    GeoMacro 系统架构                           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ArcGIS Pro 进程                      Python 进程              │
│  ┌─────────────────────┐             ┌──────────────────────┐ │
│  │ .NET Add-in          │             │  CLI (python -m)     │ │
│  │  GpEventSubscriber   │──JSONL──→   │  history_xml_reader  │ │
│  │  EventJsonWriter     │             │  event_normalizer    │ │
│  │                      │             │  variable_extractor  │ │
│  │  GeoMacro Panel      │←──Process──│  code_generator      │ │
│  │  (WPF + C#)          │             │  script_validator    │ │
│  └─────────────────────┘             └──────────────────────┘ │
│                                                               │
│  ArcGIS Desktop / Pro XML 历史                                 │
│  %APPDATA%\ESRI\Desktop10.8\ArcToolbox\History\               │
│  %APPDATA%\ESRI\ArcGISPro\ArcToolbox\History\                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 测试结果

```
15 passed in 0.05s
```

| 测试文件 | 用例数 | 覆盖 |
|---------|--------|------|
| `test_code_generator.py` | 3 | Buffer（英文键名）、Clip（固定输入）、CalculateField（in-place） |
| `test_history_collector.py` | 3 | 事件合并、增量快照、未知成功处理 |
| `test_history_xml_reader.py` | 2 | XML 解析、目录发现 |
| `test_pipeline_e2e.py` | 1 | Buffer→Clip 完整链路 |
| `test_script_validator.py` | 5 | 正常、缺参、中文路径、失败项、报告格式 |
| `test_variable_extractor.py` | 1 | 路径变量识别 |

---

## 文件清单

### Python 模块（`src/geomacro/`）

| 文件 | 行数 | 职责 |
|------|------|------|
| `history_xml_reader.py` | ~310 | XML 历史发现/解析/容错恢复 |
| `history_parser.py` | ~143 | 历史记录→中间字典 |
| `event_normalizer.py` | ~185 | 中间字典→StandardEvent |
| `history_collector.py` | ~278 | 增量采集、合并、去重 |
| `models.py` | ~80 | 数据模型（Parameter, StandardEvent, VariableSlot 等） |
| `variable_extractor.py` | ~54 | 变量/常量提取 |
| `template_registry.py` | ~50 | 工具注册表（12 个白名单） |
| `code_generator.py` | ~270 | 脚本生成引擎 |
| `dependency_analyzer.py` | ~47 | 路径依赖建图 |
| `script_validator.py` | ~180 | 语法/路径/缺参/中文路径验证 |
| `ui_presenter.py` | ~39 | 面板状态管理 |
| `session_store.py` | ~44 | 会话持久化 |
| `cli.py` | ~90 | 命令行入口 |

### C# 模块（`addins/GeoMacroAddin/`）

| 文件 | 职责 |
|------|------|
| `GpEventSubscriber.cs` | GP 事件反射订阅 |
| `GpEventRecord.cs` | 事件 DTO |
| `EventJsonWriter.cs` | JSONL 写入 |
| `EventLogService.cs` | 日志 ring buffer |
| `GeoMacroPanelViewModel.cs` | 面板绑定与命令 |
| `GeoMacroPanel.xaml` | 面板 UI |
| `PythonRunner.cs` | Python 进程桥接 |
| `HistoryEventItem.cs` | UI 事件模型（含 IsSelected） |
| `Config.daml` | 插件清单 |

---

## Phase 2 待办

1. **扩展白名单工具** — 增加更多常用工具（如 Kriging, IDW, Slope, Aspect）
2. **通用反射方案** — 从 arcpy 工具签名自动推断参数，无需手动维护白名单
3. **面板交互编辑** — 允许用户在面板中直接修改变量名和参数值
4. **工具链可视化** — 在面板中显示 DAG 依赖图
5. **Dry-run 模式** — 生成前在临时环境中试执行
6. **Batch 脚本生成** — 支持 `.bat` / `.ps1` 输出格式
7. **跨项目支持** — 多项目历史合并
8. **错误自动回滚** — 执行失败时自动清理中间产物

---

## 实现决策回顾

| 决策点 | 选择 | 理由 |
|-------|------|------|
| 监听策略 | XML 日志轮询 + .NET 事件 | 兼容性好，实现稳定 |
| 脚本语言 | Python（不支持 BAT） | 语法简单，易调试 |
| 参数识别 | 路径自动变量 + 其它常量 | 学生团队易理解 |
| 工具匹配 | 白名单 + 中英文 tool_path 解析 | 兼容中文 ArcGIS 环境 |
| 数据交换 | JSON（本地文件） | 简化架构，无外部依赖 |
| 面板框架 | ArcGIS Pro WPF DockPane | 与 Pro 集成最紧密 |
| 构建工具 | dotnet build + 手动打包 | 绕过 CodeTaskFactory 兼容性问题 |
