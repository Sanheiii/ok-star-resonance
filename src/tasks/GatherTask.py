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
            'Use Focus': False,
            'Gathering Key': 'f',
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
            pattern1 = re.compile('探集')
            pattern2_str = '專注'
        else:
            pattern1 = re.compile('Focused|Normal')
            pattern2_str = 'Focused'

        boxes = self.ocr(0.75, 0.5, 0.84, 0.61, match=pattern1)

        if not boxes:
            self.run_interval = 1
            return

        sorted_boxes = sorted(boxes, key=lambda b: b.center()[1])

        for i, box in enumerate(sorted_boxes):
            self.sleep(0.5)
            if self.config.get('Use Focus') and re.search(pattern2_str, box.name):
                self.send_key(self.config.get('Gathering Key'))
                self.run_interval = 5.5
                break
            elif not self.config.get('Use Focus') and not re.search(pattern2_str, box.name):
                self.send_key(self.config.get('Gathering Key'))
                self.run_interval = 5.5
                break
            else:
                self.scroll(self.width_of_screen(0.5), self.height_of_screen(0.5), 120)
        return