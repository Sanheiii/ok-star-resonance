from enum import Enum
import time

from ok import og
from qfluentwidgets import FluentIcon

from src.tasks.SRTask import SRTask

class DungeonTaskBase(SRTask):

    task_name = 'Unnamed Dungeon Task'
    task_name_zh = '未命名副本任务'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_normal_difficulty = False
        if og.app.po_translation and (catalog:=getattr(og.app.po_translation, '_catalog', None)):
            catalog[self.task_name] = self.task_name_zh
        self.name = self.task_name
        self.group_name = 'Dungeon'
        self.group_icon = FluentIcon.GAME

    def run(self):
        self._require_packet_capture()
        self.info['entry_count'] = 0
        self.info['win_count'] = 0

    def begin(self):
        if not self.enter(self.difficulty):
            self.log_error('进入副本失败')
            return False
        return True

    def move_to_position(self, start_position, target_position, line_tolerance=2,
                         target_tolerance=2):
        """Revive after a death interruption, then retry the current target."""
        while True:
            completed = super().move_to_position(
                start_position,
                target_position,
                line_tolerance=line_tolerance,
                target_tolerance=target_tolerance,
            )
            if completed:
                return True
            self.handle_death()
            start_position = self.position

    def move_to_positions(self, positions, line_tolerance=2, node_tolerance=2):
        """Revive as needed and continue until every path node is reached."""
        remaining = list(positions)
        while remaining:
            start = self.position
            if start is None:
                return remaining
            for index, target in enumerate(remaining):
                segment_start = start if index == 0 else remaining[index - 1]
                completed = super().move_to_position(
                    segment_start,
                    target,
                    line_tolerance=line_tolerance,
                    target_tolerance=node_tolerance,
                )
                if not completed:
                    remaining = remaining[index:]
                    if not self.handle_death():
                        return remaining
                    break
                if index < len(remaining) - 1:
                    self._release_move_keys()
                    self.sleep(1)
            else:
                return None
        return None

    def handle_death(self):
        if self.is_dead:
            self._release_move_keys()
        while self.is_dead:
            self.next_frame()
            if (revive_box := self.find_one("dungeon_revive")) and self.is_colorful(revive_box):
                self.click(revive_box)
            self.sleep(1)
        return True

    def wait_out_of_combat(self, time_out=300):
        self._require_packet_capture()
        inactive_since = None

        def is_out_of_combat():
            nonlocal inactive_since
            self._require_packet_capture()
            in_combat = self.in_combat
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

    def investigate(self, pos=None):
        self.info['state'] = '准备交互开本仪器'
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
        self.info['state'] = f'前往开本仪器: {pos}'
        self.move_to_position(self.position, pos, target_tolerance=1.5)
        self.info['state'] = f'交互开本仪器'
        self.sleep(2)
        self.send_key('f')
        self.info['state'] = f'点击开本'
        self.sleep(1)
        self.click(0.632,0.857)
        self.info['state'] = f'等待开本读秒'
        self.sleep(8)

    def enter(self, difficulty):
        # 交互副本入口
        self.info['state'] = '等待副本入口按钮'
        if box:=self.wait_feature('dungeon_entrance'):
            self.info['state'] = '点击交互副本入口'
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
        self.info['state'] = '等待选择难度'
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
                self.info['state'] = '选择大师难度'
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
        self.info['state'] = '选择单双人模式'
        self.click(0.812,0.859)
        self.sleep(1)
        # 点击进入副本
        self.info['state'] = '点击进入副本'
        self.click(0.933,0.920)
        self.sleep(1)
        # 等待副本UI
        if not self.wait_feature('loading'):
            self.log_error('没有找到加载页面')
            return False
        self.info['state'] = '等待进本加载'
        while self.frame is None or self.find_one('loading'):
            self.sleep(1)
            self.next_frame()
        self.info['state'] = '加载完成'
        if not  self.wait_feature('dungeon_scene_icon'):
            self.log_error('加载完成后没有找到副本UI')
            return False
        self.info['entry_count'] += 1
        self.info['state'] = '已进入副本'
        return True

    def handle_end(self):
        self.info['state'] = 'Boss战结束，等待结算'
        if not self.wait_click_feature('next', box=self.box_of_screen(0.46, 0.86, 0.53, 0.92), time_out=30):
            self.log_error('Boss战结束后没等到结算')
            return False
        self.info['win_count'] += 1
        # 点击离开
        self.wait_click_feature('exit', box=self.box_of_screen(0.88, 0.91, 0.94, 0.97))
        self.wait_feature('loading')
        self.info['state'] = '等待出本加载'
        while self.find_one('loading'):
            self.sleep(1)
        self.info['state'] = '本次副本成功'

    def clear(self):
        self.info['state'] = '副本流程出现错误，尝试退回状态'

class Difficulty(Enum):
    NORMAL = 1
    HARD = 2
    MASTER1 = 3
    MASTER6 = 4
