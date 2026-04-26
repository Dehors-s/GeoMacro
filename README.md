# GeoMacro

**从 ArcGIS 操作历史一键生成批量处理脚本**

GeoMacro 是一个 ArcGIS Pro 插件，它能**记住你刚刚做过的地理处理操作**，自动把这些操作转换成一个**可以反复使用的 Python 脚本**——而且这个脚本能批量处理一个文件夹里的所有数据。

---

## 这个项目解决什么问题？

**想象你有一个很枯燥的重复工作：**

你手上有一个文件夹，里面有 50 个 Shapefile（`.shp`）文件，你需要对每一个文件做同样的操作：先修复几何、再裁剪到指定范围、最后计算一个新字段。

**通常的做法：**
1. 打开 ArcGIS Pro
2. 对第 1 个文件执行 Repair Geometry
3. 对第 1 个文件执行 Clip
4. 对第 1 个文件执行 Calculate Field
5. 重复以上 3 步 49 次……

**GeoMacro 的做法：**
1. 在 ArcGIS Pro 中执行 1 次这 3 个工具
2. 打开 GeoMacro 面板 → 点 Refresh → 点 Generate
3. 得到一份 Python 脚本，它可以自动处理所有 50 个文件

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **历史捕获** | 自动记录你在 ArcGIS Pro / ArcGIS Desktop 中执行的地理处理操作 |
| **智能识别** | 自动区分"输入文件"（每次要换的）和"固定参数"（全程不变的） |
| **脚本生成** | 一键生成可批量运行的 Python 脚本 |
| **脚本运行** | 直接在面板里执行生成的脚本，看到结果 |
| **版本区分** | 自动识别操作来自 ArcGIS Pro 3.0 还是 ArcGIS Desktop 10.8 |
| **预检报告** | 生成脚本前先检查潜在问题（中文路径、文件不存在、语法错误等） |

### 支持的工具（白名单）

| 工具名称 | 对应的 arcpy 调用 |
|----------|-------------------|
| Buffer（缓冲区） | `arcpy.analysis.Buffer` |
| Clip（裁剪） | `arcpy.analysis.Clip` |
| Dissolve（融合） | `arcpy.management.Dissolve` |
| Merge（合并） | `arcpy.management.Merge` |
| FeatureClassToShapefile | `arcpy.conversion.FeatureClassToShapefile` |
| CalculateField（计算字段） | `arcpy.management.CalculateField` |
| RepairGeometry（修复几何） | `arcpy.management.RepairGeometry` |
| RasterCalculator（栅格计算器） | `arcpy.sa.RasterCalculator` |
| ZonalStatisticsAsTable（分区统计） | `arcpy.sa.ZonalStatisticsAsTable` |
| 更多…… | 在 `template_registry.py` 中扩展 |

---

## 系统要求

| 组件 | 要求 |
|------|------|
| **操作系统** | Windows 10 / Windows 11 |
| **ArcGIS Pro** | 3.0 或更高版本（需安装 ArcGIS Pro SDK for .NET） |
| **ArcGIS Desktop** | 10.8（可选——历史数据会从 XML 日志自动读取） |
| **Python** | 3.9+（推荐 conda 环境） |
| **.NET SDK** | 6.0（用于编译 ArcGIS Pro 插件） |
| **Visual Studio** | 2022（用于编译插件，可选——也可以用 `dotnet build`） |

---

## 快速开始（5 分钟）

### 如果你是第一次使用

#### 第一步：安装依赖

```powershell
# 克隆仓库
git clone https://github.com/Dehors-s/GeoMacro
cd GeoMacro

# 创建 Python 环境
conda env create -f environment.yml
conda activate geomacro_env

# 安装 Python 包
pip install -e .
```

#### 第二步：编译 ArcGIS Pro 插件

```powershell
cd addins\GeoMacroAddin
dotnet build /p:Configuration=Release /p:DisableArcGISPackaging=true
```

