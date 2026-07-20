from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon6613Task(DungeonTaskBase):

    INSTRUMENT_POSITION = (-52.860, -11.590)

    def __init__(self, *args, **kwargs):
        self.task_name = 'Desolate Garden - Hard'
        self.task_name_zh = '荒芜之庭 - 困难'
        self.task_desc = 'DPS classes may take longer during the Boss fight.'
        self.task_desc_zh = '输出职业在Boss战可能消耗更多时间。'
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False
        super().__init__(*args, **kwargs)

    def run(self):
        super().run()
        while True:
            if not self.exec():
                self.return_to_initial_state()

    def exec(self):
        if not self.begin():
            return False
        self.investigate(self.INSTRUMENT_POSITION)
        self.send_key('h')

        if not self._follow_route((
                (-28.258, -12.534),
                (-8.380, 17.429),
                (28.550, 18.090),
        ), '前往第一朵花'):
            return False
        if not self._wait_for_combat_end('第一朵花'):
            return False

        if not self._follow_route((
                (130.514, 17.068),
                (148.106, 36.960),
                (143.460, 57.670),
        ), '前往第二朵花'):
            return False
        if not self._wait_for_combat_end('第二朵花'):
            return False

        if not self._follow_route(
                ((143.460, 57.670),), '前往水晶区域传送门'):
            return False
        self.info['State'] = '进入水晶区域'
        self.send_key('f')
        self.send_key('w', down_time=0.5, after_sleep=0.5)
        self.send_key('f')
        self.sleep(5)

        if not self._activate_crystal(
                (85.820, 56.920),
                (-66.800, -134.770),
                '第一个水晶'):
            return False

        if not self._activate_crystal(
                (85.820, 72.450),
                (25.440, -0.240),
                '第三个水晶'):
            return False

        if not self._follow_route(
                ((81.490, 64.870),), '前往最终传送门'):
            return False
        self.sleep(1)
        self.send_key('f')
        self.send_key('w', down_time=0.5, after_sleep=0.5)
        self.send_key('f', after_sleep=3)

        if not self._follow_route((
                (-84.072, 39.021),
                (-58.440, 39.017),
        ), '前往Boss区域'):
            return False

        self.info['State'] = '进入Boss区域'
        self.send_key('w', down_time=3,after_sleep=3)

        for i in range(3):
            self.send_key('esc',after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break
        self.send_key('e')

        self.info['State'] = 'Boss战斗中'
        if not self.wait_out_of_combat(time_out=420):
            self.log_error('Boss战斗超时')
            return False

        return self.handle_end()

    def _activate_crystal(self, crystal_position, exit_position, name):
        if not self._follow_route((crystal_position,), f'前往{name}'):
            return False

        self.info['State'] = f'激活{name}'
        self.send_key('f', after_sleep=1)
        self.send_key('w', down_time=0.5, after_sleep=1)
        self.send_key('f', after_sleep=1)
        self.sleep(3)
        self.send_key('f')
        self.send_key('w', down_time=2)
        self.sleep(10)
        if not self._wait_for_combat_end(name):
            return False

        if not self._follow_route((exit_position,), f'离开{name}区域'):
            return False
        self.send_key('f', after_sleep=1)
        self.send_key('w', down_time=0.5, after_sleep=1)
        self.send_key('f',after_sleep=2)
        return True

    def _follow_route(self, route, state):
        self.info['State'] = state
        # self._move_mouse_relative(0, 1800)
        remaining = self.move_to_positions(
            route,
            node_tolerance=1,
            max_path_deviation=8,
            enable_sprint=True,
        )
        if remaining is not None:
            self.log_error(f'{state}移动失败，剩余路径: {remaining}')
            return False
        self.sleep(0.5)
        return True

    def _wait_for_combat_end(self, state, time_out=180):
        self.info['State'] = f'{state}战斗中'
        if self.wait_out_of_combat(time_out=time_out):
            return True
        self.log_error(f'{state}战斗超时')
        return False
