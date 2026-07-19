import re
import time

from src.tasks.SRTriggerTask import SRTriggerTask

class ClaimMonthlyPassTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto-claim Monthly Card"
        self.description = "Automatically claims the monthly card when it interface pops up"
        self.trigger_count = 0
        self.trigger_interval = 60
        self.regex_map = {
            'zhs': {
                'close': re.compile('点击空白处关闭'),
            },
            'zht': {
                'close': re.compile('點擊空白處關閉'),
            },
            'en': {
                'close': re.compile('Click anywhere to close'),
            },
            'jp': {
                'close': re.compile('空白をクリックして閉じる'),
            }
        }

    def run(self):
        self.handle_monthly_card()

    def handle_monthly_card(self):
        if box:=self.ocr(0.40, 0.94, 0.60, 1, match=self.get_regex('close')):
            self.click_box(box)
            return True
        return False