然后打包部署：

```powershell
# 以下 PowerShell 脚本一键完成：编译 → 打包 esriAddinX → 注册到 Pro
.\scripts\dev\build-addin.ps1
```

#### 第三步：在 ArcGIS Pro 中使用

1. 重启 ArcGIS Pro
2. 打开任意项目
3. 在顶部功能区找到 **GeoMacro** 标签页
4. 点击 **GeoMacro Pipeline** 按钮打开面板
5. 在 ArcGIS Pro 中执行 2-3 个地理处理工具（如 Clip、Buffer）
6. 回到 GeoMacro 面板，点 **Refresh** 加载历史
7. 点 **P** 只显示 ArcGIS Pro 的事件
8. 勾选需要的操作 → 点 **Gen** 生成脚本
9. 预览脚本 → 点 **Run** 直接运行 → 点 **Save** 保存到文件

---

## 面板使用指南

### 面板布局

```
┌──────────────────────────────────────────────┐
│ GeoMacro Pipeline                            │
├──────────────────────────────────────────────┤
│ [⟳] [All] [No] [P] [D] [*] [Gen] [Run] [Save]│
├──────────────────────────────────────────────┤
│ ☑ [P]✓ 修复几何                              │
│ ☑ [P]✓ 裁剪要素                              │
│ ☐ [D]✓ 计算字段                              │
│                                              │
│ ─ ─ ─ ─ 拖拽调整大小 ─ ─ ─ ─                │
│ ┌─ Script Preview ──────────────────────┐   │
│ │ """GeoMacro generated pipeline"""     │   │
│ │ import arcpy                          │   │
│ │ arcpy.env.overwriteOutput = True      │   │
│ │ ...                                   │   │
│ └───────────────────────────────────────┘   │
├──────────────────────────────────────────────┤
│ [Pro] 12 events, 3 selected.                 │
└──────────────────────────────────────────────┘
```

### 工具栏按钮说明

| 按钮 | 作用 |
|------|------|
| **⟳** | 刷新历史记录（从 ArcGIS Pro 的 XML 日志重新加载） |
| **All** | 全选当前列表中的所有事件 |
| **No** | 取消全选 |
| **P** | **仅显示** ArcGIS Pro 3.0 的事件 |
| **D** | **仅显示** ArcGIS Desktop 10.8 的事件 |
| **\*** | 显示所有来源的事件 |
| **Gen** | 生成 Python 批处理脚本 |
| **Run** | 直接运行生成的脚本（结果显示在预览区） |
| **Save** | 保存脚本到本地 `.py` 文件 |

### 事件列表中的标记

每条事件左侧显示：

- **☑** 复选框：勾选 = 该操作会包含在生成的脚本中
- **蓝色标签**：`P` = ArcGIS Pro 事件，`D10.8` = Desktop 10.8 事件
- **✓ / ✗**：操作成功 / 失败

---

## 命令行使用（不打开 ArcGIS Pro 也能用）

```powershell
# 激活 conda 环境
conda activate geomacro_env

# 扫描历史并生成脚本（一行命令）
python -m geomacro --lookback 720 --output-dir ./output

# 参数说明：
#   --lookback (-l)   扫描最近多少小时内的历史（默认 24）
#   --max-files (-m)  最多扫描多少个 XML 文件（默认 30）
#   --output-dir (-o) 输出目录（默认 ./output）
#   --include-failed  是否包含失败的操作
#   --quiet (-q)      静默模式，只输出摘要

# 运行生成的脚本
python output/generated_script.py --input "D:\我的数据" --output "D:\处理结果"
```

---

## 项目结构

