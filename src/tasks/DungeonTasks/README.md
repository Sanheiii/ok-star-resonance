# 副本脚本编写教程

本文面向准备编写副本脚本的第三方开发者。通过截图、OCR、模板匹配、抓包状态以及模拟键鼠操作游戏 UI 的 Python 任务，不应读取游戏内存、修改游戏文件或向游戏进程注入代码。

## 1. 开始之前

- 启动并正确配置 Npcap 抓包。`DungeonTaskBase.run()` 会检查抓包状态；世界坐标、场景、战斗状态和附近实体也都依赖抓包数据。
- 游戏窗口必须在前台，画面比例为 16:9，分辨率不低于 1280×720。
- 开发时使用 `main_debug.py`，并先手动验证每一段移动、交互和异常恢复。大部分副本流程无法用无头单元测试完整验证。

现有的各 `DungeonTask` 也可以作为完整示例。

## 2. 最小脚本模板

在本目录新建与类同名的模块，例如 `Dungeon0000Task.py`。下面的模板故意在副本主体处抛出异常，避免尚未填写的脚本误操作；

```python
from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon0000Task(DungeonTaskBase):

    # 开本仪器的世界坐标，填写 (X, Z) 或抓包返回的 (X, Y, Z)。
    INSTRUMENT_POSITION = (0.0, 0.0)  # TODO: 填写

    def __init__(self, *args, **kwargs):
        # 英文原文与中文翻译必须在 super().__init__() 前赋值，基类会在
        # 初始化时读取并注册它们。
        self.task_name = "Example Dungeon - Hard"
        self.task_name_zh = "示例副本 - 困难"
        self.task_desc = "Automatically clears Example Dungeon - Hard."
        self.task_desc_zh = "自动通关示例副本 - 困难。"
        super().__init__(*args, **kwargs)

        self.difficulty = Difficulty.HARD
        # DungeonTaskBase 初始化时会把此值设为 False；支持普通难度时必须改成 True。
        self.has_normal_difficulty = False

    def run(self):
        # 检查抓包状态及初始化数据跟踪。
        super().run()
        while True:
            if not self.exec():
                self.return_to_initial_state()

    def exec(self):
        # 回到可进本状态、按配置购买物品、选择难度并进入副本。
        if not self.begin():
            return False

        # 前往并启动开本仪器。传入坐标比自动搜索更稳定。
        self.investigate(self.INSTRUMENT_POSITION)

        if not self._run_dungeon_flow():
            return False

        # Boss 已击败且脱战后再调用。它会等待结算、增加成功次数并离本。
        return self.handle_end()

    def _run_dungeon_flow(self):
        # ===== 第三方开发者填写区域：道中、机关与 Boss =====
        # 建议拆成多个返回 bool 的小方法；任何一步失败都 return False，
        # 外层会调用 return_to_initial_state() 恢复。
        #
        # 下面示例完成两次移动后等待一场战斗结束：
        # route1 = (
        #     (12.34, 56.78),  # TODO: 按实际路线填写每一个移动节点的 (X, Z)
        #     (23.45, 67.89),
        # )
        # if not self._follow_route(route1, "道中第一波"):
        #     return False
        # if not self.wait_in_combat(time_out=15):
        #     self.log_error("没有进入战斗")
        #     return False
        # if not self.wait_out_of_combat(time_out=180):
        #     self.log_error("战斗超时")
        #     return False
        raise NotImplementedError("请填写当前副本的道中、机关和 Boss 流程， 完成后移除本行代码")
        # ===== 填写区域结束 =====

    def _follow_route(self, route, state):
        self.info['state'] = state
        remaining = self.move_to_positions(
            route,
            line_tolerance=2,
            node_tolerance=2,
            max_path_deviation=8,
            enable_sprint=True,
        )
        if remaining is not None:
            self.log_error(f"移动失败，剩余路径: {remaining}")
            return False
        return True
```

然后在 `src/config.py` 的 `onetime_tasks` 中注册模块和类：

```python
["src.tasks.DungeonTasks.Dungeon0000Task", "Dungeon0000Task"],
```

模块名、类名和注册项必须完全一致。重新启动程序后，任务会出现在 `副本` 分组中。

## 3. 推荐的填写方式

`move_to_positions()` 成功时返回 `None`，失败时返回尚未完成的节点列表，因此不要写成 `if not self.move_to_positions(...)`。单点移动 `move_to_position()` 才是成功返回 `True`、失败返回 `False`。

自动战斗键不要写死为 `h`，应读取用户键位：

```python
self.send_key(self.get_custom_key("Auto Battle"))
```

可用的项目自定义动作目前包括 `自动战斗`、`飘浮`、`幻影冲刺` 和 `切换走跑`。普通按键、按下和释放分别使用 ok-script 提供的 `send_key()`、`send_key_down()`、`send_key_up()`。需要长按时优先使用 `send_key(..., down_time=秒数, after_sleep=按下后休眠时间)`；如果手工按下按键，必须保证失败、异常和任务禁用路径也会释放它。

