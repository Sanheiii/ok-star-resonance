from enum import Enum

from src.tasks.SRTask import SRTask

class DungeonTaskBase(SRTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_normal_difficulty = False

    def run(self):
        self._require_packet_capture()
        self.info['entry_count'] = 0
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
            if not self._handle_death():
                return False
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
                    if not self._handle_death():
                        return remaining
                    break
                if index < len(remaining) - 1:
                    self._release_move_keys()
                    self.sleep(1)
            else:
                return None
        return None

    def _handle_death(self):
        """Use the dungeon revive UI and wait until normal gameplay resumes."""
        self._release_move_keys()
        self.next_frame()
        if not self.wait_feature("leave_dungeon", time_out=5):
            return not self.is_dead

        while self.find_one("leave_dungeon"):
            if (revive_box := self.find_one("dungeon_revive")) and self.is_colorful(revive_box):
                self.click(revive_box)
            self.sleep(1)
            self.next_frame()
        self.sleep(3)
        return not self.is_dead

    def investigate(self, pos=None):
        self.sleep(2)
        if pos is None:
            pos = next((
                entity.get('position')
                for entity in self.nearby_entities.values()
                if entity.get('attr_id') == 10001 and entity.get('position') is not None
            ), None)
            if pos is None:
                self.log_error('没有找到调查目标')
                return False
        self.move_to_position(self.position, pos, target_tolerance=1.5)
        self.sleep(2)
        self.send_key('f')
        self.sleep(1)
        self.click(0.632,0.857)
        self.sleep(10)

    def enter(self, difficulty):
        # 交互副本入口
        if box:=self.wait_feature('dungeon_entrance'):
            self.send_key_down('lalt')
            self.sleep(0.1)
            self.click(box)
            self.sleep(0.1)
            self.send_key_up('lalt')
            self.sleep(1)
            self.log_info('点击交互副本入口')
        else:
            self.log_error('没有找到副本入口')
            return False
        # 选择难度
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
        self.click(0.812,0.859)
        self.sleep(1)
        # 点击进入副本
        self.click(0.933,0.920)
        self.sleep(1)
        # 等待副本UI
        if not self.wait_feature('loading'):
            self.log_error('没有找到加载页面')
            return False
        while self.frame is None or self.find_one('loading'):
            self.sleep(1)
            self.next_frame()
        if not  self.wait_feature('dungeon_scene_icon'):
            self.log_error('加载完成后没有找到副本UI')
            return False
        self.info['entry_count'] += 1
        return True


class Difficulty(Enum):
    NORMAL = 1
    HARD = 2
    MASTER1 = 3
    MASTER6 = 4
