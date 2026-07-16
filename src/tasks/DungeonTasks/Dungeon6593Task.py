from src.tasks.DungeonTaskBase import DungeonTaskBase, Difficulty

class Dungeon6593Task(DungeonTaskBase):

    def __init__(self, *args, **kwargs):
        self.task_name = 'Dungeon 6593'
        self.task_name_zh = '镜中的审判 - 困难'
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False
        super().__init__(*args, **kwargs)

    def run(self):
        if not super().run():
            return
        # 开本仪器
        self.investigate(None)
        # 还没写路线

        self.sleep(1)
        pass