```
GeoMacro/
├── src/geomacro/           ← Python 核心代码
│   ├── cli.py              ← 命令行入口（一键生成）
│   ├── code_generator.py   ← 脚本生成引擎
│   ├── template_registry.py ← 工具模板映射
│   ├── variable_extractor.py ← 变量识别
│   ├── script_validator.py ← 预检验证器
│   ├── history_xml_reader.py ← ArcGIS XML 历史读取
│   ├── history_parser.py   ← 历史数据规范化
│   ├── event_normalizer.py ← 事件标准化
│   ├── models.py           ← 数据模型
│   └── ...
├── addins/GeoMacroAddin/   ← ArcGIS Pro 插件（C#）
│   ├── Dockpane/           ← 面板界面
│   ├── Commands/           ← 按钮命令
│   ├── Services/           ← 服务（Python 桥接等）
│   ├── Models/             ← C# 数据模型
│   ├── Config.daml         ← 插件配置文件
│   └── GeoMacroAddin.csproj ← 项目文件
├── tests/                  ← Python 测试（15 个测试用例）
├── runtime/                ← 运行时数据（日志、历史快照）
│   └── merged/             ← 合并后的历史事件
├── docs/                   ← 文档
├── scripts/dev/            ← 开发用脚本
├── pyproject.toml          ← Python 项目配置
├── content.txt             ← 技术调研文档
└── plan.md                 ← 项目架构蓝图
```

---

## 技术栈

| 层次 | 技术 |
|------|------|
| **前端（ArcGIS Pro UI）** | C# / WPF / ArcGIS Pro SDK 3.0 |
| **后端（业务逻辑）** | Python 3.9+ / arcpy |
| **数据交换** | JSON（插件写 JSON → Python 读 JSON） |
| **事件捕获** | `GPExecuteToolEvent`（反射订阅）+ XML 日志轮询 |
| **构建工具** | dotnet build / MSBuild |
| **测试** | pytest（15 个测试，全部通过） |

---

## 工作原理（简要）

```
你操作 ArcGIS Pro
       │
       ▼
┌──────────────────┐
│ .NET Add-in      │  ← 实时监听 GPExecuteToolEvent
│ 写入 JSONL 文件   │     同时轮询 XML 历史日志
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Python 管道       │  ← 读取 JSON + XML
│ 规范化 → 合并去重  │     合并两个来源的事件
│ 变量提取 → 脚本生成 │     识别输入/输出/固定参数
│ 预检验证 → 报告    │     生成可运行的 Python 脚本
└──────┬───────────┘
       │
       ▼
    .py 脚本（可批量运行）
```

---

## 常见问题

### Q: 面板里看不到任何事件？

- 确认已在 ArcGIS Pro 中执行过地理处理工具（Clip、Buffer 等）
- 确保 ArcGIS Pro 已开启 XML 日志记录：**Geoprocessing → Geoprocessing Options → 勾选 "Write geoprocessing operations to a log file"**
- 点击面板上的 **Refresh** 按钮

### Q: 生成的脚本报错 "0 positional arguments but N given"？

- 插件会自动检测工具的参数签名。如果是中文版 ArcGIS，参数名会变成位置参数
- 脚本应该是 `arcpy.management.RepairGeometry(working, 'true', 'ESRI')` 这种形式
- 如果仍有问题，检查工具是否在白名单中

### Q: 事件太多，怎么只看 Pro 3.0 的？

点击工具栏的 **P** 按钮即可过滤。

### Q: 如何添加新的白名单工具？

编辑 `src/geomacro/template_registry.py`，在 `DEFAULT_TOOL_MAP` 中添加：

```python
"mytool": "arcpy.management.MyTool",
```

### Q: 如何重新编译插件？

```powershell
cd addins\GeoMacroAddin
.\build.ps1      # 一键编译 + 打包 + 注册
# 或手动：
dotnet build /p:Configuration=Release /p:DisableArcGISPackaging=true
```

然后重启 ArcGIS Pro。

---

## 许可证

本项目仅供学习和研究使用。ArcGIS Pro 和 arcpy 是 Esri 公司的产品。
