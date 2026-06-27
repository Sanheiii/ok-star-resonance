import time
from src.tasks.SRTriggerTask import SRTriggerTask


class MissionEntryTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto-Confirm Mission Entry"
        self.description = "Automatically clicks the confirmation button when a mission or dungeon entry prompt appears."
        self.trigger_interval = 0.2

    def run(self):
        if self._find_msg() and (box:=self._find_confirm()):
            self.click(box)
        if box:=self._find_accept():
            self.click(box)
        return

    def _find_msg(self):
        language = self.get_game_language()
        if language == 'zhs':
            return self.find_one("msg_confirm_mission", box=self.box_of_screen(0.40, 0.80, 0.59, 0.84))
        elif language == 'zht':
            return self.find_one("msg_confirm_mission_zht")
        elif language == 'en':
            return self.find_one("msg_confirm_mission_en", box=self.box_of_screen(0.38, 0.77, 0.62, 0.82))
        else:
            return None

    def _find_confirm(self):
        language = self.get_game_language()
        if language == 'zhs':
            return self.find_one("confirm", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
        elif language == 'zht':
            return self.find_one("confirm_zht", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
        elif language == 'en':
            return self.find_one("confirm_en", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
        elif language == 'jp':
            return self.find_one("confirm_jp", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
        else:
            return None

    def _find_accept(self):
        language = self.get_game_language()
        if language == 'zhs':
            return self.find_one("accept")
        elif language == 'zht':
            return self.find_one("accept")
        elif language == 'en':
            return self.find_one("accept_en")
        elif language == 'jp':
            return self.find_one("accept_jp")
        else:
            return None