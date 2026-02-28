from ok import BaseTask

from src.tasks.AutoPartyTask import AutoPartyTask
from src.tasks.AutoReviveTask import AutoReviveTask
from src.tasks.ClaimMonthlyPassTask import ClaimMonthlyPassTask

class GuildHuntAssistTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Guild Hunt"
        self.description = "Auto-accept invites and assist in Guild Hunts."
        self.default_config.update({
            'I\'m Tank': False,
            "Combat Wait Time": 5
        })
        self.executed = False

    def run(self):
        self.info['Entry Count'] = 0
        while True:
            # 检测队友退出队伍自动退队
            if self.find_one('box_teammate_left', box=self.box_of_screen(0.46, 0.18, 0.63, 0.30)):
                self.send_key('i')
                if self.wait_click_feature('box_leave_party', box=self.box_of_screen(0.89, 0.88, 1, 0.95), raise_if_not_found=False):
                    self.sleep(1)
                    self.click(0.62,0.74)
                self.sleep(1)
                self.send_key('esc')
                self.sleep(3)

            # 确认进入副本
            if self.find_one('box_msg_confirm_mission', box=self.box_of_screen(0.40, 0.77, 0.60, 0.81)):
                # 刷新状态，允许进行操作
                self.click(0.9,0.91)
                self.executed = False

            # 检测到在副本内
            if not self.executed and self.find_one('box_guild_hunt_title', box=self.box_of_screen(0.02, 0.21, 0.06, 0.24)):
                # Entry Count增加
                self.info['Entry Count'] += 1
                if self.config.get('I\'m Tank'):
                    # 是T
                    self.send_key('e')
                    self.sleep(1)
                    self.send_key('z')
                    self.send_key('h')
                else:
                    # 不是T
                    wait_time = self.config.get("Combat Wait Time", 5)
                    self.sleep(wait_time)
                    self.send_key_down('w')
                    self.sleep(2)
                    self.send_key_up('w')
                    self.send_key('h')
                self.executed = True

            self.next_frame()
            # 处理自动入队和自动复活
            self.run_task_by_class(AutoPartyTask)
            self.run_task_by_class(AutoReviveTask)
            # 如果触发任务中勾了自动领取月卡则检查月卡
            claim_monthly_pass_task = self.get_task_by_class(ClaimMonthlyPassTask)
            if claim_monthly_pass_task.enabled:
                claim_monthly_pass_task.run()