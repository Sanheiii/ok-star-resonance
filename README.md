<div align="center">
  <h1 align="center">
    <img src="icons/icon.png" width="200"/>
    <br/>
    ok-star-resonance
  </h1> 
<h3><i>基于图像识别的星痕共鸣自动化, 使用windows接口模拟用户点击, 无读取游戏内存或侵入修改游戏文件/数据.</i></h3>
</div>

![Static Badge](https://img.shields.io/badge/platfrom-Windows-blue?color=blue)
[![GitHub release (with filter)](https://img.shields.io/github/v/release/sanheiii/ok-star-resonance)](https://github.com/sanheiii/ok-star-resonance/releases)
[![GitHub all releases](https://img.shields.io/github/downloads/sanheiii/ok-star-resonance/total)](https://github.com/sanheiii/ok-star-resonance/releases)

# 免责声明

本软件是一个外部工具，旨在自动化星痕共鸣的游戏玩法。它仅通过现有用户界面与游戏交互，并遵守相关法律法规。该软件包旨在简化用户与游戏的交互，不会破坏游戏平衡或提供不公平优势，也不会修改任何游戏文件或代码。

本软件开源、免费，仅供个人学习交流使用，仅限于个人游戏账号，不得用于任何商业或营利性目的。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目及开发者团队无关。若您发现商家使用本软件进行代练并收费，这是商家的个人行为，本软件不授权用于代练服务，产生的问题及后果与本软件无关。本软件不授权任何人进行售卖，售卖的软件可能被加入恶意代码，导致游戏账号或电脑资料被盗，与本软件无关。

### 下载

* [GitHub下载](https://github.com/sanheiii/ok-star-resonance/releases)
* [夸克网盘](https://pan.quark.cn/s/53ef87577da9?pwd=nVL9)

### 功能

1. 钓鱼
2. 简易采集

### 特性

1. 能够任意16：9分辨率下运行,可窗口化,可全屏,屏幕缩放比例无要求
2. 不可后台运行
3. AI识别鱼位置，精准摆竿

### 待办
1. 训练一个采集点识别模型低头采集查找采集点并寻路
2. 将钓鱼重构为一次性任务以提高连点性能

### 低优先级
2. 购买鱼饵和鱼竿，目前用户可以提前买好

### 出现问题请检查

有问题点这里, 挨个检查再提问:

1. **溜鱼方向错误:** 钓鱼界面按O关闭他人和自己的角色名显示，并确保自己所在的钓点没有船，这些元素目前可能会错误识别为水花
2. **拉鱼速度慢，溜鱼延迟大:** 脚本性能受限，可以降低游戏分辨率以提高脚本刷新率，如果在白天挂可以关闭自动点月卡功能
3. **只能/不能进行专注采集** 采集依赖文字识别，调整视角不要让任务引导叠加在采集按钮下干扰识别
4. **解压问题:** 将压缩包解压到仅包含英文字符的目录中。
5. **杀毒软件干扰:** 将下载和解压目录添加到您的杀毒软件/Windows Defender 白名单中。
6. **显示设置:** 确保游戏使用16：9的分辨率，关闭显卡滤镜和锐化。使用默认游戏亮度并禁用在游戏上显示FPS(如小飞机)。
7. **自定义按键绑定:** 如没有使用默认按键，请在APP中设置, 不在设置里的按键不支持。
8. **版本过旧:** 确保您使用的是最新版本的 ok-star-resonance。
9. **进一步帮助:** 如果问题仍然存在，请提交产生错误时的屏幕截图及脚本日志。

### Python 源码运行

仅支持Python 3.12

```
#CPU版本, 使用openvino
pip install -r requirements.txt --upgrade #install python dependencies, 更新代码后可能需要重新运行
python main.py # run the release version
python main_debug.py # run the debug version
```

### 致谢

* 本程序基于[ok-script](https://github.com/ok-oldking/ok-script)开发。
