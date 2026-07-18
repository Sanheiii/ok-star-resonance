from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon1234Task(DungeonTaskBase):

    INSTRUMENT_POSITION = (34.800, 36.100)
    BOSS_ATTR_ID = 1399

    def __init__(self, *args, **kwargs):
        self.task_name = 'Delusion - Dragon Claw Valley - Hard'
        self.task_name_zh = '弥妄·巨龙爪痕 - 困难'
        self.task_desc = 'Not recommended for DPS or Lifebind.'
        self.task_desc_zh = '不建议使用输出或愈合执行此任务。'
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

        combat_routes = (
            (
                '第一段道中',
                (
                    (23.543, 37.156),
                    (26.375, 83.674),
                    (107.424, 91.754),
                ),
            ),
            (
                '第二段道中',
                (
                    (107.424, 91.754),
                    (108.310, 137.405),
                    (92.884, 134.451),
                    (83.987, 149.444),
                    (128.464, 158.061),
                    (151.631, 129.405)
                )
            ),
        )
        for state, route in combat_routes:
            if not self._follow_route(route, state):
                return False
            if not self._wait_for_combat_end(state):
                return False
        self.send_key('h')
        if not self._follow_route(
                    ((151.631, 129.405), (159.678, 154.856),), '前往第一处交互点'):
            return False
        self.info['State'] = '交互并等待机关完成'
        self.sleep(1)
        self.send_key('space', after_sleep=0.5)
        self.send_key('f')
        self.sleep(13)
        self.send_key('h')

        if not self._follow_route(((294.137, 232.450),), '第三段道中'):
            return False
        if not self._wait_for_combat_end('第三段道中'):
            return False

        if not self._follow_route((
                (294.137, 232.450),
                (320.840, 248.300),
                (350.688, 239.436),
                (381.305, 243.641),
                (401.854, 222.871),
                (418.544, 231.008),
                (415.400, 297.313),
                (439.273, 309.574),
                (461.532, 314.801),
        ), '前往第二处交互点'):
            return False
        self.info['State'] = '交互开启后续路线'
        self.sleep(1)
        self.send_key('f', after_sleep=1)

        if not self._follow_route((
                (493.592, 332.410),
                (465.287, 373.782),
                (430.305, 381.840),
                (421.043, 392.396),
        ), '前往Boss区域'):
            return False

        self.info['State'] = '进入Boss区域'
        self.look_at(0)
        self.sleep(1)
        self.look_at(0)
        self.send_key('w', down_time=3, after_sleep=0.2)
        self.send_key('esc')
        self.sleep(5)
        boss_position = self._wait_for_entity_position(
            self.BOSS_ATTR_ID,
            time_out=15,
        )
        if boss_position is None:
            self.log_error(f'没有检测到Boss: {self.BOSS_ATTR_ID}')
            return False

        self.info['State'] = 'Boss战中'
        if not self.move_to_position(
                self.position,
                boss_position,
                target_tolerance=2,
                enable_sprint=True):
            self.log_error('无法前往Boss位置')
            return False
        self.sleep(3)
        if not self.wait_out_of_combat(time_out=420):
            self.log_error('Boss战超时')
            return False

        return self.handle_end()

    def _follow_route(self, route, state):
        self.info['State'] = state
        self._move_mouse_relative(0, 1800)
        remaining = self.move_to_positions(
            route,
            node_tolerance=2,
            max_path_deviation=8,
            enable_sprint=True,
        )
        if remaining is not None:
            self.log_error(f'{state}移动失败，剩余路径: {remaining}')
            return False
        return True

    def _wait_for_combat_end(self, state, time_out=180):
        self.info['State'] = f'{state}战斗中'
        if self.wait_out_of_combat(time_out=time_out):
            return True
        self.log_error(f'{state}战斗超时')
        return False

    def _wait_for_entity_position(self, attr_id, time_out):
        result = {'position': None}

        def find_entity():
            result['position'] = next((
                entity.get('position')
                for entity in self.nearby_entities.values()
                if (entity.get('attr_id') == attr_id
                    and entity.get('position') is not None)
            ), None)
            return result['position'] is not None

        if not self.wait_until(find_entity, time_out=time_out):
            return None
        return result['position']
