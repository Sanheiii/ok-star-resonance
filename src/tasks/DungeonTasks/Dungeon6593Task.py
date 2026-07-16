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
        # 依次走到下面坐标的10范围内，等待怪物消失
        monsters = (
            (34017, (-9.000, -15.600)),
            (34018, (-9.000, 15.600)),
            (34019, (18.000, 0.000)),
        )
        if not self._clear_monsters(monsters):
            return
        self.sleep(3)
        if self.is_dead and not self.handle_death():
            return

        # 依次站在下面点位，然后面向下一个点位，然后按下w，等待0.5秒后按两次space，间隔0.5s，然后松开w，等待2秒，然后用self.move_to_position校准落点，target_tolerance=1
        jump_points1 = (
            (21.653, 10.925),
            (30.430, 13.940),
            (38.610, 10.980),
            (46.430, 7.800),
            (50.840, 0.810),
            (50.974, -7.304),
        )
        if not self._jump_route(jump_points1):
            return

        self.sleep(1)

    def _clear_monsters(self, monsters):
        for monster_id, target_position in monsters:
            if not self.move_to_position(
                    self.position, target_position, target_tolerance=2):
                return False
            while any(
                    entity.get('attr_id') == monster_id
                    for entity in self.nearby_entities.values()):
                if self.is_dead and not self.handle_death():
                    return False
                self.sleep(0.2)
        return True

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
            self.sleep(2)
            if not self.move_to_position(
                    self.position, target_position, target_tolerance=1):
                return False
        return True
