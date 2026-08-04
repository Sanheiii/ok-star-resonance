from ok import og

from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon1931Task(DungeonTaskBase):

    INSTRUMENT_POSITION = (9.920, 50.740)
    TWO_OUTDOOR_WAVES_CONFIG = 'Fight Only Two Outdoor Waves'

    def __init__(self, *args, **kwargs):
        self.task_name = 'Divine Threshold of the Distant Sky - Hard'
        self.task_name_zh = '远天的神槛 - 困难'
        self.task_desc = (
            'Automatically clears Divine Threshold of the Distant Sky - Hard.'
        )
        self.task_desc_zh = '自动通关远天的神槛 - 困难。'
        self.difficulty = Difficulty.HARD
        super().__init__(*args, **kwargs)
        if og.app.po_translation and (
                catalog := getattr(og.app.po_translation, '_catalog', None)):
            catalog[self.TWO_OUTDOOR_WAVES_CONFIG] = '道中外场仅打两波'
        self.default_config.update({
            self.TWO_OUTDOOR_WAVES_CONFIG: False,
        })

    def run(self):
        super().run()
        while True:
            if not self.exec():
                self.return_to_initial_state()

    def exec(self):
        if not self.begin():
            return False

        self.investigate(self.INSTRUMENT_POSITION)

        two_outdoor_waves = self.config.get(
            self.TWO_OUTDOOR_WAVES_CONFIG, False)
        first_route = [
            (25.015, 47.788),
            (42.934, 28.295),
            (53.763, 4.169),
        ]
        if two_outdoor_waves:
            first_route.extend((
                (48.321, -18.409),
                (31.769, -41.090),
            ))

        if not self._follow_route(first_route, '前往第一处战斗区域', camera_offset=135):
            return False
        if not self._wait_for_combat_end(
                '第一处战斗'):
            return False

        if not two_outdoor_waves:
            if not self._follow_route((
                    (53.763, 4.169),
                    (48.321, -18.409),
                    (31.769, -41.090),
            ), '前往第二处战斗区域', camera_offset=135):
                return False
            if not self._wait_for_combat_end(
                    '第二处战斗'):
                return False

        outdoor_wave_name = '第二' if two_outdoor_waves else '第三'

        if not self._follow_route((
                (31.769, -41.090),
                (4.714, -50.665),
                (-37.944, -37.833),
        ), f'前往{outdoor_wave_name}处战斗区域', camera_offset=135):
            return False
        if not self._wait_for_combat_end(
                f'{outdoor_wave_name}处战斗'):
            return False

        if not self._follow_route((
                (-37.944, -37.833),
                (-17.600, -17.600),
        ), '前往第一处机关'):
            return False
        self._interact('激活第一处机关')

        indoor_wave_name = '第三' if two_outdoor_waves else '第四'
        if not self._follow_route(
                ((0.000, 0.000),), f'前往{indoor_wave_name}处战斗区域'):
            return False
        if not self._wait_for_combat_end(f'{indoor_wave_name}处战斗'):
            return False

        if not self._follow_route(((0.000, 0.000),), '前往Boss机关'):
            return False

        self._interact('激活Boss机关')

        self._skip_boss_animation('跳过Boss出场动画')
        if not self._follow_route(((0.000, 0.000),), '前往Boss'):
            return False
        self.click(0.5, 0.5)
        if not self._wait_for_combat_end('Boss战斗', time_out=420):
            return False

        self._skip_boss_animation('跳过Boss结算动画')
        return self.handle_end()

    def _follow_route(self, route, state, camera_offset=0):
        self.info['State'] = state
        remaining = self.move_to_positions(
            route,
            line_tolerance=1,
            node_tolerance=1,
            max_path_deviation=8,
            enable_sprint=True,
            camera_offset=camera_offset
        )
        if remaining is not None:
            self.log_error(f'{state}移动失败，剩余路径: {remaining}')
            return False
        return True

    def _wait_for_combat_end(self, state, time_out=180):
        auto_combat_key = self.get_custom_key('Auto Battle')
        self.send_key(auto_combat_key)
        self.info['State'] = f'等待进入{state}'
        if not self.wait_in_combat():
            self.log_error(f'{state}没有进入战斗')
            return False
        self.info['State'] = f'{state}中'
        if not self.wait_out_of_combat(time_out=time_out):
            self.log_error(f'{state}超时')
            return False
        self.send_key(auto_combat_key)
        self.pickup_special_reward(1207)
        return True

    def _interact(self, state):
        self.info['State'] = state
        self.sleep(1)
        self.send_key('f', after_sleep=1)
        self.send_key('w', down_time=0.5, after_sleep=1)
        self.send_key('f',after_sleep=5)

    def _skip_boss_animation(self, state):
        self.info['State'] = state
        for _ in range(3):
            self.send_key('esc', after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break
