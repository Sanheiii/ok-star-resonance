from ok import BaseTask

from src.tasks.AutoPartyTask import AutoPartyTask
from src.tasks.AutoReviveTask import AutoReviveTask
from src.tasks.ClaimMonthlyPassTask import ClaimMonthlyPassTask
from src.tasks.MissionEntryTask import MissionEntryTask

class GuildHuntAssistTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Guild Hunt"
        self.description = "Auto-accept invites and assist in Guild Hunts."
        self.default_config.update({
            'I\'m Tank': False,
            'Opening Skill': 'Z',
            "Combat Wait Time": 5
        })
        self.executed = False

    def run(self):
        self.info['Entry Count'] = 0
        while True:
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
                self.executed = False

            # 检测到在副本内
            if not self.executed and self.find_one('guild_hunt_title',box=self.box_of_screen(0.02, 0.21, 0.06, 0.24), threshold=0.6):
                # Entry Count增加
                self.info['Entry Count'] += 1
                if self.config.get('I\'m Tank'):
                    # 是T
                    self.sleep(0.5)
                    self.send_key('e')
                    self.sleep(1)
                    self.send_key(self.config.get('Opening Skill'))
                    self.sleep(0.5)
                    self.send_key('h')
                else:
                    # 不是T
                    wait_time = self.config.get("Combat Wait Time", 5)
                    self.sleep(wait_time)
                    self.send_key_down('w')
                    self.sleep(2)
                    self.send_key_up('w')
                    self.sleep(0.5)
                    self.send_key(self.config.get('Opening Skill'))
                    self.sleep(0.5)
                    self.send_key('h')
                self.executed = True

            # 点击下一步
            if box:=self.find_one('next', box=self.box_of_screen(0.46, 0.86, 0.53, 0.92)):
                self.click(box)
                self.executed = False
            # 点击离开
            if box:=self.find_one('exit', box=self.box_of_screen(0.88, 0.91, 0.94, 0.97)):
                self.click(box)
                self.sleep(1)
                self.executed = False

            self.next_frame()
            # 处理自动入队和自动复活
            self.run_task_by_class(AutoPartyTask)
            self.run_task_by_class(AutoReviveTask)
            self.run_task_by_class(MissionEntryTask)
            # 如果触发任务中勾了自动领取月卡则检查月卡
            claim_monthly_pass_task = self.get_task_by_class(ClaimMonthlyPassTask)
            if claim_monthly_pass_task.enabled:
                claim_monthly_pass_task.run()