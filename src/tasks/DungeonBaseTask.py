from enum import Enum

from src.tasks.SRTask import SRTask


class DungeonBaseTask(SRTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        self._require_packet_capture()
        if not self.enter(self.difficulty):
            self.log_error('进入副本失败')
            return False
        return True

    def investigate(self, pos):
        self.sleep(1)
        self.send_key('s', down_time=0.2)
        self.send_key('w', down_time=1)
        self.sleep(3)
        self.move_to_position(self.position,pos)
        self.send_key('f')
        self.sleep(1)
        self.click(0.632,0.857)
        self.sleep(10)
        pass

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
                self.click(0.092,0.154)
            elif difficulty is Difficulty.HARD:
                self.click(0.092,0.245)
            elif difficulty in (Difficulty.MASTER1, Difficulty.MASTER6):
                self.click(0.092,0.344)
                self.sleep(1)
                self.swipe(self.width_of_screen(0.370),self.height_of_screen(0.922),self.width_of_screen(0.999),self.height_of_screen(0.922))
                self.sleep(2)
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
            return True
        return self.wait_feature('dungeon_scene_icon', time_out=60) is not None


class Difficulty(Enum):
    NORMAL = 1
    HARD = 2
    MASTER1 = 3
    MASTER6 = 4