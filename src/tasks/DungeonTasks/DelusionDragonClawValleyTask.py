import time

from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class DelusionDragonClawValleyTask(DungeonTaskBase):

    INSTRUMENT_POSITION = (34.800, 36.100)
    BOSS_ATTR_ID = 1399

    def __init__(self, *args, **kwargs):
        self.task_name = 'Delusion - Dragon Claw Valley'
        self.task_name_zh = '弥妄·巨龙爪痕'
        self.task_desc = 'Not recommended for DPS or Lifebind.'
        self.task_desc_zh = '不建议使用输出或愈合执行此任务。'
        super().__init__(*args, **kwargs)
        self.default_config.update({'Difficulty': 'Hard'})
        self.config_type['Difficulty'] = {
            'type': 'drop_down',
            'options': ['Hard', 'Master 1'],
        }

    def run(self):
        super().run()
        while True:
            self.difficulty = {
                'Hard': Difficulty.HARD,
                'Master 1': Difficulty.MASTER1,
                '困难': Difficulty.HARD,
                '大师1': Difficulty.MASTER1,
            }.get(self.config.get('Difficulty', 'Hard'), Difficulty.HARD)
            if self.exec():
                if self.record_successful_clear():
                    break
            else:
                self.return_to_initial_state()

    def exec(self):
        if not self.begin():
            return False
        self.investigate(self.INSTRUMENT_POSITION)
        if not self._follow_route((
                    (23.177, 32.644),
                    (26.375, 83.674),
                    (107.424, 91.754),
                ), '第一段道中', camera_offset=180):
            return False
        self._start_auto_battle()
        if not self._wait_for_combat_end('第一段道中'):
            return False

        if not self._follow_route((
                    (107.424, 91.754),
                    (108.310, 137.405),
                    (92.884, 134.451),
                    (83.987, 149.444),
                    (128.464, 158.061),
                    (147.734, 176.133),
                    (170.479, 168.627),
                    (181.499, 163.740),
                    (172.265, 151.090),
                    (149.702, 126.962),
                    (151.631, 129.405)
                ), '第二段道中'):
            return False
        self._start_auto_battle()
        if not self._wait_for_combat_end('第二段道中'):
            return False

        if not self._follow_route(
                    ((151.631, 129.405), (159.678, 154.856),), '前往第一处交互点'):
            return False
        self.info['State'] = '交互并等待机关完成'
        self.sleep(1)
        self.send_key('space', after_sleep=0.5)
        self.send_key('f')
        self.sleep(13)

        if not self._follow_route(((294.137, 232.450),), '第三段道中'):
            return False
        self._start_auto_battle()
        if not self._wait_for_last_route_combat_end('第三段道中'):
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
        self.sleep(6)
        boss_position = self._wait_for_entity_position(
            self.BOSS_ATTR_ID,
            time_out=15,
        )
        if boss_position is None:
            self.log_error(f'没有检测到Boss: {self.BOSS_ATTR_ID}')
            return False

        self.info['State'] = 'Boss战中'
        self.send_key(self.get_custom_key('Phantom Dash'))
        # if not self.move_to_position(
        #         self.position,
        #         boss_position,
        #         target_tolerance=2,
        #         enable_sprint=True):
        #     self.log_error('无法前往Boss位置')
        #     return False
        self.sleep(3)
        self._start_auto_battle()
        if not self._wait_for_combat_end(
                'Boss战', time_out=420, check_special_reward=False):
            return False

        return self.handle_end()

    def _follow_route(self, route, state, camera_offset=0):
        self.info['State'] = state
        remaining = self.move_to_positions(
            route,
            node_tolerance=1,
            max_path_deviation=8,
            enable_sprint=True,
            camera_offset=camera_offset
        )
        if remaining is not None:
            self.log_error(f'{state}移动失败，剩余路径: {remaining}')
            return False
        return True

    def _wait_for_combat_end(
            self, state, time_out=180, check_special_reward=True):
        self.info['State'] = f'{state}战斗中'
        if self.wait_out_of_combat(time_out=time_out):
            self._stop_auto_battle()
            if check_special_reward:
                self.pickup_special_reward(1207)
            return True
        self._stop_auto_battle()
        self.log_error(f'{state}战斗超时')
        return False

    def _wait_for_last_route_combat_end(
            self, state, time_out=180, check_special_reward=True):
        self.info['State'] = f'{state}战斗中'
        deadline = time.monotonic() + time_out
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if self.wait_out_of_combat(time_out=min(10, remaining)):
                self._stop_auto_battle()
                if check_special_reward:
                    self.pickup_special_reward(1207)
                return True

            teammates = (
                entity
                for entity_uuid, entity in self.nearby_entities.items()
                if (entity_uuid != self.player_uuid
                    and entity.get('is_teammate'))
            )
            if not any(entity.get('in_combat') for entity in teammates):
                self._stop_auto_battle()
                if check_special_reward:
                    self.pickup_special_reward(1207)
                self.click(0.882, 0.875, after_sleep=5)
                return True

        self._stop_auto_battle()
        self.log_error(f'{state}战斗超时')
        return False

    def _start_auto_battle(self):
        self.send_key(self.get_custom_key('Auto Battle'))

    def _stop_auto_battle(self):
        self.send_key(self.get_custom_key('Auto Battle'))

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
