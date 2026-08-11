import math
import time

from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class DesolateGardenTask(DungeonTaskBase):

    INSTRUMENT_POSITION = (-52.860, -11.590)
    BOSS_ATTR_ID = 4711
    BOSS_TIMEOUT = 420
    BOSS_END_CHECK_DELAY = 5
    SPECIAL_TRIGGER_ATTR_ID = 884640
    SPECIAL_TARGET_ATTR_ID = 884642

    def __init__(self, *args, **kwargs):
        self.task_name = 'Desolate Garden'
        self.task_name_zh = '荒芜之庭'
        self.task_desc = 'DPS classes may take longer during the Boss fight.'
        self.task_desc_zh = '输出职业在Boss战可能消耗更多时间。'
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
                (-28.258, -12.534),
                (-21.654, -3.858),
                (-7.471, 14.240),
                (28.550, 18.090),
        ), '前往第一朵花'):
            return False
        self._start_auto_battle()
        if not self.wait_in_combat():
            self._stop_auto_battle()
            self.log_error('第一朵花没有进入战斗')
            return False
        if not self._wait_for_combat_end('第一朵花'):
            return False

        if not self._follow_route((
                (54.937, 17.827),
                (130.514, 17.068),
                (148.106, 36.960),
                (143.460, 57.670),
        ), '前往第二朵花'):
            return False
        self._start_auto_battle()
        if not self.wait_in_combat():
            self._stop_auto_battle()
            self.log_error('第二朵花没有进入战斗')
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
                (82.640, 65.050),
                (32.890, 121.960),
                '第二个水晶'):
            return False

        if (self.difficulty is Difficulty.MASTER1
                and not self._activate_crystal(
                    (85.820, 72.450),
                    (25.440, -0.240),
                    '第三个水晶')):
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
        self.send_key('w', down_time=3, after_sleep=3)

        for _ in range(3):
            self.send_key('esc', after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break
        self.info['State'] = 'Boss战斗中'

        self._boss_auto_battle_enabled = False
        while True:
            if not self._trigger_boss_combat():
                return False
            if not self._wait_for_boss_combat_end(
                    time_out=self.BOSS_TIMEOUT):
                return False
            self.sleep(self.BOSS_END_CHECK_DELAY)
            if not self._boss_exists(self.nearby_entities):
                return self.handle_end()

            self.info['State'] = 'Boss战斗团灭，重新开怪'
            self._boss_auto_battle_enabled = False

    def _wait_for_boss_combat_end(self, time_out):
        self.info['State'] = 'Boss战斗中'
        deadline = time.monotonic() + time_out
        special_handled = False
        while True:
            if time.monotonic() >= deadline:
                self._set_boss_auto_battle(False)
                self.log_error('Boss战斗超时')
                return False

            in_combat = self.in_combat or self._is_any_teammate_in_combat()
            if not in_combat:
                return True

            entities = self.nearby_entities
            if (not special_handled
                    and self._entities_with_attr(
                        entities,
                        self.SPECIAL_TRIGGER_ATTR_ID,
                    )):
                special_handled = True
                self._handle_boss_special()
                self.info['State'] = 'Boss战斗中'

            self.next_frame()
            self.sleep(0.2)

    def _trigger_boss_combat(self):
        self.send_key(self.get_custom_key('Phantom Dash'), after_sleep=1)
        self.click(0.5, 0.5,after_sleep=0.5)
        self._set_boss_auto_battle(True)
        if self.wait_in_combat():
            return True
        self._set_boss_auto_battle(False)
        self.log_error('Boss没有进入战斗')
        return False

    def _set_boss_auto_battle(self, enabled):
        current = getattr(self, '_boss_auto_battle_enabled', False)
        if current == enabled:
            return
        self.send_key(self.get_custom_key('Auto Battle'))
        self._boss_auto_battle_enabled = enabled

    @classmethod
    def _boss_exists(cls, entities):
        return any(
            entity.get('attr_id') == cls.BOSS_ATTR_ID
            for entity in entities.values()
        )

    def _handle_boss_special(self):
        self._set_boss_auto_battle(False)
        try:
            self._run_boss_special()
        finally:
            if self.in_combat or self._is_any_teammate_in_combat():
                self._set_boss_auto_battle(True)

    def _run_boss_special(self):
        visited_trigger_uuids = set()
        visited_target_uuids = set()
        while True:
            if not self._has_special_targets():
                return

            triggers = self._entities_with_attr(
                self.nearby_entities,
                self.SPECIAL_TRIGGER_ATTR_ID,
            )
            unvisited_triggers = {
                entity_uuid: entity
                for entity_uuid, entity in triggers.items()
                if entity_uuid not in visited_trigger_uuids
            }
            if unvisited_triggers:
                trigger_uuid, trigger = self._nearest_entity_to(
                    self.position,
                    unvisited_triggers,
                )
                self.info['State'] = (
                    f'Boss特殊机制：前往触发点 {trigger_uuid}'
                )
                while not self.move_to_position(
                        self.position,
                        trigger['position'],
                        target_tolerance=1,
                        line_tolerance=1,
                        enable_sprint=False):
                    if not self._has_special_targets():
                        return
                    self.send_key('w', down_time=1)
                    current_trigger = self.nearby_entities.get(trigger_uuid)
                    if (current_trigger is None
                            or current_trigger.get('attr_id')
                            != self.SPECIAL_TRIGGER_ATTR_ID):
                        break
                    trigger = current_trigger
                    self.next_frame()
                visited_trigger_uuids.add(trigger_uuid)

            targets = self._entities_with_attr(
                self.nearby_entities,
                self.SPECIAL_TARGET_ATTR_ID,
            )
            unvisited_targets = {
                entity_uuid: entity
                for entity_uuid, entity in targets.items()
                if entity_uuid not in visited_target_uuids
            }
            if not unvisited_targets:
                return

            target_uuid, target = self._nearest_entity_to(
                self.position,
                unvisited_targets,
            )
            self.info['State'] = f'Boss特殊机制：前往目标 {target_uuid}'
            arrived = False
            while True:
                movement_target = self._position_beyond(
                    self.position,
                    target['position'],
                    5,
                )
                if self.move_to_position(
                        self.position,
                        movement_target,
                        target_tolerance=1,
                        line_tolerance=1,
                        enable_sprint=True):
                    arrived = True
                    break
                if not self._has_special_targets():
                    return
                current_target = self.nearby_entities.get(target_uuid)
                if (current_target is None
                        or current_target.get('attr_id')
                        != self.SPECIAL_TARGET_ATTR_ID):
                    break
                target = current_target
                self.next_frame()
            visited_target_uuids.add(target_uuid)
            if arrived:
                self.info['State'] = f'Boss特殊机制：目标 {target_uuid} 等待3秒'
                self.sleep(2)

    def _has_special_targets(self):
        return bool(self._entities_with_attr(
            self.nearby_entities,
            self.SPECIAL_TARGET_ATTR_ID,
        ))

    @staticmethod
    def _entities_with_attr(entities, attr_id):
        return {
            entity_uuid: entity
            for entity_uuid, entity in entities.items()
            if (entity.get('attr_id') == attr_id
                and entity.get('position') is not None)
        }

    @classmethod
    def _nearest_entity_to(cls, current_position, entities):
        current_x, current_z = cls._xz(current_position)
        return min(entities.items(), key=lambda item: math.hypot(
            cls._xz(item[1]['position'])[0] - current_x,
            cls._xz(item[1]['position'])[1] - current_z,
        ))

    @classmethod
    def _position_beyond(cls, start_position, target_position, distance):
        start_x, start_z = cls._xz(start_position)
        target_x, target_z = cls._xz(target_position)
        delta_x = target_x - start_x
        delta_z = target_z - start_z
        length = math.hypot(delta_x, delta_z)
        if length == 0:
            return target_x, target_z
        scale = distance / length
        return (
            target_x + delta_x * scale,
            target_z + delta_z * scale,
        )

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

        self._start_auto_battle()
        if not self.wait_in_combat():
            self._stop_auto_battle()
            self.log_error(f'{name}没有进入战斗')
            return False
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
            line_tolerance=1,
            node_tolerance=1,
            max_path_deviation=8,
            enable_sprint=True,
        )
        if remaining is not None:
            self.log_error(f'{state}移动失败，剩余路径: {remaining}')
            return False
        self.sleep(0.5)
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

    def _start_auto_battle(self):
        self.send_key(self.get_custom_key('Auto Battle'))

    def _stop_auto_battle(self):
        self.send_key(self.get_custom_key('Auto Battle'))
