import math

from src.packet_capture.parser import ActorState
from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon6593Task(DungeonTaskBase):

    def __init__(self, *args, **kwargs):
        self.task_name = 'Judgment in the Mirror - Hard'
        self.task_name_zh = '镜中的审判 - 困难'
        self.task_desc = 'Not recommended for Wind Knights using the Skyward specialization.'
        self.task_desc_zh = '不建议使用青岚骑士空战流执行此任务。'
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False
        super().__init__(*args, **kwargs)

    def run(self):
        super().run()
        while True:
            if not self.exec():
                self.return_to_initial_state()

    def exec(self):
        # 进本与开启仪器
        if not self.begin():
            return False
        self.investigate((-29.350, -7.840))

        # 等人机去找怪打再动
        self.info['State'] = '等待人机往前冲'
        self.sleep(4)
        # 移动到右侧桩怪背后
        self.move_to_position(self.position,(-9.190, -19.024), enable_sprint = True)
        self.send_key('h')
        # 按顺序解决三个桩怪
        monsters = (
            (34017, (-9.000, -19.000)),
            (34018, (-9.000, 15.600)),
            (34019, (18.000, 0.000)),
        )
        self.info['State'] = '大广场战斗中'
        if not self._clear_monsters(monsters):
            self.log_error('广场三个桩超时')
            return False

        # 确认击杀的只有桩怪，可能留小怪，先等脱战
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('广场三个桩清完了，但是剩余小怪超时没有脱战')
            return False
        self.sleep(3)

        self.info['State'] = '第一次跳台'
        # 二段跳收起武器
        self.send_key('space', after_sleep=0.2)
        self.send_key('space', after_sleep=2)
        while not self._jump_to_area2():
            pass

        # 在第一个浮空岛战斗
        self.info['State'] = '第一个小浮空岛战斗中'
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('第一个小浮空岛战斗超时')
            return False

        self.info['State'] = '第二次跳台'
        # 二段跳收起武器
        self.send_key('space', after_sleep=0.2)
        self.send_key('space', after_sleep=2)
        if not self._jump_to_area3():
            # 如果失败了重试到成功为止
            while True:
                if self._jump_to_area2() and self._jump_to_area3():
                    break


        # 在第二个浮空岛战斗
        self.info['State'] = '第二个小浮空岛战斗中'
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('第二个小浮空岛战斗超时')
            return False

        # Boss战
        self.info['State'] = '道中清完了，等待Boss动画'
        self.sleep(7)
        nearby_entities = self.nearby_entities
        boss_position = next((
            entity.get('position')
            for entity in nearby_entities.values()
            if (entity.get('attr_id') == 34000
                and entity.get('position') is not None)
        ), None)
        if boss_position is None:
            self.log_error('没有检测到Boss')
            return False
        self.info['State'] = 'Boss战中'
        self.move_to_position(self.position, boss_position, target_tolerance=2, enable_sprint = True)
        self.sleep(3)
        if not self.wait_out_of_combat(time_out=420):
            self.log_error('Boss战超时')
            return False

        # 结算
        self.handle_end()

    def _clear_monsters(self, monsters):
        for monster_id, target_position in monsters:
            while not self.move_to_position(self.position, target_position, target_tolerance=2, enable_sprint = True):
                self.sleep(1)
            while True:
                nearby_entities = self.nearby_entities
                if not any(
                        entity.get('attr_id') == monster_id
                        for entity in nearby_entities.values()):
                    break
                dummy_positions = self._dummy_positions(nearby_entities)
                current_position = self.position
                if (dummy_positions
                        and self._is_near_any_position(
                            current_position,
                            dummy_positions,
                            6,
                        )):
                    safe_position = self._first_clockwise_safe_position(
                        current_position,
                        dummy_positions,
                        6,
                    )
                    if safe_position is not None:
                        self.move_to_position(current_position, safe_position, target_tolerance=1, enable_sprint = True)
                self.sleep(0.2)
        return True

    @staticmethod
    def _dummy_positions(entities):
        return [
            entity.get('position')
            for entity in entities.values()
            if (entity.get('entity_type') == 11
                and entity.get('attr_id') == 3400013
                and entity.get('position') is not None)
        ]

    def _is_near_any_position(
            self, current_position, positions, minimum_distance):
        if current_position is None:
            return False
        current_x, current_z = self._xz(current_position)
        return any(
            math.hypot(target_x - current_x, target_z - current_z)
            < minimum_distance
            for target_x, target_z in map(self._xz, positions)
        )

    def _first_clockwise_safe_position(
            self, current_position, obstacle_positions, minimum_distance):
        if current_position is None:
            return None
        current_x, current_z = self._xz(current_position)
        radius = math.hypot(current_x, current_z)
        if radius == 0:
            return None

        obstacles = [self._xz(position) for position in obstacle_positions]
        start_angle = math.atan2(current_z, current_x)
        for step in range(1, 361):
            angle = start_angle - math.radians(step)
            candidate = (
                radius * math.cos(angle),
                radius * math.sin(angle),
            )
            if all(
                    math.hypot(
                        candidate[0] - obstacle_x,
                        candidate[1] - obstacle_z,
                    ) >= minimum_distance
                    for obstacle_x, obstacle_z in obstacles):
                return candidate
        return None

    def _nearest_entity(self, current_position, entities):
        if current_position is None:
            return None
        current_x, current_z = self._xz(current_position)
        candidates = []
        for entity in entities.values():
            position = entity.get('position')
            if (position is None
                    or entity.get('attr_id') == 34016):
                continue
            target_x, target_z = self._xz(position)
            candidates.append((position, math.hypot(
                target_x - current_x,
                target_z - current_z,
            )))
        return min(candidates, key=lambda candidate: candidate[1], default=None)


    def _jump_to_area2(self):
        start_pos = (22.693, -12.085)
        camera_dir = 90
        # 大概走到位置
        if self.move_to_positions([(0, 0), start_pos], node_tolerance=2, max_path_deviation=5, enable_sprint=True) is not None:
            return False
        # 看地面
        self._move_mouse_relative(0, 500)
        # 两次纠正视角
        self.look_at(camera_dir)
        self.sleep(1)
        self.look_at(camera_dir)
        # 开启走路增加精度，然后走到起始点
        self.send_key('rctrl', after_sleep=0.2)
        self.send_key('s', down_time=2, after_sleep=0.1)
        self.send_key('w', down_time=1, after_sleep=0.1)
        if not self.move_to_position(self.position, start_pos, target_tolerance=0.1, max_path_deviation=3, rotate_camera=False):
            return False
        self.send_key('rctrl', after_sleep=0.2)
        # 录制的操作
        self.send_key_down('w', after_sleep=0.82) # key down 'w'
        self.send_key('space', down_time=0.18, after_sleep=0.23)
        self.send_key('space', down_time=0.19, after_sleep=0.21)
        self.send_key('q', down_time=0.16, after_sleep=1.69)
        self.send_key('q', down_time=0.11, after_sleep=0.11)
        self.send_key_up('w', after_sleep=5)
        # 检查是否被传送了
        return not self._is_teleported()

    def _jump_to_area3(self):
        start_pos = (57.887, -10.731)
        camera_dir = 33
        # 大概走到位置
        if not self.move_to_position(self.position, start_pos, target_tolerance=2, max_path_deviation=3):
            return False
        # 看地面
        self._move_mouse_relative(0, 500)
        # 两次纠正视角
        self.look_at(camera_dir)
        self.sleep(1)
        self.look_at(camera_dir)
        # 开启走路增加精度，然后走到起始点
        self.send_key('rctrl', after_sleep=0.2)
        self.send_key('s', down_time=2, after_sleep=0.1)
        self.send_key('w', down_time=1, after_sleep=0.1)
        if not self.move_to_position(self.position, start_pos, target_tolerance=0.1, max_path_deviation=3, rotate_camera=False):
            return False
        self.send_key('rctrl', after_sleep=0.2)
        # 录制的操作
        self.send_key_down('w', after_sleep=0.19)
        self.send_key_down('shift', after_sleep=0.63)
        self.send_key('space', down_time=0.25, after_sleep=0.29)
        self.send_key('space', down_time=0.23)
        self.send_key_up('shift', after_sleep=0.19)
        self.send_key('q', down_time=0.18, after_sleep=0.19)
        self.send_key('q', down_time=0.14, after_sleep=0.83)
        self.send_key('space', down_time=0.17, after_sleep=0.28)
        self.send_key('space', down_time=0.18, after_sleep=0.32)
        self.send_key('q', down_time=0.17, after_sleep=1.37)
        self.send_key('q', down_time=0.11, after_sleep=0.11)
        self.send_key_up('w', after_sleep=5)
        # 检查是否被传送了
        return not self._is_teleported()

    def _is_teleported(self):
        # 如果位置在这个点则认为跳失败了
        if abs(self.position[0] - -43.480) < 1 and abs(self.position[2] - -7.870) < 1:
            return True
        if abs(self.position[0] - 19.050) < 1 and abs(self.position[2] - 13.770) < 1:
            return True
        return False
