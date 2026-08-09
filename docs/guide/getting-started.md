# 快速开始

## 下载

China 与 Global 版本的区别仅在于检查更新所使用的服务器，与目标游戏版本无关。

- [GitHub Releases](https://github.com/Sanheiii/ok-star-resonance/releases)
- [夸克网盘](https://pan.quark.cn/s/53ef87577da9?pwd=nVL9)

<div class="doc-alert doc-alert-danger">
  <strong>请从可信渠道下载</strong>
  <p>本项目不授权任何人售卖软件。第三方重新打包的程序可能包含恶意代码。</p>
</div>

## 安装与启动

1. 从上述渠道下载最新版本并解压或安装。
2. 如果杀毒软件拦截程序，将下载目录和安装目录加入信任区。
3. 启动《星痕共鸣》，使用 16:9 分辨率，最低 1280×720。
4. 启动 ok-star-resonance，并在设置中选择正确的客户端语言。
5. 保持游戏窗口位于前台，然后选择需要运行的任务。

## 可选内容

需要修改内置识别模板时，可以将模板仓库克隆到项目根目录的 `ok_templates`：

```powershell
git clone https://github.com/Sanheiii/ok-star-resonance-templates.git ok_templates
```

`ok_templates` 和 `midi` 都属于可选的本地内容，默认不会提交到 Git。

## 使用前检查

- 关闭显卡滤镜、锐化与游戏画面上的 FPS 叠加层。
- 游戏内使用自定义按键时，在应用设置中同步配置受支持的按键。
- 依赖抓包位置数据的任务需要选择正确的网卡，或改用 WinDivert。
- 本工具不支持后台运行，请勿遮挡或最小化游戏窗口。
