import time
from src.tasks.SRTriggerTask import SRTriggerTask


class AutoSkillTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Skill Spammer"
        self.description = "Auto-cast skills at set intervals."

        # 初始化配置，用户可以在UI中进行勾选
        self.default_config.update({
            'Spam Interval (s)': 0.1,
            'Enable Basic Attack': True,
            'Enable Skill 1': True,
            'Enable Skill 2': True,
            'Enable Skill 3': True,
            'Enable Skill 4': True,
            'Enable Skill 5': True,
            'Enable Ult': True,
            'Enable Imagine Z': True,
            'Enable Imagine X': True
        })

        self.last_action_time = 0

        self.key_map = [
            ('Enable Skill 1', '1'),
            ('Enable Skill 2', '2'),
            ('Enable Skill 3', '3'),
            ('Enable Skill 4', '4'),
            ('Enable Skill 5', '5'),
            ('Enable Ult', 'r'),
            ('Enable Imagine Z', 'z'),
            ('Enable Imagine X', 'x'),
        ]

    def run(self):
        now = time.time()
        interval = self.config.get('Spam Interval (s)')

        if now - self.last_action_time >= interval:
            self._spam_all_skills()
            self.last_action_time = now

    def _spam_all_skills(self):
        if self.config.get('Enable Basic Attack'):
            self.click(0.5, 0.5)

        for config_key, key_char in self.key_map:
            if self.config.get(config_key):
                self.send_key(key_char)
                # self.sleep(0.01)