import time
from src.tasks.SRTriggerTask import SRTriggerTask


class AutoPartyTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Party Auto-Acceptor"
        self.description = "Automates the acceptance party requests and invitations."
        self.trigger_interval = 0.2

    def run(self):
        if self.find_one('box_party_accept', box=self.box_of_screen(0.95, 0.20, 1, 0.27)):
            if self.find_one('box_event_icon', box=self.box_of_screen(0.72, 0.20, 0.79, 0.27)):
                self.send_key(';')
            else:
                self.send_key('\'')
        pass
