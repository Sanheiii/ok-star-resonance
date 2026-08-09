# 贡献指南

感谢你愿意为 `ok-star-resonance` 做贡献。提交修改前，请先阅读首页的[免责声明](../index.md)并确保项目能从源码运行。

## 开发约定

- 仅使用 Python 3.12。
- `requirements.in` 是直接依赖的唯一来源；修改后使用 `uv pip compile` 生成 `requirements.txt`。
- 持续任务继承 `SRTriggerTask`，一次性任务继承 `SRTask`，并在 `src/config.py` 注册。
- OCR 文本应覆盖适用的简中、繁中、英文与日文客户端。
- 游戏坐标优先使用相对画面的 0–1 比例，不直接硬编码像素坐标。
- 长循环使用框架提供的可中断等待方法，并确保异常路径释放按键和鼠标。
- 不要实现读取游戏内存、修改游戏文件或注入游戏进程的功能。

编写任务时优先参考 [ok-script API 文档](https://github.com/ok-oldking/ok-script/blob/master/docs/api_doc/README.md)。

## 提交 PR 前

1. 保持改动范围清晰，不混入无关格式化或重构。
2. 运行与改动相关的测试，并在 PR 描述中写明结果。
3. 用户可见行为发生变化时，提供截图、录屏或清晰的复现步骤。
4. 不要提交日志、截图、缓存、个人配置、真实抓包或其他敏感数据。
5. 修改 protobuf 时同时提交 `.proto` 和生成的 `_pb2.py`，并运行解析器测试。

## 文档贡献

文档源文件位于 `docs/`，导航与主题配置位于仓库根目录的 `mkdocs.yml`。新增页面后请同步更新 `nav`，并运行：

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

严格构建会把无效链接、遗漏导航等问题作为错误报告。

