# AGENTS.md

本文件面向在本仓库中工作的自动化代理。除非用户另有要求，修改代码时遵循以下约定。

## 项目概览

`ok-star-resonance` 是仅支持 Windows 的 Python 3.12 桌面自动化工具，用于《星痕共鸣》。程序通过屏幕捕获、OCR、模板匹配、目标检测和模拟键鼠与游戏 UI 交互；不要引入读取游戏内存、修改游戏文件或注入游戏进程的实现。

核心依赖和子系统：

- `ok-script`：任务生命周期、窗口捕获、OCR、输入模拟和 GUI 框架。
- PySide6 / QFluentWidgets：桌面界面。
- OpenCV、OpenVINO、ONNX Runtime DirectML：视觉与目标检测。
- `src/packet_capture/`：基于 Npcap 的网络包捕获、TCP 重组和 protobuf 解码。
- `src/tasks/`：一次性任务和持续触发任务。

程序需要前台游戏窗口，目标游戏分辨率必须为 16:9，最低为 1280×720。

## 重要目录与入口

- `main.py`：发布模式入口。
- `main_debug.py`：开启调试日志和截图的开发入口。
- `src/config.py`：应用配置、游戏窗口规则、任务和自定义页签注册中心。
- `src/globals.py`：挂载在 `ok.og` 上的进程级共享状态。
- `src/tasks/SRTaskBase.py`：一次性与触发任务共享的游戏、移动和抓包辅助方法。
- `src/tasks/SRTask.py`：一次性任务基类。
- `src/tasks/SRTriggerTask.py`：持续触发任务基类。
- `i18n/zh_CN/LC_MESSAGES/ok.po"`：i18n文件，简单维护英文原文和中文翻译
- `src/gui/`：自定义 Qt 界面。
- `src/packet_capture/`：抓包设备绑定、协议解析和线程安全状态。
- `src/packet_capture/proto/BlueProtobuf.proto`：仓库维护的最小线协议定义。
- `src/packet_capture/proto/BlueProtobuf_pb2.py`：由 `.proto` 生成；不要手工编辑。
- `assets/coco_annotations.json`、`assets/images/`：模板匹配标注和图像，由程序自身处理`ok_templates/`目录下的文件产生。
- `configs/`、`logs/`、`screenshots/`：运行时产物，不应提交。
- `ok_templates/`、`midi/`：可选的本地内容，默认被 Git 忽略。

## 环境与常用命令

只使用 Python 3.12。`requirements.in` 是直接依赖的唯一来源，`requirements.txt` 是由其生成的完整锁定清单。修改依赖时编辑 `requirements.in`，不要直接手工维护 `requirements.txt`。

```powershell
# 修改 requirements.in 后重新生成锁定清单
uv pip compile requirements.in --output-file requirements.txt

# 首次创建 Python 3.12 虚拟环境
uv venv --python 3.12

# 严格按锁定清单同步虚拟环境
uv pip sync requirements.txt

# 开发运行
.\.venv\Scripts\python.exe main_debug.py

# 发布模式运行
.\.venv\Scripts\python.exe main.py

# 运行全部 unittest 文件（仓库脚本会逐文件运行，包括 TestMain.py）
.\run_tests.ps1

# 运行无需真实游戏窗口的单个测试
.\.venv\Scripts\python.exe -m unittest tests.test_packet_parser
```

`tests/TestMain.py` 是依赖 `ok.test.TaskTestCase` 和测试截图的集成式测试骨架；本地缺少 `tests/images/test.png` 时不能把它当作可靠的无头测试。新增纯逻辑测试时使用 `test_*.py` 命名，并尽量避免 GUI、游戏窗口、Npcap 和硬件依赖。

重新生成 protobuf：

```powershell
.\.venv\Scripts\python.exe -m grpc_tools.protoc `
  --proto_path=src\packet_capture\proto `
  --python_out=src\packet_capture\proto `
  src\packet_capture\proto\BlueProtobuf.proto
```

仅在确实修改了 `.proto` 且环境安装了 `grpcio-tools` 时运行。提交时应同时包含 `.proto` 和生成的 `_pb2.py`，并运行解析器测试。

## 任务架构

任务分为两类：

- 持续响应游戏状态的任务继承 `SRTriggerTask`，并注册到 `src/config.py` 的 `trigger_tasks`。
- 用户手动执行的一次性流程继承 `SRTask` 或在不需要共享能力时继承 `ok.BaseTask`，并注册到 `onetime_tasks`。

新增任务时：

1. 在 `src/tasks/` 创建与类同名的模块。
2. 在 `__init__` 中调用 `super()`，设置 `name`、`description`，并通过 `default_config.update(...)` 添加配置。
3. 将主流程放在 `run()`，拆分较长的识别与操作步骤。
4. 在 `src/config.py` 注册模块路径和类名。
5. 为语言相关 OCR 文本补齐适用的 `zhs`、`zht`、`en`、`jp` 正则；不要假设只运行简中客户端。
6. 为可独立验证的解析、坐标换算或状态逻辑添加测试。

任务执行可能随时被禁用。长循环和等待优先使用框架提供的 `self.sleep()`、`wait_until()` 等可中断方法，不要用长时间的阻塞 `time.sleep()`。模拟按键后必须确保异常和禁用路径能够释放按键或鼠标；涉及线程的任务应避免直接从工作线程操作 Qt 控件。

## 坐标、视觉和语言约定

- 游戏区域坐标通常使用相对于画面的 0–1 比例；优先使用 `box_of_screen()`、`width_of_screen()`、`height_of_screen()` 等框架转换方法。
- 不要写死仅适用于某个像素分辨率的坐标。改动需兼容配置声明的 16:9 分辨率集合。
- 模板应加入 `assets/images/` 并同步维护 `assets/coco_annotations.json`；不要用运行时截图替代正式资源。
- OCR 匹配优先复用 `get_game_language()` 和任务的 `regex_map`。
- 保持源文件为 UTF-8。仓库中部分中文在某些 Windows PowerShell 输出编码下会显示为乱码；在确认文件真实编码前，不要批量“修复”中文或整文件重写。

## 抓包子系统约定

- Npcap 是 Windows 上的可选运行时依赖。没有 Npcap 或没有真实流量时，解析器和状态层仍应可导入、可测试。
- 网络输入不可信：帧长度、偏移、压缩数据和 protobuf 解码必须保留边界检查与失败隔离。
- `PacketCaptureData` 由捕获线程写入、GUI/任务线程读取；修改共享状态时保持其锁语义。
- 依赖抓包位置数据的任务应通过 `SRTaskBase._require_packet_capture()` 或等价的明确检查快速失败，不要静默使用陈旧位置。
- 修改 TCP 重组、压缩或消息 ID 映射时，优先添加小型二进制夹具单元测试，不要提交真实用户抓包或敏感网络数据。

## 代码与变更规范

- 遵循现有 Python 风格：4 空格缩进、模块使用绝对导入、类使用 PascalCase、方法和变量使用 snake_case。
- 新代码可使用 Python 3.12 类型语法，但不要为无关旧代码做大范围格式化或类型改写。
- 保持变更聚焦；不要顺手提交 `configs/`、`logs/`、`screenshots/`、缓存、模型、MIDI 或本地模板。
- 不要手工修改生成的 `requirements.txt`、protobuf 或构建产物。
- 不要覆盖用户工作树中的未提交修改。开始和结束前检查 `git status --short`，只处理当前任务涉及的文件。
- 绝大多数功能均需游戏实机测试，修改完成后无需构建与测试。
- 用户可能在两次对话之间手动修改部分代码，不要撤销用户修改的这部分代码。
