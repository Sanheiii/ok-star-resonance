import cv2
import numpy as np
import ok

from src.tasks.SRTriggerTask import SRTriggerTask


class AutoReviveTask(SRTriggerTask):

    def is_colorful(self, box: ok.Box, min_saturation=50):
        roi = box.crop_frame(self.frame)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        s_channel = hsv[:, :, 1]
        avg_saturation = np.mean(s_channel)
        print(avg_saturation)
        return avg_saturation > min_saturation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Revive"
        self.description = "Automatically interacts with the revive prompt."
        self.trigger_interval = 0.2
        self.last_detected_box = None

        self.default_config.update({
            'Allow Respawn to Base': False,
            # 'Use Revive Bean': False,
        })

    def run(self):
        area = self.box_of_screen(0.81, 0.84, 0.94, 0.92)
        target_box = None
        if (box := self.find_one('box_revive', box=area)) and self.is_colorful(box):
            target_box = box
        elif self.config.get('Allow Respawn to Base') and (box := self.find_one('box_respawn', box=area)) and self.is_colorful(box):
            target_box = box
        elif self.config.get('Use Revive Bean') and (box := self.find_one('box_use_revive_bean', box=area)) and self.is_colorful(box):
            target_box = box

        if target_box:
            if  self.last_detected_box and target_box.center_distance(self.last_detected_box) < 0.05:
                self.click(target_box)
                self.last_detected_box = None
            else:
                self.last_detected_box = target_box
        else:
            self.last_detected_box = None

        if self.config.get('Use Revive Bean'):
            pass