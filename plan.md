## Plan: GeoMacro MVP Architecture Blueprint

目标是在几天内交付可演示的 ArcGIS Pro MVP：静默抓取用户最近 Geoprocessing 历史，自动抽取可变输入与固定参数，生成可批量遍历目录的 Python 脚本。推荐先做“稳定优先”的轮询采集路线，再扩展实时监听与复杂参数。

**Steps**
1. Phase A - 事件采集与快照基线：定义历史抓取边界（最近 N 条、成功/失败过滤、项目作用域），实现增量快照机制（基于 event_id+timestamp 去重）。此阶段输出标准原始事件列表。 
2. Phase B - 历史标准化：将不同工具历史统一映射为 StandardEvent（tool_name、ordered_params、messages、outputs）。对路径参数做规范化（绝对路径、分隔符统一、编码检测）。*depends on 1*
3. Phase C - 变量识别与依赖建图：区分常量参数与变量参数，构建工具链依赖 DAG（上游输出 -> 下游输入），识别可循环入口（通常是首工具输入目录）。*depends on 2*
4. Phase D - 代码模板与生成：按“线性流水线”生成 Python 模板（初始化、遍历目录、每步 arcpy 调用、输出命名规则、日志与异常处理）。仅支持 Python 目标，不做 BAT。*depends on 3*
5. Phase E - 预检与验证：执行脚本静态校验（语法、参数缺失、路径风险）、最小 dry-run（可选）和生成报告（可运行/需人工补参）。*depends on 4*
6. Phase F - MVP UI 闭环：提供最小面板流程：刷新历史 -> 多选步骤 -> 标记变量 -> 预览脚本 -> 保存脚本。不实现复杂流程编辑器。*parallel with 2-5 via mocked data, final integration depends on 5*
7. Phase G - 集成验收与演示脚本：在 2-3 条典型遥感流程上做端到端回归，固化演示数据与演示话术，确保课堂/答辩可稳定复现。*depends on 5 and 6*

**Architecture Lifecycle (从监听到生成)**
1. Listener/Collector：轮询 ArcGIS Pro Geoprocessing 历史，抓取新增事件。
2. Normalizer：统一事件模型并校正路径与参数顺序。
3. Extractor：识别输入/输出路径、固定参数、可变参数。
4. PipelineGraph：建立步骤依赖关系，确认执行顺序。
5. Generator：将变量槽位注入模板，生成批处理 Python。
6. Validator：输出风险清单与缺参提示。
7. Exporter：保存 .py 并附带运行说明。

**Core Modules**
1. HistoryCollector：增量拉取历史事件，负责去重与时间窗口。
2. HistoryParser：将 ArcGIS 历史记录解析为中间对象（含工具名、参数、消息）。
3. EventNormalizer：参数标准化（命名参数化、路径规范化、类型标签）。
4. VariableExtractor：抽取循环变量（输入目录、文件模式）与常量参数。
5. DependencyAnalyzer：识别工具链前后依赖，生成线性执行序列或报冲突。
6. TemplateRegistry：维护可支持工具模板及参数映射规则。
7. CodeGenerator：按模板生成 Python 脚本文本。
8. ScriptValidator：语法、路径、参数完整性检查并输出报告。
9. UIPresenter：面板状态管理与用户交互（选择、标记变量、预览、保存）。
10. SessionStore：保存当前捕获会话与用户标注，支持“重新打开继续编辑”。

**Relevant files**
- d:/Work space/GEO/GeoMacro/src/geomacro/history_collector.py - 历史增量采集与去重逻辑。
- d:/Work space/GEO/GeoMacro/src/geomacro/history_parser.py - 历史记录到中间模型解析。
- d:/Work space/GEO/GeoMacro/src/geomacro/event_normalizer.py - 参数与路径规范化。
- d:/Work space/GEO/GeoMacro/src/geomacro/variable_extractor.py - 变量/常量识别规则。
- d:/Work space/GEO/GeoMacro/src/geomacro/dependency_analyzer.py - DAG 构建与线性化。
- d:/Work space/GEO/GeoMacro/src/geomacro/template_registry.py - 工具模板注册。
- d:/Work space/GEO/GeoMacro/src/geomacro/code_generator.py - 模板渲染与脚本文本生成。
- d:/Work space/GEO/GeoMacro/src/geomacro/script_validator.py - 预检与风险输出。
- d:/Work space/GEO/GeoMacro/src/geomacro/ui_presenter.py - MVP 面板交互逻辑。
- d:/Work space/GEO/GeoMacro/tests/test_variable_extractor.py - 变量识别回归测试。
- d:/Work space/GEO/GeoMacro/tests/test_code_generator.py - 代码生成与语法回归测试。
- d:/Work space/GEO/GeoMacro/tests/test_pipeline_e2e.py - 端到端流程测试。

**Verification**
1. 采集正确性：在 ArcGIS Pro 中连续执行 5 个工具，检查抓取事件数、顺序、去重是否准确。
2. 变量识别：准备 3 组不同输入目录样本，确认输出脚本仅将预期字段参数化。
3. 生成可运行性：对生成脚本执行语法检查并在测试数据上跑通至少 2 条流程。
4. 边界测试：中文路径、超长路径、失败历史项、缺失参数四类场景均能给出明确提示。
5. UI 闭环：从“刷新历史”到“保存脚本”全链路可在 3 分钟内完成。

