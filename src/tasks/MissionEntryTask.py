import time
from src.tasks.SRTriggerTask import SRTriggerTask


class MissionEntryTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto-Confirm Mission Entry"
        self.description = "Automatically clicks the confirmation button when a mission or dungeon entry prompt appears."
        self.trigger_interval = 0.2

    def run(self):
        if self.find_one('box_msg_confirm_mission', box=self.box_of_screen(0.40, 0.77, 0.60, 0.81)):
            self.click(0.9,0.91)