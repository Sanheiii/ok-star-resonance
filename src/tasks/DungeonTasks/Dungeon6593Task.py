from src.tasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon6593Task(DungeonTaskBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Dungeon6593"
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False

    def run(self):
        if not super().run():
            return
        # 开本仪器
        self.investigate()
        # 还没写路线

        self.sleep(1)
        pass
