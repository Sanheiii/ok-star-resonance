from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon1722Task(DungeonTaskBase):

    INSTRUMENT_POSITION = (-50.000, -400.000)
    COMBAT_ROUNDS = (
        (5023, 1955),
        (5024, 1956),
        (5025, 1957),
    )
    EXIT_SCENE_OBJECT_ATTR_ID = 5029
    BOSS_ENTRANCE_ATTR_ID = 5028
    BOSS_ATTR_ID = 33420
    ENTITY_WAIT_TIMEOUT = 10

    def __init__(self, *args, **kwargs):
        self.task_name = 'Delusion - Flowing Moon Wilderness - Hard'
        self.task_name_zh = '弥妄·流月之野 - 困难'
        self.task_desc = 'Automatically clears Delusion - Flowing Moon Wilderness - Hard.'
        self.task_desc_zh = '自动通关弥妄·流月之野 - 困难。'
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

        for scene_object_attr_id, monster_attr_id in self.COMBAT_ROUNDS:
            self.move_to_position(self.position, (-50.000, -380.000), enable_sprint=True)
            if not self._clear_round(scene_object_attr_id, monster_attr_id):
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

        return self._use_scene_object(
            self.EXIT_SCENE_OBJECT_ATTR_ID,
            f'前往场景物体 {self.EXIT_SCENE_OBJECT_ATTR_ID}',
        )

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
                target_tolerance=1.5,
                enable_sprint=True):
            return True
        self.log_error(f'{state}移动失败: {position}')
        return False

    def _wait_for_entity_position(self, attr_id, entity_type):
        result = {'position': None}

        def find_entity():
            result['position'] = next((
                entity.get('position')
                for entity in self.nearby_entities.values()
                if (entity.get('attr_id') == attr_id
                    and entity.get('entity_type') == entity_type
                    and entity.get('position') is not None)
            ), None)
            return result['position'] is not None

        if not self.wait_until(
                find_entity,
                time_out=self.ENTITY_WAIT_TIMEOUT):
            return None
        return result['position']
