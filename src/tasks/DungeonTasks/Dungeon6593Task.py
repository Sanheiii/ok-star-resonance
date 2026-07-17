import math

from src.packet_capture.parser import ActorState
from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon6593Task(DungeonTaskBase):

    def __init__(self, *args, **kwargs):
        self.task_name = 'Dungeon 6593'
        self.task_name_zh = '镜中的审判 - 困难'
        self.task_desc = 'S4 Dungeon "镜中的审判" - Hard'
        self.task_desc_zh = '启动前需要使用正确的网卡开始抓包'
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
        self.investigate(None)

        # 等人机去找怪打再动
        self.info['state'] = '等待人机往前冲'
        self.sleep(4)
        # 移动到右侧桩怪背后
        self.move_to_position(self.position,(-9.190, -19.024))
        self.send_key('h')
        # 按顺序解决三个桩怪
        monsters = (
            (34017, (-9.000, -19.000)),
            (34018, (-9.000, 15.600)),
            (34019, (18.000, 0.000)),
        )
        self.info['state'] = '大广场战斗中'
        if not self._clear_monsters(monsters):
            self.log_error('广场三个桩超时')
            return False

        # 确认击杀的只有桩怪，可能留小怪，先等脱战
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('广场三个桩清完了，但是剩余小怪超时没有脱战')
            return False
        self.sleep(3)
        # 广场清完了关h
        self.send_key('h')

        jump_points1 = (
            (23.740, 9.808),
            (30.430, 13.940),
            (38.610, 10.980),
            (46.430, 7.800),
            (50.840, 0.810),
            (50.974, -7.304),
        )
        # 先走到跳台起始点，走路方法会自动复活
        self.info['state'] = '前往跳台起始点'
        self.move_to_position(self.position, jump_points1[0], 0.5, 0.5)
        self.info['state'] = '第一次跳台'

        if not self._jump_route(jump_points1):
            # 如果失败了重试到成功为止
            while True:
                self.move_to_position(self.position, jump_points1[0], 0.5, 0.5)
                if self._jump_route(jump_points1):
                    break

        # 在第一个浮空岛战斗
        self.info['state'] = '第一个小浮空岛战斗中'
        self.send_key('h')
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('第一个小浮空岛战斗超时')
            return False
        # 第一个小浮空岛清完了关h
        self.send_key('h')

        # 第二次跳台
        jump_points2 = (
            (62.046, -11.995),
            (68.830, -8.110),
            (72.190, -1.040),
            (68.020, 5.300),
            (65.240, 12.720),
            (68.530, 19.630),
            (70.680, 27.130),
            (82.517, 26.304),
        )
        self.info['state'] = '第二次跳台'
        if not self._jump_route(jump_points2):
            # 如果失败了重试到成功为止
            while True:
                self.move_to_position(self.position, jump_points1[0], 0.5, 0.5)
                if self._jump_route(jump_points1) and self._jump_route(jump_points2):
                    break

        # 在第二个浮空岛战斗
        self.send_key('h')
        self.info['state'] = '第二个小浮空岛战斗中'
        if not self.wait_out_of_combat(time_out=180):
            self.log_error('第二个小浮空岛战斗超时')
            return False

        # Boss战
        self.info['state'] = '道中清完了，等待Boss动画'
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
        self.info['state'] = 'Boss战中'
        self.move_to_position(self.position, boss_position, target_tolerance=2)
        self.sleep(3)
        if not self.wait_out_of_combat(time_out=420):
            self.log_error('Boss战超时')
            return False

        # 结算
        self.handle_end()

    def _clear_monsters(self, monsters):
        for monster_id, target_position in monsters:
            while not self.move_to_position(self.position, target_position, target_tolerance=2):
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
                        self.move_to_position(current_position, safe_position, target_tolerance=1)
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

    def _jump_route(self, positions):
        positions = tuple(positions)
        if not positions:
            return True

        if not self.move_to_position(self.position, positions[0], target_tolerance=0.5):
            self.log_error('移动到跳台初始点位失败')
            return False

        route = positions[1:]
        for index, target_position in enumerate(route):
            if not self.look_at(target_position):
                self.log_error('无法识别镜头朝向')
                self.rotate_camera(5)
            self.sleep(0.5)
            if not self.look_at(target_position):
                self.log_error('无法识别镜头朝向')
            self.sleep(0.3)
            self.send_key_down('w')
            try:
                self.sleep(0.9)
                self.send_key('space')
                self.sleep(0.2)
                if index == len(route) - 1:
                    self.send_key('q')
                self.send_key_up('w')
            finally:
                self.send_key_up('w')
            self.sleep(2)

            # 如果跳台摔下去了返回 False
            blocked_states = {
                ActorState.FALL,
                ActorState.TELEPORT,
                ActorState.FALL_TELEPORT,
            }
            blocked_positions = {
                (19.050, 13.770),
                (-43.480, -7.870),
            }
            position_blocked = any(
                abs(self.position[0] - x) < 0.001
                and abs(self.position[2] - z) < 0.001
                for x, z in blocked_positions
            )

            # 跳完摔下去或者被传送走
            if self.actor_state in blocked_states or position_blocked:
                self.sleep(3)
                return False
            if not self.move_to_position(self.position, target_position, target_tolerance=0.5, max_path_deviation=3):
                self.log_error('移动到跳台中心点失败')
                return False
        return True
