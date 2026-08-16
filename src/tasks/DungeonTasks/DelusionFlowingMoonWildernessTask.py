import math
import time

from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class DelusionFlowingMoonWildernessTask(DungeonTaskBase):

    INSTRUMENT_POSITION = (-50.000, -400.000)
    COMBAT_ROUNDS = (
        (5023, 1955),
        (5024, 1956),
        (5025, 1957),
    )
    # 黑：5020
    # 银：5026、5027
    # 绿：5039、5038、5037
    # 5022找140155，5021找140154，交互后等待一分钟，再找出口门
    MASTER_INTERACTION_ATTR_ID = 5020
    MASTER_SILVER_GATE_ATTR_IDS = (5026, 5027)
    MASTER_GREEN_GATES = (
        (5039, (-256.953, -382.241)),
        (5038, (166.698, -391.799)),
        (5037, (65.990, -246.499)),
    )
    MASTER_5026_NPC_ATTR_ID = 140156
    MASTER_5027_NPC_ATTR_ID = 140157
    MASTER_5040_ATTR_ID = 5040
    MASTER_5026_MONSTER_ATTR_ID = 1960
    MASTER_FALLBACK_ENTRY_ATTR_IDS = (5022, 5021)
    MASTER_5022_NPC_ATTR_ID = 140155
    MASTER_5021_NPC_ATTR_ID = 140154
    MASTER_5021_POSITION = (-13.169, -218.602)
    MASTER_5021_LOOP_TIMEOUT = 60
    MASTER_FALLBACK_WAIT_TIME = 60
    EXIT_SCENE_OBJECT_ATTR_ID = 5029
    BOSS_ENTRANCE_ATTR_ID = 5028
    BOSS_ATTR_ID = 33420
    ENTITY_WAIT_TIMEOUT = 10

    def __init__(self, *args, **kwargs):
        self.task_name = 'Delusion - Flowing Moon Wilderness'
        self.task_name_zh = '弥妄·流月之野'
        self.task_desc = ''
        self.task_desc_zh = ''
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False
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
        self._master_boss_entrance_found = False

        if self.difficulty is Difficulty.MASTER1:
            if not self._run_master_route():
                return False
        elif not self._run_hard_route():
            return False

        if not self._use_scene_object(
                self.BOSS_ENTRANCE_ATTR_ID, '前往Boss入口'):
            return False

        boss_position = self._wait_for_entity_position(
            self.BOSS_ATTR_ID,
            entity_type=1,
        )
        if boss_position is None:
            self.log_error(f'等待Boss超时: {self.BOSS_ATTR_ID}')
            return False

        self.info['State'] = '跳过Boss出场动画'
        for _ in range(3):
            self.send_key('esc', after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break

        if not self._move_to_entity(boss_position, 'Boss'):
            return False
        self.click(0.5, 0.5)
        self.send_key(self.get_custom_key('Auto Battle'))

        if not self.wait_in_combat():
            self.log_error('Boss没有进入战斗')
            return False
        self.info['State'] = 'Boss战斗中'
        if not self.wait_out_of_combat(time_out=420):
            self.log_error('Boss战斗超时')
            return False

        self.info['State'] = '跳过Boss结算动画'
        for _ in range(3):
            self.send_key('esc', after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break

        return self.handle_end()

    def _run_hard_route(self):
        for scene_object_attr_id, monster_attr_id in self.COMBAT_ROUNDS:
            self.move_to_position(self.position, (-50.000, -380.000), enable_sprint=True)
            if not self._clear_round(scene_object_attr_id, monster_attr_id):
                return False
            if getattr(self, '_master_boss_entrance_found', False):
                return True
        return True

    def _run_master_route(self):
        while True:
            # The boss entrance means all optional combat rounds are complete.
            if DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
                    self.nearby_entities,
                    self.BOSS_ENTRANCE_ATTR_ID,
                    entity_type=3) is not None:
                return True

            if self._wait_for_entity_position(
                    self.MASTER_INTERACTION_ATTR_ID,
                    entity_type=3) is None:
                if not self._run_master_special_route():
                    return False
                continue
            self.sleep(1)
            combat_round = self._find_combat_round()
            if combat_round is not None:
                scene_object_attr_id, monster_attr_id = combat_round
                self.move_to_position(
                    self.position,
                    (-50.000, -380.000),
                    enable_sprint=True,
                )
                if not self._clear_round(
                        scene_object_attr_id, monster_attr_id):
                    return False
                continue

            target_gate = (
                DelusionFlowingMoonWildernessTask._find_master_target_gate(
                    self.nearby_entities,
                )
            )
            if target_gate is not None:
                if not self._run_master_target_gate(target_gate):
                    return False
                if getattr(self, '_master_boss_entrance_found', False):
                    return True
                if not self._use_master_exit():
                    return False
                continue

            if not self._use_scene_object(
                    self.MASTER_INTERACTION_ATTR_ID,
                    f'交互场景物体 {self.MASTER_INTERACTION_ATTR_ID}'):
                return False
            self.info['State'] = '等待大师道中变化'
            self.sleep(3)

    @staticmethod
    def _find_master_target_gate(entities):
        for attr_id in (
                DelusionFlowingMoonWildernessTask.MASTER_SILVER_GATE_ATTR_IDS):
            if DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
                    entities,
                    attr_id,
                    entity_type=3) is not None:
                return attr_id
        for attr_id, _position in (
                DelusionFlowingMoonWildernessTask.MASTER_GREEN_GATES):
            if DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
                    entities,
                    attr_id,
                    entity_type=3) is not None:
                return attr_id
        return None

    def _run_master_target_gate(self, gate_attr_id):
        green_gate_positions = dict(self.MASTER_GREEN_GATES)
        if gate_attr_id in green_gate_positions:
            return self._run_master_green_route(
                gate_attr_id,
                green_gate_positions[gate_attr_id],
            )
        if gate_attr_id == 5026:
            return self._run_master_5026_route()
        if gate_attr_id == 5027:
            return self._run_master_5027_route()
        self.log_error(f'未知大师道中入口: {gate_attr_id}')
        return False

    def _run_master_green_route(self, gate_attr_id, target_position):
        if not self._use_scene_object(
                gate_attr_id, f'进入绿门 {gate_attr_id}'):
            return False
        self.info['State'] = f'等待绿门 {gate_attr_id} 变化'
        self.sleep(1)

        self.info['State'] = f'前往绿门 {gate_attr_id} 战斗区域'
        if not self.move_to_position(
                self.position,
                target_position,
                enable_sprint=True):
            self.log_error(f'前往绿门 {gate_attr_id} 战斗区域失败')
            return False

        self.send_key(self.get_custom_key('Auto Battle'))
        if not self.wait_in_combat():
            self.log_error(f'绿门 {gate_attr_id} 没有进入战斗')
            return False
        self.info['State'] = f'绿门 {gate_attr_id} 战斗中'
        if not self.wait_out_of_combat(time_out=180):
            self.log_error(f'绿门 {gate_attr_id} 战斗超时')
            return False
        self.send_key(self.get_custom_key('Auto Battle'))
        return True

    def _run_master_5026_route(self):
        if not self._use_scene_object(5026, '进入银门 5026'):
            return False

        npc_position = self._wait_for_entity_position(
            self.MASTER_5026_NPC_ATTR_ID,
            entity_type=2,
        )
        if npc_position is None:
            self.log_error(f'等待NPC超时: {self.MASTER_5026_NPC_ATTR_ID}')
            return False
        if not self._move_to_entity(
                npc_position, f'前往NPC {self.MASTER_5026_NPC_ATTR_ID}'):
            return False

        self._interact_master_npc(self.MASTER_5026_NPC_ATTR_ID)
        self.info['State'] = '等待银门 5026 事件'

        target_entities = self._wait_for_entities(
            self.MASTER_5040_ATTR_ID,
            entity_type=3,
        )
        if target_entities is None:
            self.log_error(f'等待目标超时: {self.MASTER_5040_ATTR_ID}')
            return False
        target_entities = (
            DelusionFlowingMoonWildernessTask._sort_entities_by_distance(
                self.position,
                target_entities,
            )
        )
        last_backtick_time = None
        for entity_uuid, target_entity in target_entities:
            entity = self.nearby_entities.get(
                entity_uuid,
                target_entity,
            )
            if (entity.get('attr_id') != self.MASTER_5040_ATTR_ID
                    or entity.get('entity_type') != 3
                    or entity.get('position') is None):
                continue
            if not self._move_to_entity(
                    entity['position'], f'前往目标 {self.MASTER_5040_ATTR_ID}'):
                return False
            if last_backtick_time is not None:
                remaining_wait = 3.2 - (
                    time.monotonic() - last_backtick_time
                )
                if remaining_wait > 0:
                    self.sleep(remaining_wait)
            last_backtick_time = time.monotonic()
            self.send_key('`', after_sleep=1)

        monster_position = self._wait_for_entity_position(
            self.MASTER_5026_MONSTER_ATTR_ID,
            entity_type=1,
        )
        if monster_position is None:
            self.log_error(
                f'等待怪物超时: {self.MASTER_5026_MONSTER_ATTR_ID}'
            )
            return False
        if not self._move_to_entity(
                monster_position,
                f'前往怪物 {self.MASTER_5026_MONSTER_ATTR_ID}'):
            return False

        self.send_key(self.get_custom_key('Auto Battle'))
        if not self.wait_in_combat():
            self.log_error('银门 5026 没有进入战斗')
            return False
        self.info['State'] = '银门 5026 战斗中'
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('银门 5026 战斗超时')
            return False
        self.send_key(self.get_custom_key('Auto Battle'))
        return True

    def _run_master_5027_route(self):
        if not self._use_scene_object(5027, '进入银门 5027'):
            return False

        npc_position = self._wait_for_entity_position(
            self.MASTER_5027_NPC_ATTR_ID,
            entity_type=2,
        )
        if npc_position is None:
            self.log_error(f'等待NPC超时: {self.MASTER_5027_NPC_ATTR_ID}')
            return False
        if not self._move_to_entity(
                npc_position, f'前往NPC {self.MASTER_5027_NPC_ATTR_ID}'):
            return False

        self._interact_master_npc(self.MASTER_5027_NPC_ATTR_ID)
        while True:
            event_exit = self._find_master_event_exit()
            if event_exit is not None:
                return True
            self.send_key('`', after_sleep=1)

    def _interact_master_npc(self, npc_attr_id):
        self.info['State'] = f'交互NPC {npc_attr_id}'
        self.send_key('f', after_sleep=1)
        self.send_key('w', down_time=0.5, after_sleep=1)
        self.send_key('f', after_sleep=1)

    def _wait_for_entities(self, attr_id, entity_type):
        result = {'entities': None}

        def find_entities():
            result['entities'] = {
                entity_uuid: entity
                for entity_uuid, entity in self.nearby_entities.items()
                if (entity.get('attr_id') == attr_id
                    and entity.get('entity_type') == entity_type
                    and entity.get('position') is not None)
            }
            return bool(result['entities'])

        if not self.wait_until(
                find_entities,
                time_out=self.ENTITY_WAIT_TIMEOUT):
            return None
        return result['entities']

    @staticmethod
    def _sort_entities_by_distance(current_position, entities):
        remaining_entities = dict(entities)
        ordered_entities = []
        next_position = current_position
        while remaining_entities:
            current_x, current_z = (
                DelusionFlowingMoonWildernessTask._position_xz(next_position)
            )
            entity_uuid, entity = min(
                remaining_entities.items(),
                key=lambda item: math.hypot(
                    DelusionFlowingMoonWildernessTask._position_xz(
                        item[1]['position']
                    )[0] - current_x,
                    DelusionFlowingMoonWildernessTask._position_xz(
                        item[1]['position']
                    )[1] - current_z,
                ),
            )
            ordered_entities.append((entity_uuid, entity))
            next_position = entity['position']
            del remaining_entities[entity_uuid]
        return ordered_entities

    @staticmethod
    def _position_xz(position):
        if len(position) >= 3:
            return position[0], position[2]
        return position[0], position[1]

    def _find_master_event_exit(self):
        boss_position = DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
            self.nearby_entities,
            self.BOSS_ENTRANCE_ATTR_ID,
            entity_type=3,
        )
        if boss_position is not None:
            self._master_boss_entrance_found = True
            return self.BOSS_ENTRANCE_ATTR_ID, boss_position

        exit_position = DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
            self.nearby_entities,
            self.EXIT_SCENE_OBJECT_ATTR_ID,
            entity_type=3,
        )
        if exit_position is not None:
            return self.EXIT_SCENE_OBJECT_ATTR_ID, exit_position
        return None

    def _wait_for_master_event_exit(self):
        result = {'exit': None}

        def find_exit():
            result['exit'] = self._find_master_event_exit()
            return result['exit'] is not None

        if not self.wait_until(
                find_exit,
                time_out=self.ENTITY_WAIT_TIMEOUT):
            return None
        return result['exit']

    def _use_master_exit(self):
        event_exit = self._wait_for_master_event_exit()
        if event_exit is None:
            self.log_error('等待5029或5028超时')
            return False
        attr_id, position = event_exit
        if attr_id == self.BOSS_ENTRANCE_ATTR_ID:
            return True

        if self._find_master_event_exit() is not None:
            if getattr(self, '_master_boss_entrance_found', False):
                return True
            position = DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
                self.nearby_entities,
                self.EXIT_SCENE_OBJECT_ATTR_ID,
                entity_type=3,
            ) or position
        if not self._move_to_entity(
                position, f'前往场景物体 {self.EXIT_SCENE_OBJECT_ATTR_ID}'):
            return False
        self._find_master_event_exit()
        if getattr(self, '_master_boss_entrance_found', False):
            return True
        self.send_key('f')
        self.send_key('w', down_time=0.5)
        self.send_key('f', after_sleep=4)
        return True

    def _run_master_special_route(self):
        entry = self._wait_for_any_entity_position(
            self.MASTER_FALLBACK_ENTRY_ATTR_IDS,
            entity_type=3,
        )
        if entry is None:
            self.log_error('没有等到Boss传送门，空传送门，或金娜传送门')
            return False

        entry_attr_id, _entry_position = entry
        if entry_attr_id == 5022:
            if not self._run_master_5022_route():
                return False
        elif entry_attr_id == 5021:
            if not self._run_master_5021_route():
                return False
        else:
            self.log_error(f'未知金娜入口: {entry_attr_id}')
            return False

        if getattr(self, '_master_boss_entrance_found', False):
            return True
        return self._use_master_exit()

    def _run_master_5022_route(self):
        if not self._use_scene_object(5022, '进入云朵金娜'):
            return False

        npc_position = self._wait_for_entity_position(
            self.MASTER_5022_NPC_ATTR_ID,
            entity_type=2,
        )
        if npc_position is None:
            self.log_error(f'等待NPC超时: {self.MASTER_5022_NPC_ATTR_ID}')
            return False
        if not self._move_to_entity(
                npc_position, f'前往NPC {self.MASTER_5022_NPC_ATTR_ID}'):
            return False

        self.info['State'] = f'交互NPC {self.MASTER_5022_NPC_ATTR_ID}'
        self.send_key('f', after_sleep=1)
        self.send_key('w', down_time=0.5, after_sleep=1)
        self.send_key('f', after_sleep=1)
        self.info['State'] = '等待直到云朵事件超时'
        self.sleep(self.MASTER_FALLBACK_WAIT_TIME)
        return True

    def _run_master_5021_route(self):
        if not self._use_scene_object(5021, '进入花朵金娜'):
            return False

        npc_position = self._wait_for_entity_position(
            self.MASTER_5021_NPC_ATTR_ID,
            entity_type=2,
        )
        if npc_position is None:
            self.log_error(f'等待NPC超时: {self.MASTER_5021_NPC_ATTR_ID}')
            return False
        if not self._move_to_entity(
                npc_position, f'前往NPC {self.MASTER_5021_NPC_ATTR_ID}'):
            return False

        self.info['State'] = f'交互NPC {self.MASTER_5021_NPC_ATTR_ID}'
        self.send_key('f', after_sleep=1)
        self.send_key('w', down_time=0.5, after_sleep=1)
        self.send_key('f', after_sleep=1)

        self.info['State'] = '前往幻幻花'
        if not self.move_to_position(
                self.position,
                self.MASTER_5021_POSITION,
                target_tolerance=1,
                enable_sprint=True):
            self.log_error(f'前往幻幻花失败')
            return False
        self.send_key('space', after_sleep=0.5)
        self.send_key('q', after_sleep=1)

        deadline = time.monotonic() + self.MASTER_5021_LOOP_TIMEOUT
        while True:
            if self.is_dead:
                self.handle_death()
            event_exit = self._find_master_event_exit()
            if event_exit is not None:
                return True
            if time.monotonic() >= deadline:
                self.log_error('花朵金娜循环超时')
                return False
            self.send_key('space', after_sleep=1.5)
            self.send_key('`', after_sleep=1)

    def _find_combat_round(self):
        for scene_object_attr_id, monster_attr_id in self.COMBAT_ROUNDS:
            if DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
                    self.nearby_entities,
                    scene_object_attr_id,
                    entity_type=3) is not None:
                return scene_object_attr_id, monster_attr_id
        return None

    def _wait_for_any_entity_position(self, attr_ids, entity_type):
        attr_ids = set(attr_ids)
        result = {'entity': None}

        def find_entity():
            result['entity'] = next((
                (entity.get('attr_id'), entity.get('position'))
                for entity in self.nearby_entities.values()
                if (entity.get('attr_id') in attr_ids
                    and entity.get('entity_type') == entity_type
                    and entity.get('position') is not None)
            ), None)
            return result['entity'] is not None

        if not self.wait_until(
                find_entity,
                time_out=self.ENTITY_WAIT_TIMEOUT):
            return None
        return result['entity']

    @staticmethod
    def _find_nearby_entity_position(entities, attr_id, entity_type):
        return next((
            entity.get('position')
            for entity in entities.values()
            if (entity.get('attr_id') == attr_id
                and entity.get('entity_type') == entity_type
                and entity.get('position') is not None)
        ), None)

    def _clear_round(self, scene_object_attr_id, monster_attr_id):
        if not self._use_scene_object(
                scene_object_attr_id,
                f'前往场景物体 {scene_object_attr_id}'):
            return False

        monster_position = self._wait_for_entity_position(
            monster_attr_id,
            entity_type=1,
        )
        if monster_position is None:
            self.log_error(f'等待怪物超时: {monster_attr_id}')
            return False
        if not self._move_to_entity(monster_position, f'怪物 {monster_attr_id}'):
            return False

        self.send_key(self.get_custom_key('Auto Battle'))
        if not self.wait_in_combat():
            self.log_error(f'怪物没有进入战斗: {monster_attr_id}')
            return False
        self.info['State'] = f'怪物 {monster_attr_id} 战斗中'
        if not self.wait_out_of_combat(time_out=180):
            self.log_error(f'怪物战斗超时: {monster_attr_id}')
            return False
        self.send_key(self.get_custom_key('Auto Battle'))

        return self._use_master_exit()

    def _use_scene_object(self, attr_id, state):
        position = self._wait_for_entity_position(attr_id, entity_type=3)
        if position is None:
            self.log_error(f'等待场景物体超时: {attr_id}')
            return False
        if not self._move_to_entity(position, state):
            return False
        self.send_key('f')
        self.send_key('w', down_time=0.5)
        self.send_key('f', after_sleep=4)
        return True

    def _move_to_entity(self, position, state):
        self.info['State'] = state
        if self.move_to_position(
                self.position,
                position,
                target_tolerance=1,
                enable_sprint=True):
            return True
        self.log_error(f'{state}移动失败: {position}')
        return False

    def _wait_for_entity_position(self, attr_id, entity_type):
        result = {'position': None}

        def find_entity():
            result['position'] = (
                DelusionFlowingMoonWildernessTask._find_nearby_entity_position(
                    self.nearby_entities,
                    attr_id,
                    entity_type,
                )
            )
            return result['position'] is not None

        if not self.wait_until(
                find_entity,
                time_out=self.ENTITY_WAIT_TIMEOUT):
            return None
        return result['position']
