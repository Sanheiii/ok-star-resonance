import re
from enum import Enum
import time
from re import Pattern

import numpy as np
from ok import og, Box
from qfluentwidgets import FluentIcon

from src.dungeon_config import DUNGEON_SETTINGS
from src.packet_capture.parser import ActorState
from src.tasks.ClaimMonthlyPassTask import ClaimMonthlyPassTask
from src.tasks.SRTask import SRTask

class DungeonTaskBase(SRTask):

    _SKILL_UI_ANCHOR_BOX = (0.503, 0.898, 0.509, 0.904)
    _SKILL_UI_DARK_BGR = np.array((0, 0, 4), dtype=np.int16)
    _SKILL_UI_DARK_TOLERANCE = 2
    _SKILL_UI_DARK_MIN_RATIO = 0.3
    _SKILL_GAP_BOXES = (
        (0.373, 0.881, 0.377, 0.902),
        (0.398, 0.881, 0.402, 0.902),
        (0.423, 0.881, 0.427, 0.902),
        (0.448, 0.881, 0.452, 0.902),
        (0.473, 0.881, 0.477, 0.902),
        (0.497, 0.896, 0.501, 0.912),
        (0.535, 0.875, 0.540, 0.899),
        (0.573, 0.875, 0.577, 0.899),
    )
    _AUTO_COMBAT_OUTLINE_MIN_RATIO = 0.04

    task_name = 'Unnamed Dungeon Task'
    task_name_zh = '未命名副本任务'
    task_desc = 'Task Description'
    task_desc_zh = '任务详情'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_normal_difficulty = False
        if og.app.po_translation and (catalog:=getattr(og.app.po_translation, '_catalog', None)):
            catalog[self.task_name] = self.task_name_zh
            catalog[self.task_desc] = self.task_desc_zh
        self.name = self.task_name
        self.description = self.task_desc
        self.group_name = 'Dungeon'
        self.group_icon = FluentIcon.GAME

    def get_dungeon_setting(self, key):
        """Return a shared dungeon setting, with defaults for headless tests."""
        default = DUNGEON_SETTINGS.default_config[key]
        get_global_config = getattr(self, 'get_global_config', None)
        if get_global_config is None:
            return getattr(self, 'config', {}).get(key, default)
        return get_global_config(DUNGEON_SETTINGS).get(key, default)

    def run(self):
        self._require_packet_capture()
        self.info['Entry Count'] = 0
        self.info['Pass Count'] = 0
        self.info['Pass Rate'] = '0.00%'
        self.info['Special Reward Count'] = 0
        self._last_redeem_pass_count = None

    def is_auto_combat_enabled(self):
        """Return whether the current frame shows the auto-combat skill outline."""
        return self._detect_auto_combat(self.frame)

    @classmethod
    def _detect_auto_combat(cls, frame):
        """Return auto-combat state, or ``None`` when the skill UI is hidden."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        if frame.ndim < 3 or frame.shape[2] < 3:
            return None

        anchor = cls._crop_normalized(frame, cls._SKILL_UI_ANCHOR_BOX)
        anchor_delta = np.abs(
            anchor[..., :3].astype(np.int16) - cls._SKILL_UI_DARK_BGR
        )
        dark_ratio = np.all(
            anchor_delta <= cls._SKILL_UI_DARK_TOLERANCE,
            axis=2,
        ).mean()
        if dark_ratio < cls._SKILL_UI_DARK_MIN_RATIO:
            return None

        for box in cls._SKILL_GAP_BOXES:
            gap = cls._crop_normalized(frame, box)[..., :3].astype(np.int16)
            blue, green, red = gap[..., 0], gap[..., 1], gap[..., 2]
            outline = (
                (blue >= 160)
                & (green >= 100)
                & (blue - red >= 50)
                & (blue - green >= 10)
            )
            if outline.mean() >= cls._AUTO_COMBAT_OUTLINE_MIN_RATIO:
                return True
        return False

    @staticmethod
    def _crop_normalized(frame, box):
        height, width = frame.shape[:2]
        left = max(0, min(width - 1, round(box[0] * width)))
        top = max(0, min(height - 1, round(box[1] * height)))
        right = max(left + 1, min(width, round(box[2] * width)))
        bottom = max(top + 1, min(height, round(box[3] * height)))
        return frame[top:bottom, left:right]

    def begin(self):
        self._update_pass_rate()
        if not self.find_one('menu_icon'):
            self.return_to_initial_state()
        if not self.redeem_items():
            self.log_error('购买物品失败')
            return False
        if not self.enter(self.difficulty):
            self.log_error('进入副本失败')
            return False
        return True

    def redeem_items(self):
        if not DungeonTaskBase.get_dungeon_setting(self, 'Purchase Items'):
            return True

        pass_count = self.info['Pass Count']
        purchase_interval = DungeonTaskBase.get_dungeon_setting(
            self, 'Purchase Every N Clears'
        )
        if (pass_count == 0
                or purchase_interval <= 0
                or pass_count % purchase_interval != 0
                or self._last_redeem_pass_count == pass_count):
            return True

        item_positions = (
            (0.176, 0.338), (0.296, 0.338), (0.416, 0.338),
            (0.536, 0.338), (0.657, 0.338), (0.777, 0.338),
            (0.897, 0.338),
            (0.176, 0.612), (0.296, 0.612), (0.416, 0.612),
            (0.536, 0.612), (0.657, 0.612), (0.777, 0.612),
            (0.897, 0.612),
            (0.176, 0.887), (0.296, 0.887), (0.416, 0.887),
            (0.536, 0.887), (0.657, 0.887), (0.777, 0.887),
            (0.897, 0.887),
        )

        item_index = DungeonTaskBase.get_dungeon_setting(
            self, 'Purchase Item Index'
        )
        if not 1 <= item_index <= len(item_positions):
            self.log_error(f'Purchase item index out of range: {item_index}')
            self._last_redeem_pass_count = pass_count
            return True

        season_hub_key = DungeonTaskBase.get_custom_key(self, 'Season Hub')
        self.send_key(season_hub_key, after_sleep=2)
        self.click(0.035, 0.454, after_sleep=1)
        #Detect Purchase First
        if DungeonTaskBase.get_dungeon_setting(
                self, 'Purchase Quota-limited Items First'):
            purchasable, index = self.detect_quota_limited_purchasable_item_index()
            if purchasable:
                item_index = index
                self.log_info("可被购买的index为" + str(item_index))
        # Get Position
        item_position = item_positions[item_index - 1]
        self.click(item_position[0], item_position[1], after_sleep=1)
        self.click(0.812, 0.676, after_sleep=1)
        self.click(0.633, 0.856, after_sleep=1)
        self.send_key(season_hub_key, after_sleep=0)

        self._last_redeem_pass_count = pass_count
        return True

    def detect_quota_limited_purchasable_item_index(self) -> tuple[bool, int]:
        out_of_stock_indexes = {
            self.detect_purchase_index(box)
            for box in self.ocr(0.118, 0.420, 0.834, 0.465, "已售罄")
        }
        quota_limited_indexes = [
            self.detect_purchase_index(box)
            for box in self.ocr(0.118, 0.388, 0.834, 0.415, re.compile(r'本周限购', flags=0))
        ]
        purchasable_indexes = [
            i for i in quota_limited_indexes if i not in out_of_stock_indexes
        ]
        if not purchasable_indexes:
            return False, 0
        first = min(purchasable_indexes)
        return first != 0, first

    def detect_purchase_index(self, box: Box) -> int:
        x = box.x / self.width
        index = 0
        if x < 0.235:
            index = 1
        elif x < 0.356:
            index = 2
        elif x < 0.475:
            index = 3
        elif x < 0.596:
            index = 4
        elif x < 0.717:
            index = 5
        elif x < 0.835:
            index = 6
        return index

    def wait_out_of_combat(self, time_out=300):
        self._require_packet_capture()
        inactive_since = None

        def is_out_of_combat():
            nonlocal inactive_since
            self._require_packet_capture()
            in_combat = self.in_combat or self.actor_state == ActorState.SKILL
            is_dead = self.is_dead
            if in_combat or is_dead:
                inactive_since = None
                if is_dead:
                    self.handle_death()
                return False

            now = time.monotonic()
            if inactive_since is None:
                inactive_since = now
            return now - inactive_since >= 3

        return bool(self.wait_until(is_out_of_combat, time_out=time_out))

    def wait_in_combat(self, time_out=30):
        self._require_packet_capture()

        def is_in_combat():
            self._require_packet_capture()
            return bool(self.in_combat)

        return bool(self.wait_until(is_in_combat, time_out=time_out))

    def investigate(self, pos=None):
        self.info['State'] = '准备交互开本仪器'
        self.sleep(2)
        if pos is None:
            pos = next((
                entity.get('position')
                for entity in self.nearby_entities.values()
                if entity.get('attr_id') == 10001 and entity.get('position') is not None
            ), None)
            if pos is None:
                self.log_error('没有找到开本仪器')
                return False
        self.info['State'] = f'前往开本仪器: {pos}'
        self.move_to_position(self.position, pos, target_tolerance=1.5)
        self.info['State'] = f'交互开本仪器'
        self.sleep(2)
        self.send_key('f')
        self.info['State'] = f'点击开本'
        self.sleep(1)
        self.click(0.632,0.857)
        self.info['State'] = f'等待开本读秒'
        self.sleep(8)

    def pickup_special_reward(self, entity_id):
        """Move to a nearby special reward and interact with it."""
        try:
            reward_position = next((
                entity.get('position')
                for entity in self.nearby_entities.values()
                if (entity.get('attr_id') == entity_id
                    and entity.get('position') is not None)
            ), None)
            if reward_position is None:
                return False

            self.info['State'] = '前往特殊奖励'
            if not self.move_to_position(
                    self.position,
                    reward_position,
                    target_tolerance=1.5,
                    enable_sprint=True):
                return False

            self.info['State'] = '拾取特殊奖励'
            self.send_key('f')
            self.info['Special Reward Count'] = (
                self.info.get('Special Reward Count', 0) + 1
            )
            return True
        except Exception as error:
            self.log_error(f'拾取特殊奖励失败: {error}')
            return False

    def enter(self, difficulty):
        # 交互副本入口
        self.info['State'] = '等待副本入口按钮'
        if box:=self.wait_feature('dungeon_entrance', threshold=0.7):
            self.info['State'] = '点击交互副本入口'
            self.send_key_down('lalt')
            self.sleep(0.1)
            self.click(box)
            self.sleep(0.1)
            self.send_key_up('lalt')
            self.sleep(1)
        else:
            self.log_error('没有找到副本入口')
            return False
        # 选择难度
        self.info['State'] = '等待选择难度'
        if self.wait_feature('dungeon_icon'):
            if difficulty is Difficulty.NORMAL:
                if not self.has_normal_difficulty:
                    self.log_error('没有这个难度')
                    return False
                self.click(0.092, 0.154)
            elif difficulty is Difficulty.HARD:
                self.click(0.092, 0.245 if self.has_normal_difficulty else 0.154)
            elif difficulty in (Difficulty.MASTER1, Difficulty.MASTER6):
                self.click(0.092, 0.344 if self.has_normal_difficulty else 0.245)
                self.sleep(1)
                self.info['State'] = '选择大师难度'
                self.scroll(self.width_of_screen(0.370),self.height_of_screen(0.922),-3000)
                self.sleep(1)
                pass
                if difficulty is Difficulty.MASTER1:
                    self.click(0.361,0.919)
                else:
                    self.click(0.701,0.919)
            else:
                self.log_error('没有这个难度')
                return False
            self.sleep(1)
        else:
            return False
        # 选择单双人模式
        self.info['State'] = '选择单双人模式'
        self.click(0.812,0.859)
        self.sleep(1)
        # 点击进入副本
        self.info['State'] = '点击进入副本'
        self.click(0.933,0.920)
        self.sleep(1)
        # 等待副本UI
        if not self.wait_feature('loading'):
            self.log_error('没有找到加载页面')
            return False
        self.info['State'] = '等待进本加载'
        while self.frame is None or self.find_one('loading'):
            self.sleep(1)
            self.next_frame()
        self.info['State'] = '加载完成'
        if not self.wait_feature('dungeon_scene_icon'):
            self.log_error('加载完成后没有找到副本UI')
            return False
        self.info['Entry Count'] += 1
        self.info['State'] = '已进入副本'
        return True

    def handle_end(self):
        self.info['State'] = 'Boss战结束，等待结算'
        if not self.wait_click_feature('next', box=self.box_of_screen(0.46, 0.86, 0.53, 0.92), time_out=30, raise_if_not_found=False):
            self.log_error('Boss战结束后没等到结算')
            return False
        self.info['Pass Count'] += 1
        self._update_pass_rate()
        # 点击离开
        self.wait_click_feature('exit', box=self.box_of_screen(0.88, 0.91, 0.94, 0.97), time_out=5, raise_if_not_found=False)
        self.wait_feature('loading')
        self.info['State'] = '等待出本加载'
        while self.find_one('loading'):
            self.sleep(1)
            self.next_frame()
        self.info['State'] = '本次副本成功'
        return True

    def return_to_initial_state(self):
        self.info['State'] = '副本流程出现错误，尝试退回状态'
        # 在主城不截图
        if self.scene_id != 8:
            self.screenshot('dungeon/recovery_error')
        confirm = {
            'en': 'confirm_en',
            'jp': 'confirm_jp',
            'zht': 'confirm_zht',
        }.get(self.get_game_language(), 'confirm')

        claim_monthly_pass_task = self.get_task_by_class(ClaimMonthlyPassTask)

        while True:
            if self.next_frame() is None:
                self.log_warning('Unable to capture the game window while recovering; retrying')
                self.sleep(1)
                continue

            menu_icon_white_percentage = self.calculate_color_percentage(
                {'r': (255, 255), 'g': (255, 255), 'b': (255, 255)},
                self.get_box_by_name('menu_icon'),
            )
            if 0.5 < menu_icon_white_percentage < 1.0 and self.scene_id in [8, None]:
                break

            if self.find_one('loading'):
                self.sleep(1)
                continue

            handled = False
            needs_confirmation = False

            if claim_monthly_pass_task.handle_monthly_card():
                handled = True

            elif box := self.find_one(['escape', 'leave_dungeon', 'dungeon_timeout']):
                self.click(box)
                handled = True
                needs_confirmation = True

            elif self.find_one('dungeon_scene_icon'):
                self.send_key('p')
                handled = True
                needs_confirmation = True

            elif self.find_one('single_confirm'):
                self.click(0.5, 0.74)
                handled = True

            elif self.find_one('anchor_login'):
                self.click(0.5, 0.83)
                handled = True

            elif self.find_one('anchor_select_chara'):
                self.click(0.86, 0.88)
                handled = True

            elif self.find_one(confirm):
                self.click(0.37, 0.74)
                handled = True

            elif self.calculate_color_percentage({'r': (250, 255), 'g': (250, 255), 'b': (250, 255)}, self.get_box_by_name('close')) > 0.15:
                self.send_key('esc')
                handled = True
                needs_confirmation = True

            if needs_confirmation and (box := self.wait_feature(confirm, time_out=1)):
                self.click(box)

            if not handled:
                self.send_key('esc')

            self.sleep(1)

    def _update_pass_rate(self):
        completed_entries = self.info['Entry Count']
        pass_rate = (
            self.info['Pass Count'] / completed_entries
            if completed_entries > 0
            else 0
        )
        self.info['Pass Rate'] = f'{pass_rate:.2%}'


class Difficulty(Enum):
    NORMAL = 1
    HARD = 2
    MASTER1 = 3
    MASTER6 = 4
