import re
import time

from src.tasks.SRTriggerTask import SRTriggerTask


class GatherTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Gather"
        self.description = "Auto-click when the button appears. Please adjust angle for clear text."
        self.trigger_count = 0

        self.default_config.update({
            'Use Focus': False
        })

        self.last_run_time = 0
        self.run_interval = 0

    def run(self):
        lang = self.get_game_language()

        if time.time() - self.last_run_time < self.run_interval:
            return

        self.run_interval = 0

        self.last_run_time = time.time()

        if lang == 'zhs':
            pattern1 = re.compile('采集')
            pattern2_str = '专注'
        elif lang == 'zht':
            pattern1 = re.compile('採集')
            pattern2_str = '專注'
        else:
            pattern1 = re.compile('Focused|Normal')
            pattern2_str = 'Focused'

        boxes = self.ocr(0.75, 0.5, 0.84, 0.68, match=pattern1)

        if not boxes:
            self.run_interval = 1
            return

        sorted_boxes = sorted(boxes, key=lambda b: b.center()[1])

        for i, box in enumerate(sorted_boxes):
            self.sleep(0.5)
            if ((self.config.get('Use Focus') and re.search(pattern2_str, box.name)) or (not self.config.get('Use Focus') and not re.search(pattern2_str, box.name))):
                self.send_key_down('alt_l')
                self.sleep(0.1)
                self.click(box)
                self.sleep(0.1)
                self.send_key_up('alt_l')
                self.run_interval = 5.5
                break
        return