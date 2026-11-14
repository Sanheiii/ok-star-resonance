import math

from src.tasks.AutoPartyTask import AutoPartyTask
from src.tasks.AutoReviveTask import AutoReviveTask
from src.tasks.ClaimMonthlyPassTask import ClaimMonthlyPassTask
from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase
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
        })
        self.config_type['Combat Wait Time'] = {'min': 0}
        self._reset_hunt_state()

    def _reset_hunt_state(self):
        self.executed = False
        self._combat_teammates = set()
        self._combat_scene_id = None
        self.info['Teammate Count'] = 0

    def run(self):
        if self.config.get('Use Packet Capture', False):
            self._require_packet_capture()
        self._reset_hunt_state()
        self.info['Entry Count'] = 0
        while True:
            use_packet_capture = self.config.get('Use Packet Capture', False)
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
            if not self.executed and self.find_one('guild_hunt_title',box=self.box_of_screen(0.02, 0.21, 0.06, 0.24), threshold=0.6):
                # Entry Count增加
                self.info['Entry Count'] += 1
                if self.config.get('I\'m Tank'):
                    # 是T
                    self.sleep(0.5)
                    self.send_key('e')
                    self.sleep(1)
                    self._move_briefly(('a',), 0.5)
                    self.sleep(0.5)
                    self.send_key(self.config.get('Opening Skill'))
                    self.sleep(0.5)
                    self.send_key('h')
                else:
                    # 不是T
                    wait_time = self.config.get("Combat Wait Time", 5)
                    self.sleep(wait_time)
                    self._move_briefly(('w',), 2)
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

    def _return_to_guild_scene(self):
        DungeonTaskBase.return_to_initial_state(self, initial_scene_ids=(12000,))
        self._reset_hunt_state()

    def _handle_packet_combat(self):
        self._require_packet_capture()
        if self.scene_id in (None, 12000):
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
            return
        self.info['Teammate Count'] = len(teammates)
        if self._combat_teammates - entities.keys():
            self.info_set('State', '队友已离开场景，尝试退出协会狩猎')
            self._return_to_guild_scene()
            return
        self._combat_teammates.update(teammates)
        if self.is_dead or self.actor_state in self._MOVE_BLOCKED_ACTOR_STATES:
            return
        current = self.position
        if current is None:
            return
        current_x, current_z = self._xz(current)
        monsters = [
            entity for entity in entities.values()
            if entity.get('entity_type') == 1
            and not entity.get('is_dead', False)
            and entity.get('current_hp') != 0
            and entity.get('position') is not None
        ]
        if not monsters:
            return
        target = min(monsters, key=lambda entity: math.dist(
            (current_x, current_z), self._xz(entity['position']),
        ))
        target_x, target_z = self._xz(target['position'])
        delta = target_x - current_x, target_z - current_z
        distance = math.hypot(*delta)
        if distance == 0:
            return
        self.detect_camera_direction()
        if not self._camera_direction_detected:
            return
        relative = self._relative_target_angle(delta)
        if abs(relative) > 60:
            if not self.look_at(target['position']):
                return
            relative = self._relative_target_angle(delta)
        if distance > 15:
            keys = self._MOVE_KEYS[round(relative / 45.0) % len(self._MOVE_KEYS)]
            self._move_briefly(keys, 0.2)

    def _move_briefly(self, keys, duration):
        try:
            for key in keys:
                self.send_key_down(key)
            self.sleep(duration)
        finally:
            for key in reversed(keys):
                self.send_key_up(key)
