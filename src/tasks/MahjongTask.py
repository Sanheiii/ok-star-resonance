from ok import BaseTask

class MahjongTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '自动麻将'
        self.default_config.update({
            '只做断幺': False,
        })

    def run(self):
        tiles_features: list[str] = [
            'maj_1m', 'maj_2m', 'maj_3m', 'maj_4m', 'maj_5m', 'maj_0m', 'maj_6m', 'maj_7m', 'maj_8m', 'maj_9m',
            'maj_1p', 'maj_2p', 'maj_3p', 'maj_4p', 'maj_5p', 'maj_0p', 'maj_6p', 'maj_7p', 'maj_8p', 'maj_9p',
            'maj_1s', 'maj_2s', 'maj_3s', 'maj_4s', 'maj_5s', 'maj_0s', 'maj_6s', 'maj_7s', 'maj_8s', 'maj_9s',
            'maj_1z', 'maj_2z', 'maj_3z', 'maj_4z', 'maj_5z', 'maj_6z', 'maj_7z',
        ]
        hand_boxes_list = [
            self.box_of_screen(0.193, 0.87, 0.239, 1.0),
            self.box_of_screen(0.239, 0.87, 0.287, 1.0),
            self.box_of_screen(0.287, 0.87, 0.333, 1.0),
            self.box_of_screen(0.333, 0.87, 0.380, 1.0),
            self.box_of_screen(0.380, 0.87, 0.427, 1.0),
            self.box_of_screen(0.427, 0.87, 0.474, 1.0),
            self.box_of_screen(0.474, 0.87, 0.521, 1.0),
            self.box_of_screen(0.521, 0.87, 0.567, 1.0),
            self.box_of_screen(0.567, 0.87, 0.615, 1.0),
            self.box_of_screen(0.615, 0.87, 0.661, 1.0),
            self.box_of_screen(0.661, 0.87, 0.708, 1.0),
            self.box_of_screen(0.708, 0.87, 0.755, 1.0),
            self.box_of_screen(0.755, 0.87, 0.802, 1.0)
        ]
        tiles = []
        draw = self.find_one(tiles_features, box=self.box_of_screen(0.828, 0.87, 0.875, 1.00), threshold=0.95)
        #没摸到牌不处理
        if not draw:
            return
        tiles.append(draw.name.removeprefix('maj_'))
        for hand_box in hand_boxes_list:
            hand = self.find_one(tiles_features, box=hand_box, threshold=0.95)
            if not hand:
                break
            tiles.append(hand.name.removeprefix('maj_'))
            tiles_features = tiles_features[tiles_features.index(hand.name):]
        pass