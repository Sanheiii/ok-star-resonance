import re

from src.tasks.SRTriggerTask import SRTriggerTask

class AimPurchaseButtonTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Aim Purchase"
        self.description = "Auto-disable after run"
        self.trigger_count = 0

    def run(self):
        if box:=self._find_purchase():
            target = box.center()
            self.move(target[0], target[1])
            self.disable()
        return

    def _find_purchase(self):
        language = self.get_game_language()
        if language == 'zhs' or language == 'zht':
            return self.find_one("buy", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95))
        elif language == 'jp':
            return self.find_one("buy_jp", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95))
        else:
            return self.find_one("buy_en", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95))