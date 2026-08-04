from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon1931Task(DungeonTaskBase):

    INSTRUMENT_POSITION = (9.920, 50.740)
    FIRST_WAVE_MONSTER_UUIDS = frozenset({
        8650816,
        1900608,
        1966144,
        8912960,
        4653120,
        4718656,
        9175104,
        8847424,
        8781888,
        8716352,
    })
    SECOND_WAVE_MONSTER_UUIDS = frozenset({
        8978496,
        9044032,
        11141184,
        9306176,
        9240640,
    })

    def __init__(self, *args, **kwargs):
        self.task_name = 'Divine Threshold of the Distant Sky - Hard'
        self.task_name_zh = '远天的神槛 - 困难'
        self.task_desc = (
            'Automatically clears Divine Threshold of the Distant Sky - Hard.'
        )
        self.task_desc_zh = '自动通关远天的神槛 - 困难。'
        self.difficulty = Difficulty.HARD
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

        first_route = [
            (25.015, 47.788),
            (42.934, 28.295),
            (53.763, 4.169),
            (48.321, -18.409),
            (31.769, -41.090),
        ]

        if not self._follow_route(first_route, '前往第一处战斗区域', camera_offset=135):
            return False
        if not self._wait_for_combat_end(
                '第一处战斗'):
            return False
        if not self._retry_route_for_remaining_monsters(
                first_route,
                self.FIRST_WAVE_MONSTER_UUIDS,
                '第一处战斗'):
            return False

        second_route = (
                (31.769, -41.090),
                (4.714, -50.665),
                (-37.944, -37.833),
        )
        if not self._follow_route(
                second_route, '前往第二处战斗区域', camera_offset=135):
            return False
        if not self._wait_for_combat_end(
                '第二处战斗'):
            return False
        if not self._retry_route_for_remaining_monsters(
                second_route,
                self.SECOND_WAVE_MONSTER_UUIDS,
                '第二处战斗'):
            return False

        if not self._follow_route((
                (-37.944, -37.833),
                (-17.600, -17.600),
        ), '前往第一处机关'):
            return False
        self._interact('激活第一处机关')

        if not self._follow_route(
                ((0.000, 0.000),), '前往第三处战斗区域'):
            return False
        if not self._wait_for_combat_end('第三处战斗'):
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

    def _retry_route_for_remaining_monsters(
            self, route, monster_uuids, state):
        nearby_entities = self.nearby_entities
        remaining_uuids = {
            entity_uuid
            for entity_uuid in monster_uuids.intersection(nearby_entities)
            if not nearby_entities[entity_uuid].get('is_dead', False)
        }
        if not remaining_uuids:
            return True

        self.log_info(
            f'{state}发现漏怪: {sorted(remaining_uuids)}，倒退路线重新清理')
        auto_combat_key = self.get_custom_key('Auto Battle')
        self.send_key(auto_combat_key)
        if not self._follow_route(
                reversed(route),
                f'{state}漏怪，倒退返回起点',
                camera_offset=-45):
            self.send_key(auto_combat_key)
            return False
        self.info['State'] = f'{state}漏怪，等待返回起点后脱战'
        if not self.wait_out_of_combat(time_out=180):
            self.send_key(auto_combat_key)
            self.log_error(f'{state}返回起点后战斗超时')
            return False
        if not self._follow_route(
                route,
                f'{state}漏怪，重新前往终点',
                camera_offset=135):
            self.send_key(auto_combat_key)
            return False

        self.info['State'] = f'{state}漏怪清理中'
        combat_finished = self.wait_out_of_combat(time_out=180)
        self.send_key(auto_combat_key)
        if not combat_finished:
            self.log_error(f'{state}漏怪清理超时')
            return False
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
