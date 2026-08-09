# 从源码运行

本项目仅支持 Windows 与 Python 3.12。建议使用 [uv](https://docs.astral.sh/uv/) 管理本地虚拟环境。

## 准备环境

```powershell
git clone https://github.com/Sanheiii/ok-star-resonance.git
cd ok-star-resonance
uv venv --python 3.12
uv pip sync requirements.txt
```

## 启动程序

```powershell
# 开发模式：开启调试日志和截图
.\.venv\Scripts\python.exe main_debug.py

# 发布模式
.\.venv\Scripts\python.exe main.py
```

## 运行测试

```powershell
# 运行仓库中的全部 unittest 文件
.\run_tests.ps1

# 运行不依赖真实游戏窗口的单个测试
.\.venv\Scripts\python.exe -m unittest tests.test_packet_parser
```

`tests/TestMain.py` 依赖测试截图和 `ok.test.TaskTestCase`，缺少 `tests/images/test.png` 时不能作为可靠的无头测试。

## 构建文档网站

文档依赖与应用依赖分开管理：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-docs.txt
.\.venv\Scripts\python.exe -m mkdocs serve
```

浏览器访问终端显示的本地地址即可预览。生成静态 HTML：

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

生成结果位于 `site/`，可部署到 GitHub Pages 或任意静态网站托管服务。

