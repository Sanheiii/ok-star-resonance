import time
from src.tasks.SRTriggerTask import SRTriggerTask


class AutoSkillTask(SRTriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Skill Spammer"
        self.description = "Auto-cast skills sequentially."

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
        self.current_index = 0

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
        self.key_map.reverse()

    def run(self):
        now = time.time()
        interval = self.config.get('Spam Interval (s)')

        active_actions = []
        if self.config.get('Enable Basic Attack'):
            active_actions.append(('click', None))

        for config_key, key_char in self.key_map:
            if self.config.get(config_key):
                active_actions.append(('key', key_char))

        if not active_actions:
            return

        if self.current_index == 0:
            if now - self.last_action_time < interval:
                return

        action_type, action_value = active_actions[self.current_index]

        if action_type == 'click':
            self.click(0.5, 0.5)
        elif action_type == 'key':
            self.send_key(action_value)

        self.current_index += 1

        if self.current_index >= len(active_actions):
            self.current_index = 0
            self.last_action_time = time.time()