<div align="center">
  <h1 align="center">
    <img src="icons/icon.png" width="200"/>
    <br/>
    ok-star-resonance
  </h1> 
<h3><i>基于图像识别或网络抓包的星痕共鸣自动化, 使用windows接口模拟用户点击, 无读取游戏内存或侵入修改游戏文件/数据.</i></h3>
</div>

![Static Badge](https://img.shields.io/badge/platfrom-Windows-blue?color=blue)
[![GitHub release (with filter)](https://img.shields.io/github/v/release/sanheiii/ok-star-resonance)](https://github.com/sanheiii/ok-star-resonance/releases)
[![GitHub all releases](https://img.shields.io/github/downloads/sanheiii/ok-star-resonance/total)](https://github.com/sanheiii/ok-star-resonance/releases)

# 免责声明

本软件是一个外部工具，它仅通过现有用户界面与游戏交互，并遵守相关法律法规。该软件包旨在简化用户与游戏的交互，不会破坏游戏平衡或提供不公平优势，也不会修改任何游戏文件或代码。

本软件开源、免费，仅供个人学习交流使用，仅限于个人游戏账号，不得用于任何商业或营利性目的。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目及开发者团队无关。若您发现商家使用本软件进行代练并收费，这是商家的个人行为，本软件不授权用于代练服务，产生的问题及后果与本软件无关。本软件不授权任何人进行售卖，售卖的软件可能被加入恶意代码，导致游戏账号或电脑资料被盗，与本软件无关。

### 下载

**China与Global版区别仅在于检查更新使用的服务器不同，与目标游戏的版本无关**
* [GitHub下载](https://github.com/sanheiii/ok-star-resonance/releases)
* [夸克网盘](https://pan.quark.cn/s/53ef87577da9?pwd=nVL9)

### 功能
*如果你希望支持你的语言，请提交issue，可能会要求你上传一些游戏截图*

| 功能名       | 简中 | 繁中 | 英文 | 日文 |             注释             |
|:----------| :---: | :---: | :---: |:--:|:--------------------------:|
| 钓鱼        | ● | ● | ● | ●  |
| 领取月卡      | ● | ● | ● | ●  |
| 简易采集      | ● | ● | ● | ●  |        日文文本过长换行时会出错        |
| 将鼠标指向购买按钮 | ● |  | ● |    |
| 连点技能      | ● | ● | ● | ●  |
| 同意组队      | ● | ● | ● | ●  |
| 确认进入副本    | ● | ● | ● |    |         繁中不支持进入活动          |
| 协会狩猎      | ● | ● |  |    |
| 演奏MIDI    | ● | ● | ● | ●  |
| 打麻将       | ● |  | ● | ●  |
| 演奏教学谱面    | ● | ● | ● | ●  |
| 刷单人副本     | ● | ● | ● | ●  | 其它语言可能无法在赛季商店优先购买限购商品 |

### 特性

1. 能够任意16：9分辨率下运行,可窗口化,可全屏,屏幕缩放比例无要求
2. 不可后台运行
3. 基于PushDeer的状态通知，使用方法参考[PushDeer官方说明](https://www.pushdeer.com/)
4. 支持用户自定义脚本

### 待办

1. 使用抓包获取实体进行采集
2. 钓鱼重构为一次性任务

### 出现问题请检查

有问题点这里, 挨个检查再提问:

1. **非中文客户端遇到问题** 前往本程序的设置中指定游戏客户端的语言
2. **只能/不能进行专注采集** 采集依赖文字识别，调整视角不要让任务引导叠加在采集按钮下干扰识别
3. **解压问题:** 将压缩包解压到仅包含英文字符的目录中。
4. **杀毒软件干扰:** 将下载和解压目录添加到您的杀毒软件/Windows Defender 白名单中。
5. **显示设置:** 确保游戏使用16：9的分辨率，关闭显卡滤镜和锐化。使用默认游戏亮度并禁用在游戏上显示FPS(如小飞机)。
6. **自定义按键绑定:** 如没有使用默认按键，请在APP中设置, 不在设置里的按键不支持。
7. **版本过旧:** 确保您使用的是最新版本的 ok-star-resonance。
8. **进一步帮助:** 如果问题仍然存在，请提交产生错误时的屏幕截图及脚本日志。
9. **副本中移动错误** 修改抓包的目标网卡或使用WinDivert抓包

### Python 源码运行

仅支持Python 3.12

```
git clone https://github.com/Sanheiii/ok-star-resonance.git
cd ok-star-resonance
git clone https://github.com/Sanheiii/ok-star-resonance-templates.git ok_templates # 可选，如需修改内置模板，clone此项目到ok_templates文件夹
pip install -r requirements.txt --upgrade # 安装python依赖，更新代码后可能需要重新运行
python main_debug.py # 运行 Debug 版
python main.py # 运行 Release 版
```

### 致谢

* 本程序基于[ok-script](https://github.com/ok-oldking/ok-script)开发。

### 文档网站

安装、功能兼容性、疑难解答与开发说明已整理到 [MkDocs 文档](docs/index.md)。

```powershell
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

使用 `python -m mkdocs build --strict` 可在 `site/` 生成可部署的静态 HTML。
