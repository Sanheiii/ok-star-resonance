import re

from src.tasks.SRTriggerTask import SRTriggerTask

class TargetBuyButtonTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动将鼠标指向交易行购买按钮"
        self.description = "运行后会自动关闭"
        self.trigger_count = 0

    def run(self):
        if box:=self.find_one("box_buy", box=self.box_of_screen(0.90, 0.90, 0.985, 0.95)):
            target = box.center()
            self.move(target[0], target[1])
            self.disable()
        return