**Decisions**
- In scope：历史轮询抓取、线性工具链、Python 脚本生成、基础预检、MVP 面板。
- Out of scope：实时事件钩子、BAT 生成、复杂分支图编辑器、跨版本兼容层。
- 假设：ArcGIS Pro 历史可稳定读取工具参数；若某工具参数缺失，允许用户在 UI 中补充。

**Further Considerations**
1. 工具支持名单策略：Option A 白名单（推荐，快） / Option B 通用反射（慢且不稳）。
2. 变量策略：Option A 自动推断+人工确认（推荐） / Option B 全人工标注（稳但慢）。
3. 输出命名策略：Option A 基于输入文件名拼接后缀（推荐） / Option B 完全自定义模板。


**Discovery Update 2026-04-20（官方/社区联网验证）**
- 官方确认存在公开“事件级监控”而非进程级底层钩子：`ArcGIS.Desktop.Core.Events.GPExecuteToolEvent` + `GPExecuteToolEventArgs`（含 `ID`, `IsStarting`, `GPResult`, `Path`）。
- 官方确认存在“历史级读取”接口：`IGPHistoryItem`（`ToolPath`, `GPResult`, `TimeStamp`），可通过 `Project.Current.GetProjectItemContainer(Geoprocessing.HistoryContainerKey)` 获取。
- 官方确认执行入口与标志：`Geoprocessing.ExecuteToolAsync(...)` + `GPExecuteToolFlags`（`AddToHistory`, `GPThread`, `RefreshProjectItems`, `InheritGPOptions` 等）。
- 官方确认日志侧通道：
  1) Geoprocessing Options 可开启 XML 日志到 `%AppData%\Esri\ArcGISPro\ArcToolbox\History`。
  2) ArcPy `SetLogHistory(True/False)` 控制是否写外部 XML。
- 官方确认诊断通道：Diagnostic Monitor 可记录任务/HTTP/事件日志并输出到 `Documents\ArcGIS\Diagnostics`（可通过注册表 EventLogLocation 改目录），适合性能排障与行为回放，不是稳定业务 API。
- 开源社区样例已验证上述路径可落地：`GeoProcessingHistory`、`GeoProcesssingEventsWithUI`、`GeoprocessingExecuteAsync`。
- 结论：GeoMacro MVP 不建议追求“底层进程级监控（注入/Hook）”；建议采用“公开 API 事件 + 历史容器 + 可选 XML/诊断日志”三轨融合方案。


**Implementation Kickoff（执行代理接手后立即开始）**
1. Day0-0.5：创建最小工程骨架（src/geomacro, tests, docs），先跑通空白测试与打包。
2. Day0.5-1：先实现 .NET Add-in 监听 PoC（GPExecuteToolEvent 订阅 + 事件落盘 JSON），验证能捕获 ID、Path、IsStarting、GPResult 概要。
3. Day1：实现历史抓取 PoC（IGPHistoryItem 枚举），与事件流按 execute ID 和时间窗做关联去重，产出统一事件模型。
4. Day1.5：实现 VariableExtractor v1（输入/输出路径参数化 + 常量参数冻结），仅覆盖白名单工具。
5. Day2：实现 CodeGenerator v1（线性流水线 Python 生成），可从样例历史一键生成并保存脚本。
6. Day2.5：实现 ScriptValidator v1（语法校验、路径存在检查、缺参提示）与 UI 最小闭环。
7. Day3：完成 3 条典型流程回归与演示脚本固化。

**MVP Gate（每个里程碑必须过）**
- Gate A：事件监听稳定捕获，不漏连续 20 次工具执行。
- Gate B：历史回放与事件合并后，无重复、顺序正确。
- Gate C：生成脚本在至少 2 条真实流程上可运行并得到预期输出。
- Gate D：中文路径与失败历史项场景均给出明确提示而非崩溃。


**Execution Packet（实现代理首批提交批次）**
- Commit 1（监听最小闭环）
  - 目标：跑通 GP 事件捕获并落盘。
  - 交付：事件订阅器、事件 DTO、JSON 持久化、最小日志面板。
  - 验收：手工执行 5 次工具，落盘包含 execute id、tool path、is_starting、result 摘要。
- Commit 2（历史最小闭环）
  - 目标：枚举项目历史并与事件流合并去重。
  - 交付：历史读取器、统一事件模型、去重策略（ID 优先 + 时间窗兜底）。
  - 验收：同一工具重复执行时无重复条目，顺序与 History pane 一致。
- Commit 3（生成最小闭环）
  - 目标：针对白名单工具生成 Python 批处理脚本。
  - 交付：变量抽取 v1、模板注册表 v1、代码生成器 v1。
  - 验收：至少 2 条真实流程生成脚本可运行。
- Commit 4（校验与可演示）
  - 目标：生成前后给出清晰风险提示并完成 demo。
  - 交付：语法校验、路径校验、缺参提示、演示数据与回归报告。
  - 验收：中文路径、失败项、缺参项均可解释且不崩溃。

**默认实现决策（无需再等待确认）**
- 语言分层：监听与历史抓取使用 ArcGIS Pro .NET Add-in；脚本生成与规则处理可用 Python 模块。
- 数据交换：Add-in 输出统一 JSON 事件流给生成器消费（单机本地）。
- 白名单工具：Buffer、Clip、Dissolve、Merge、FeatureClassToShapefile。
- 历史策略：仅当前项目、最近 50 条、默认剔除失败项（UI 可切换显示）。
- 变量策略：输入路径与输出路径默认参数化；其余参数默认常量，允许手动改为变量。