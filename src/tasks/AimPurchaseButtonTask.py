from src.tasks.SRTriggerTask import SRTriggerTask

class AimPurchaseButtonTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Aim Purchase"
        self.description = "Auto-disable after run"
        self.trigger_count = 0

    def run(self):
        if box:=self._find_purchase():
            self._move_to_box(box)
            self._move_to_confirm()
            self.disable()
        return

    def _move_to_confirm(self):
        if box:=self.wait_until(self._find_confirm, time_out=1):
            self._move_to_box(box)

    def _move_to_box(self, box):
        target = box.center()
        self.move(target[0], target[1])

    def _find_purchase(self):
        language = self.get_game_language()
        if language == 'zhs' or language == 'zht':
            return self.find_one("purchase", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95))
        elif language == 'jp':
            return self.find_one("purchase_jp", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95))
        else:
            return self.find_one("purchase_en", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95))

    def _find_confirm(self):
        language = self.get_game_language()
        if language == 'zhs':
            return self.find_one("confirm")
        elif language == 'zht':
            return self.find_one("confirm_zht", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
        elif language == 'jp':
            return self.find_one("confirm_jp", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
        else:
            return self.find_one("confirm_en", box=self.box_of_screen(0.83, 0.89, 0.98, 0.94))
