import math

from src.tasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon6593Task(DungeonTaskBase):

    def __init__(self, *args, **kwargs):
        self.task_name = 'Dungeon 6593'
        self.task_name_zh = '镜中的审判 - 困难'
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False
        super().__init__(*args, **kwargs)

    def run(self):
        if not super().run():
            return
        # 开本仪器
        self.investigate(None)
        # 往前走几步
        if not self.move_to_position(self.position, (-15.432, -10.630)):
            return
        self.send_key('h')
        while self.is_dead or self.in_combat == 1:
            if self.is_dead:
                if not self.handle_death():
                    return
                continue

            current_position = self.position
            entities = self.nearby_entities
            # 取最近的怪物，排除id为34016的怪物
            nearest = self._nearest_entity(current_position, entities)
            if nearest is None:
                self.sleep(0.2)
                continue

            target_position, distance = nearest
            # 如果最近的怪物距离玩家超过10米则向怪物移动直到进入10米范围
            if distance > 10 and not self.move_to_position(
                    current_position, target_position, target_tolerance=10):
                return
            # 面向怪物
            if not self.is_dead:
                self.look_at(target_position)
            self.sleep(0.2)
        self.sleep(3)
        if self.is_dead and not self.handle_death():
            return

        # 依次站在下面点位，然后面向下一个点位，然后按下w，等待0.5秒后按两次space，间隔0.5s，然后松开w，然后用self.move_to_position校准落点，target_tolerance=1
        jump_points1 = (
            (21.653, 10.925),
            (30.430, 13.940),
            (38.610, 10.980),
            (46.430, 7.800),
            (50.840, 0.810),
            (50.781, 5.821),
        )
        if not self._jump_route(jump_points1):
            return

        self.sleep(1)

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
        if not self.move_to_position(
                self.position, positions[0], target_tolerance=1):
            return False

        for target_position in positions[1:]:
            if not self.look_at(target_position):
                self.log_error('无法识别镜头朝向')
                return False
            self.send_key_down('w')
            try:
                self.sleep(0.5)
                self.send_key('space')
                self.sleep(0.5)
                self.send_key('space')
            finally:
                self.send_key_up('w')
            if not self.move_to_position(
                    self.position, target_position, target_tolerance=1):
                return False
        return True
