from ok import BaseTask


class SRTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_game_language(self):
        lang = self.get_global_config('Game Settings').get('Game Language')
        if lang == '简体中文':
            return 'zhs'
        elif lang == '繁體中文':
            return 'zht'
        elif lang == '日本語':
            return 'jp'
        else:
            return 'en'