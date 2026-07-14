from src.tasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class SeaRingedReefTask(DungeonTaskBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Sea-Ringed Reef - M1"
        self.difficulty = Difficulty.MASTER1

    def run(self):
        if not super().run():
            return
        # 开本仪器
        self.investigate((81.9,17))
        # 路线
        self.move_to_positions([(47,27),(36,40),(31,81),(-4,83),(-50,87),(-54,95),(-54,27)])