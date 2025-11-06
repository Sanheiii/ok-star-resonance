import re
import time

from src.tasks.SRTriggerTask import SRTriggerTask

class PickPassTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动领取月卡"
        self.description = "弹出月卡界面后自动领取月卡"
        self.trigger_count = 0
        self.last_check_time = None
        self.regex_map = {
            'zhs': {
                'close': re.compile('点击空白处关闭'),
            },
            'zht': {
                'close': re.compile('點擊空白處關閉'),
            }
        }

    def run(self):
        now = time.time()
        if self.last_check_time is None or now - self.last_check_time > 60:
            self.last_check_time = time.time()
            if box:=self.ocr(0.44, 0.94, 0.56, 1, match=self.get_regex('close')):
                self.click_box(box)
        return