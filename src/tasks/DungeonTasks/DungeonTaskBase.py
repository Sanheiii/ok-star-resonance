from enum import Enum
import time

from ok import og
from qfluentwidgets import FluentIcon

from src.tasks.SRTask import SRTask

class DungeonTaskBase(SRTask):

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
        self.default_config.update({
            'Purchase Items': False,
            'Purchase Every N Clears': 8,
            'Purchase Item Index': 1,
        })

    def run(self):
        self._require_packet_capture()
        self.info['Entry Count'] = 0
        self.info['Pass Count'] = 0
        self.info['Pass Rate'] = '0.00%'
        self._last_redeem_pass_count = None

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
        if not self.config.get('Purchase Items'):
            return True

        pass_count = self.info['Pass Count']
        purchase_interval = self.config.get('Purchase Every N Clears', 1)
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

        item_index = self.config.get('Purchase Item Index', 1)
        if not 1 <= item_index <= len(item_positions):
            self.log_error(f'Purchase item index out of range: {item_index}')
            self._last_redeem_pass_count = pass_count
            return True
        item_position = item_positions[item_index - 1]

        self.send_key('o', after_sleep=2)
        self.click(0.035, 0.454, after_sleep=1)
        self.click(item_position[0], item_position[1], after_sleep=1)
        self.click(0.812, 0.676, after_sleep=1)
        self.click(0.633, 0.856, after_sleep=1)
        self.send_key('o', after_sleep=0)

        self._last_redeem_pass_count = pass_count
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

    def enter(self, difficulty):
        # 交互副本入口
        self.info['State'] = '等待副本入口按钮'
        if box:=self.wait_feature('dungeon_entrance'):
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
        if not  self.wait_feature('dungeon_scene_icon'):
            self.log_error('加载完成后没有找到副本UI')
            return False
        self.info['Entry Count'] += 1
        self.info['State'] = '已进入副本'
        return True

    def handle_end(self):
        self.info['State'] = 'Boss战结束，等待结算'
        if not self.wait_click_feature('next', box=self.box_of_screen(0.46, 0.86, 0.53, 0.92), time_out=30):
            self.log_error('Boss战结束后没等到结算')
            return False
        self.info['Pass Count'] += 1
        # 点击离开
        self.wait_click_feature('exit', box=self.box_of_screen(0.88, 0.91, 0.94, 0.97))
        self.wait_feature('loading')
        self.info['State'] = '等待出本加载'
        while self.find_one('loading'):
            self.sleep(1)
            self.next_frame()
        self.info['State'] = '本次副本成功'
        return True

    def return_to_initial_state(self):
        self.info['State'] = '副本流程出现错误，尝试退回状态'
        sleep_flag = False
        while not self.find_one('menu_icon'):
            self.next_frame()
            if self.find_one('loading'):
                continue

            confirm_flag = False
            sleep_flag = True
            if box:=self.find_one(['escape', 'leave_dungeon', 'dungeon_timeout']):
                self.click(box)
                confirm_flag = True
            box = self.get_box_by_name('close')
            if self.calculate_color_percentage({'r': (250, 255), 'g': (250, 255), 'b': (250, 255)}, box) > 0.15:
                self.click(box)
                confirm_flag = True
            if self.find_one('dungeon_scene_icon'):
                self.send_key('p')
                confirm_flag = True
            lang = self.get_game_language()

            confirm = {
                'en': 'confirm_en',
                'jp': 'confirm_jp',
                'zht': 'confirm_zht',
            }.get(lang, 'confirm')

            if confirm_flag:
                if box:=self.wait_feature(confirm, time_out=3):
                    self.click(box)
            elif self.find_one(confirm):
                self.click(self.get_box_by_name('cancel'))
        if sleep_flag:
            self.sleep(1)

    def _update_pass_rate(self):
        completed_entries = self.info['Entry Count'] - 1
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