## 4. `DungeonTaskBase`提供的功能

`DungeonTaskBase` 继承自 `SRTask`，提供一些副本实用功能。

`BaseTask`提供截图、识别、等待、点击和键盘输入等通用能力，请查阅 [ok-script API 文档](https://github.com/ok-oldking/ok-script/blob/master/docs/api_doc/README.md)。

| 成员 | 参数与返回值  | 用途和注意事项                                                      |
| --- |---------|--------------------------------------------------------------|
| `wait_in_combat(time_out=15)` | 返回 `bool` | 等待进入战斗。超时返回 `False`。                                         |
| `wait_out_of_combat(time_out=300)` | 返回 `bool` | 等待连续 3 秒处于非战斗状态；检测到死亡时会调用 `handle_death()`。超时未结束战斗返回 `False` |
| `is_auto_combat_enabled()` | 返回 `True`、`False` 或 `None` | 从当前画面的技能 UI 判断自动战斗是否开启；技能 UI 不可见时返回 `None`。                  |
| `handle_end()` | 成功 `True`，失败 `False` | Boss 战结束后等待结算按钮、点击离开并等待加载结束。                                 |
| `return_to_initial_state()` | 无有意义返回值 | 截图并处理离本、关闭弹窗、月卡等情况，直到回到可重新进本的初始状态。用于本轮失败后的恢复。                |

在`最小脚本模板`中已调用而开发者无需关心的方法

| 成员 | 参数与返回值 | 用途和注意事项 |
| --- | --- | --- |
| `run()` | 无返回要求 | 检查抓包并初始化进入次数、通关次数和通关率。子类覆盖时必须先调用 `super().run()`。 |
| `begin()` | 成功 `True`，失败 `False` | 尝试恢复到初始界面，按配置购买物品，再以 `self.difficulty` 进入副本。每轮 `exec()` 开头调用。 |
| `enter(difficulty)` | `Difficulty`；返回 `bool` | 选择难度与单人模式并进入副本。通常由 `begin()` 调用。 |
| `redeem_items()` | 返回 `bool` | 根据购买配置操作兑换界面。通常由 `begin()` 调用。 |
| `investigate(pos=None)` | `pos` 为 `(X, Z)` 或 `(X, Y, Z)` | 移动到开本仪器并交互；省略 `pos` 时会搜索 `attr_id == 10001` 的附近实体。此方法成功时没有显式返回值。 |

可选难度为：

- `Difficulty.NORMAL`：普通；只有 `has_normal_difficulty = True` 时可选。
- `Difficulty.HARD`：困难。
- `Difficulty.MASTER1`：大师难度1。
- `Difficulty.MASTER6`：大师难度6。

设置页还提供以下副本通用配置：

- `Purchase Items`：是否购买物品，默认 `False`。
- `Purchase Every N Clears`：每成功通关多少次购买一次，默认 `8`。
- `Purchase Item Index`：购买界面中的物品序号，从 1 开始，当前有效范围为 1–21，默认 `1`。

若要增加当前副本自己的配置，在 `super().__init__()` 后调用 `self.default_config.update({...})`，运行时通过 `self.config.get("配置名", 默认值)` 读取。

## 5. `SRTaskBase` 提供的信息

下列属性来自抓包数据。使用它们之前应确保抓包已启动；位置或状态尚未同步时可能是 `None`。

| 属性 | 内容 |
| --- | --- |
| `packet_capture_tool` / `packet_capture` | 当前抓包工具对象。 |
| `position` | 玩家世界坐标，通常为 `(X, Y, Z)`；移动函数只使用 X、Z。 |
| `scene_id` | 当前场景 ID。 |
| `player_id` / `player_uuid` | 当前玩家标识。 |
| `nearby_entities` | 附近实体字典。常用字段有 `attr_id`、`entity_type` 和 `position`。数据会变化，应在等待循环中重新读取。 |
| `in_combat` | 是否处于战斗相关状态。业务代码通常把它当作真/假值，等待时优先使用 `wait_in_combat()` 和 `wait_out_of_combat()`。 |
| `actor_state` | `ActorState`，尚未同步时可能为 `None`。 |
| `is_dead` | 是否处于死亡或复活状态。 |

`_require_packet_capture()` 会在抓包工具未运行时抛出 `PacketCaptureRequiredError`，成功时返回抓包工具。`DungeonTaskBase.run()` 和移动方法已经调用它；如果自定义逻辑直接依赖上述抓包属性，也可以在入口处主动调用以快速失败。

需要等某个实体出现时，使用可中断的 `wait_until()`，不要写长时间阻塞的 `time.sleep()`：

```python
    def _wait_for_entity_position(self, attr_id, time_out=10):
        result = {"position": None}

        def find_entity():
            result["position"] = next((
                entity.get("position")
                for entity in self.nearby_entities.values()
                if (entity.get("attr_id") == attr_id
                    and entity.get("position") is not None)
            ), None)
            return result["position"] is not None

        if not self.wait_until(find_entity, time_out=time_out):
            return None
        return result["position"]
```

`attr_id` 和 `entity_type` 必须在目标副本中实测，不要假设其他副本的 ID 可复用。

## 6. `SRTaskBase` 提供的移动与镜头功能

### `move_to_position(...)`

```python
move_to_position(
    start_position,
    target_position,
    line_tolerance=2,
    target_tolerance=2,
    max_path_deviation=None,
    enable_sprint=False,
    rotate_camera=True,
    camera_offset=0,
)
```

- `start_position`：规划线段起点，通常传当前的 `self.position`。
- `target_position`：目标世界坐标，可为 `(X, Z)` 或 `(X, Y, Z)`。
- `line_tolerance`：沿规划路线移动时允许的横向误差。
- `target_tolerance`：判定到达目标的距离容差。
- `max_path_deviation`：与规划路线最大允许偏离，如果超过此值中止本次移动；`None` 表示不按此条件中止。
- `enable_sprint`：是否使用冲刺。
- `rotate_camera`：是否自动识别并修正镜头朝向。如果为 `False` 则只使用移动方向键而不转动镜头。
- `camera_offset`：镜头相对移动方向的水平偏转角；正数顺时针向右。比如 `90` 会让镜头看向移动方向右侧，并以 `A` 代替 `W` 横向移动。
- 返回值：到达为 `True`；停滞、偏离路线过大、加载或场景变化等失败为 `False`。移动中死亡会先尝试复活再继续。

### `move_to_positions(...)`

```python
move_to_positions(
    positions,
    line_tolerance=2,
    node_tolerance=2,
    max_path_deviation=None,
    enable_sprint=False,
    rotate_camera=True,
    camera_offset=0,
)
```

- `positions`：按顺序经过的世界坐标可迭代对象。
- `node_tolerance`：每个路线节点的到达容差。
- 其余参数含义与单点移动相同。
- 返回值：全部到达时为 `None`；失败时为包含当前失败节点在内的剩余节点列表。
  - 注意：如果使用`if move_to_positions(...)`判断移动是否成功而不使用其返回的剩余路径时，应当注意结果与直觉`相反`，即：移动成功时`不会进入`分支

### 镜头及其他辅助方法

| 方法 | 参数与行为                                                                      |
| --- |----------------------------------------------------------------------------|
| `detect_camera_direction()` | 从当前小地图识别镜头偏航角，更新并返回 `camera_direction`。识别失败时会保留旧角度；是否成功记录在内部状态中。           |
| `rotate_camera(degrees)` | 水平旋转相对角度；正数向顺时针，负数向逆时针。                                                    |
| `look_at(target)` | `target` 可为绝对角度或世界坐标。角度约定为 0 指向北方、90 指向东方；成功旋转返回 `True`，无法识别镜头时返回 `False`。 |
| `handle_death(time_out=45)` | 检测到死亡时尝试点击复活，直到完成复活，最多等待指定秒数。移动函数与等待战斗函数会自动使用它。                            |
| `get_custom_key(action)` | 返回用户配置的动作按键，不存在用户配置时使用项目默认值。                                               | |
| `get_game_language()` | 返回 `zhs`、`zht`、`jp` 或 `en`。编写客户端语言有关的识别时应使用其返回值判断语言。                       |

## 7. 继承自 ok-script 的常用能力

副本任务能直接使用 ok-script `BaseTask` 的接口。准确签名和完整行为以 [ok-script API 文档](https://github.com/ok-oldking/ok-script/blob/master/docs/api_doc/README.md) 为准，项目中常见的有：

- 帧与模板：`next_frame()`、`find_one()`、`wait_feature()`、`wait_click_feature()`。
- 输入：`click()`、`scroll()`、`send_key()`、`send_key_down()`、`send_key_up()`。
- 等待：`sleep()`、`wait_until()`。它们可响应任务禁用，长流程应优先使用，不要用长时间阻塞的 `time.sleep()`。
- 相对屏幕坐标：`box_of_screen()`、`width_of_screen()`、`height_of_screen()`。屏幕位置统一使用 0–1 比例；某个 API 需要像素时再通过这些方法换算，不要写死像素值。
- 诊断与界面：`screenshot()`、`log_error()`、`self.info["State"]`。

## 8. 开发流程省流

1. 参考 [最小脚本模板](#2-最小脚本模板) 一节创建新任务
2. 运行本程序，在抓包工具正确设置网卡，然后开始抓包，如果设置正确，在游戏内移动时，本程序中的玩家坐标将会实时刷新。
3. 进入副本，在副本中记录需要使用的开本仪器、路线节点、机关、怪物和 Boss 的坐标或其它实体的 ID或位置，距离更近的实体将会位于实体列表的更上方。
4. 编写逐段移动代码，在需要战斗的地方依次调用`wait_in_combat()``wait_out_of_combat()`并设置合理超时。
5. 所有可能失败的步骤都返回 `False` 并写入 `log_error()`，让外层恢复。
6. 调整各处延时，防止在无法控制角色的时候提前作出下一步操作
7. 用 `self.info["State"]` 标注当前阶段，便于用户和日志定位卡点。
