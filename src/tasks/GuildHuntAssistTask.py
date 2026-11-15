import math

from src.tasks.AutoPartyTask import AutoPartyTask
from src.tasks.AutoReviveTask import AutoReviveTask
from src.tasks.ClaimMonthlyPassTask import ClaimMonthlyPassTask
from src.tasks.MissionEntryTask import MissionEntryTask
from src.tasks.SRTask import SRTask


class GuildHuntAssistTask(SRTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Guild Hunt"
        self.description = "Auto-accept invites and assist in Guild Hunts."
        self.default_config.update({
            'I\'m Tank': False,
            'Opening Skill': 'Z',
            "Combat Wait Time": 5,
            'Use Packet Capture': False,
            'Approach Boss': True,
            'Boss Approach Distance (m)': 9,
            'Move Behind Boss': False,
        })
        self.config_type['Combat Wait Time'] = {'min': 0}
        self.config_type['Boss Approach Distance (m)'] = {'min': 0}
        self._reset_hunt_state()

    def _reset_hunt_state(self):
        self.executed = False
        self._combat_teammates = set()
        self._combat_scene_id = None
        self._boss_rear_target = None
        self.info['Teammate Count'] = 0

    def run(self):
        if self.config.get('Use Packet Capture', False) or self.config.get('Move Behind Boss', False):
            self._require_packet_capture()
        self._reset_hunt_state()
        self.info['Entry Count'] = 0
        while True:
            use_packet_capture = (
                self.config.get('Use Packet Capture', False)
                or self.config.get('Move Behind Boss', False)
            )
            if use_packet_capture:
                self._require_packet_capture()
                if self._combat_scene_id != self.scene_id:
                    self._reset_hunt_state()
                    self._combat_scene_id = self.scene_id

            if self._handle_reconnect():
                if use_packet_capture:
                    self._return_to_guild_scene()
                self.next_frame()
                continue

            # 检测队友退出队伍自动退队
            if self.find_one('teammate_left', box=self.box_of_screen(0.46, 0.18, 0.63, 0.30)):
                self.send_key('i')
                if self.wait_click_feature('leave_party', box=self.box_of_screen(0.89, 0.88, 1, 0.95), raise_if_not_found=False):
                    self.sleep(1)
                    self.click(0.62,0.74)
                self.sleep(1)
                self.send_key('esc')
                self.sleep(3)

            # 确认进入副本
            if self.find_one('loading'):
                # 刷新状态，允许进行操作
                self._reset_hunt_state()
                self.sleep(0.2)
                self.next_frame()
                continue

            # 检测到在副本内
            if not self.executed and self._is_in_guild_hunt():
                # Entry Count增加
                self.info['Entry Count'] += 1
                if self.config.get('I\'m Tank'):
                    # 是T
                    self.sleep(0.5)
                    self.send_key('e')
                    self.sleep(1)
                    self._move_briefly(('d',), 0.5)
                    self.sleep(0.5)
                    self.send_key(self.config.get('Opening Skill'))
                    self.sleep(0.5)
                    self.send_key('h')
                else:
                    # 不是T
                    wait_time = self.config.get("Combat Wait Time", 5)
                    self.sleep(wait_time)
                    self._move_briefly(('w', 'd'), 2)
                    self.sleep(0.5)
                    self.send_key(self.config.get('Opening Skill'))
                    self.sleep(0.5)
                    self.send_key('h')
                self.executed = True

            if use_packet_capture and self.executed:
                self._handle_packet_combat()

            # 点击下一步
            if box:=self.find_one('next', box=self.box_of_screen(0.46, 0.86, 0.53, 0.92)):
                self.click(box)
                self._reset_hunt_state()
            # 点击离开
            if box:=self.find_one('exit', box=self.box_of_screen(0.88, 0.91, 0.94, 0.97)):
                self.click(box)
                self.sleep(1)
                self._reset_hunt_state()

            self.next_frame()
            # 处理自动入队和自动复活
            self.run_task_by_class(AutoPartyTask)
            self.run_task_by_class(AutoReviveTask)
            self.run_task_by_class(MissionEntryTask)
            # 如果触发任务中勾了自动领取月卡则检查月卡
            claim_monthly_pass_task = self.get_task_by_class(ClaimMonthlyPassTask)
            if claim_monthly_pass_task.enabled:
                claim_monthly_pass_task.run()

    def _handle_reconnect(self):
        if self.find_one('single_confirm'):
            self.click(0.5, 0.74)
        elif self.find_one('anchor_login'):
            self.click(0.5, 0.83)
        elif self.find_one('anchor_select_chara'):
            self.click(0.86, 0.88)
        else:
            return False
        self._reset_hunt_state()
        self.sleep(1)
        return True

    def _is_in_guild_hunt(self):
        return self.find_one(
            'guild_hunt_title',
            box=self.box_of_screen(0.02, 0.21, 0.06, 0.24),
            threshold=0.6,
        )

    def _return_to_guild_scene(self):
        self.info_set('State', '协会狩猎回退，尝试退出副本')
        if self.scene_id != 12000:
            self.screenshot('guild_hunt/recovery_error')
        confirm = {
            'en': 'confirm_en',
            'jp': 'confirm_jp',
            'zht': 'confirm_zht',
        }.get(self.get_game_language(), 'confirm')
        claim_monthly_pass_task = self.get_task_by_class(ClaimMonthlyPassTask)

        while True:
            self._require_packet_capture()
            if self.next_frame() is None:
                self.log_warning('Unable to capture the game window while recovering; retrying')
                self.sleep(1)
                continue

            menu_icon_white_percentage = self.calculate_color_percentage(
                {'r': (255, 255), 'g': (255, 255), 'b': (255, 255)},
                self.get_box_by_name('menu_icon'),
            )
            if 0.5 < menu_icon_white_percentage < 1.0 and self.scene_id == 12000:
                break
            if self.find_one('loading'):
                self.sleep(1)
                continue

            handled = False
            needs_confirmation = False

            if claim_monthly_pass_task.handle_monthly_card():
                handled = True

            elif box := self.find_one(['escape', 'leave_dungeon', 'dungeon_timeout']):
                self.click(box)
                handled = True
                needs_confirmation = True

            elif self._is_in_guild_hunt():
                self.send_key(self.get_custom_key('Exit Dungeon'))
                handled = True
                needs_confirmation = True

            elif self.find_one('single_confirm'):
                self.click(0.5, 0.74)
                handled = True

            elif self.find_one('anchor_login'):
                self.click(0.5, 0.83)
                handled = True

            elif self.find_one('anchor_select_chara'):
                self.click(0.86, 0.88)
                handled = True

            elif self.find_one(confirm):
                self.click(0.37, 0.74)
                handled = True

            elif (self.calculate_color_percentage(
                    {'r': (250, 255), 'g': (250, 255), 'b': (250, 255)},
                    self.get_box_by_name('close')) > 0.15):
                self.send_key('esc')
                handled = True
                needs_confirmation = True

            if needs_confirmation and (box := self.wait_feature(confirm, time_out=1)):
                self.click(box)

            if not handled:
                self.send_key('esc')

            self.sleep(1)

        self._reset_hunt_state()

    def _handle_packet_combat(self):
        self._require_packet_capture()
        if self.scene_id in (None, 12000):
            self._boss_rear_target = None
            return
        entities = self.nearby_entities
        teammates = {
            entity_uuid for entity_uuid, entity in entities.items()
            if entity_uuid != self.player_uuid
            and entity.get('entity_type') == 10
            and entity.get('is_teammate', False)
        }
        in_combat = self.in_combat or any(
            entities[entity_uuid].get('in_combat', False)
            for entity_uuid in teammates
        )
        if not in_combat:
            self._boss_rear_target = None
            return
        self.info['Teammate Count'] = len(teammates)
        if self._combat_teammates - entities.keys():
            self.info_set('State', '队友已离开场景，尝试退出协会狩猎')
            self._return_to_guild_scene()
            return
        self._combat_teammates.update(teammates)
        if self.is_dead or self.actor_state in self._MOVE_BLOCKED_ACTOR_STATES:
            self._boss_rear_target = None
            return
        current = self.position
        if current is None:
            self._boss_rear_target = None
            return
        current_x, current_z = self._xz(current)
        monsters = {
            entity_uuid: entity for entity_uuid, entity in entities.items()
            if entity.get('entity_type') == 1
            and not entity.get('is_dead', False)
            and entity.get('current_hp') != 0
            and entity.get('position') is not None
        }
        if not monsters:
            self._boss_rear_target = None
            return
        target_uuid = min(monsters, key=lambda entity_uuid: math.dist(
            (current_x, current_z), self._xz(monsters[entity_uuid]['position']),
        ))
        target = monsters[target_uuid]
        target_x, target_z = self._xz(target['position'])
        delta = target_x - current_x, target_z - current_z
        distance = math.hypot(*delta)
        if distance == 0:
            self._boss_rear_target = None
            return
        self.detect_camera_direction()
        if not self._camera_direction_detected:
            return
        relative = self._relative_target_angle(delta)
        if abs(relative) > 60:
            if not self.look_at(target['position']):
                return
            relative = self._relative_target_angle(delta)
        rear_waypoint = self._boss_rear_waypoint(target_uuid, target, current, distance)
        if rear_waypoint is not None:
            relative = self._relative_target_angle((
                rear_waypoint[0] - current_x, rear_waypoint[1] - current_z,
            ))
            keys = self._MOVE_KEYS[round(relative / 45.0) % len(self._MOVE_KEYS)]
            self._move_briefly(keys, 0.2)
        elif self.config.get('Approach Boss', True) and distance > self.config.get('Boss Approach Distance (m)', 9):
            keys = self._MOVE_KEYS[round(relative / 45.0) % len(self._MOVE_KEYS)]
            self._move_briefly(keys, 0.2)

    def _boss_rear_waypoint(self, target_uuid, target, current, distance):
        facing = target.get('facing')
        if not self.config.get('Move Behind Boss', False) or facing is None:
            self._boss_rear_target = None
            return None
        current_x, current_z = self._xz(current)
        target_x, target_z = self._xz(target['position'])
        bearing = math.degrees(math.atan2(current_x - target_x, current_z - target_z))
        if self._boss_rear_target is None or self._boss_rear_target[0] != target_uuid:
            self._boss_rear_target = None
            if abs(self._angle_delta(bearing, facing)) > 60:
                return None
            self._boss_rear_target = target_uuid, distance

        radius = self._boss_rear_target[1]
        if self.config.get('Approach Boss', True):
            radius = min(radius, self.config.get('Boss Approach Distance (m)', 9))
        rear_heading = facing + 180
        rear_radians = math.radians(rear_heading)
        rear_point = (
            target_x + radius * math.sin(rear_radians),
            target_z + radius * math.cos(rear_radians),
        )
        if math.dist((current_x, current_z), rear_point) <= 1:
            self._boss_rear_target = None
            return None

        # 每次最多沿圆周绕行 45 度，避免直接穿过首领中心。
        turn = self._angle_delta(rear_heading, bearing)
        waypoint_heading = math.radians(bearing + max(-45, min(45, turn)))
        return (
            target_x + radius * math.sin(waypoint_heading),
            target_z + radius * math.cos(waypoint_heading),
        )

    def _move_briefly(self, keys, duration):
        try:
            for key in keys:
                self.send_key_down(key)
            self.sleep(duration)
        finally:
            for key in reversed(keys):
                self.send_key_up(key)
