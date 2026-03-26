from mahjong_utils.models.tile import parse_tiles
from mahjong_utils.shanten import shanten

from ok import BaseTask

class MahjongTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '麻将'
        self.description = ''

        # 记录已打出的牌
        self.discarded_tiles = []
    def run(self):
        self.discarded_tiles.clear()
        while True:
            self.next_frame()
            self.run_game()
            # 检测到对局结束的下一步则重置状态
            # self.discarded_tiles.clear()
            # 自动坐桌子及点击准备

    def run_game(self):
        # 检测到自摸或荣和，则点击它
        if box:=self.find_one(['maj_tsumo', 'maj_ron']): # 设定box
            self.click(box)
            self.info_incr('和牌次数')
            self.sleep(3)
            return
        # 检测到摸牌区有牌，进入出牌方法
        if self.find_one('maj_tile', box=self.box_of_screen(0.828, 0.87, 0.875, 1.00), threshold=0.95):
            self.discard_tile()
            self.sleep(1)
            return
        # 检测到跳过按钮，上面已优先处理和牌，立直，剩下的都跳过
        if box:=self.find_one('maj_skip'): # 设定box
            self.click(box)
            self.sleep(1)
            return

    def discard_tile(self):
        tiles = self.get_tiles()
        tiles_str = "".join(tile.name.removeprefix('maj_') for tile in tiles)
        if not len(tiles) == 14:
            # 手牌检测出错了，跳过本轮检测
            self.log_error(f'手牌检测错误，当前检出手牌：{tiles_str}')
            self.sleep(0.5)
            self.next_frame()
            return

        # 手牌传入mahjong_utils
        self.info['当前手牌'] = tiles_str
        result = shanten(parse_tiles(tiles_str))

        best_discard:str| None = None
        min_shanten = float('inf')
        max_advance = -1
        # 遍历切牌选择
        for tile_name, info in result.discard_to_advance.items():
            current_shanten = info.shanten
            current_advance = info.advance_num
            is_tenpai = (current_shanten == 0)
            will_furiten = False

            for adv_tile in info.advance:
                adv_str = str(adv_tile)
                discard_count = self.discarded_tiles.count(adv_str)
                if discard_count > 0:
                    # 存在已打出的牌，减去打出的次数
                    current_advance -= discard_count
                    if not is_tenpai:
                        # 如果没听牌，则加重惩罚减少振听概率
                        current_advance -= discard_count
                    else:
                        will_furiten = True

            # 如果已听牌且打出这张牌将会振听，则降低权重
            if is_tenpai and will_furiten:
                current_advance /= 4

            # 选择最低向听数下最大进张数
            if current_shanten < min_shanten:
                min_shanten = current_shanten
                max_advance = current_advance
                best_discard = str(tile_name)
            elif current_shanten == min_shanten:
                if current_advance > max_advance:
                    max_advance = current_advance
                    best_discard = str(tile_name)

        if not best_discard:
            self.log_error(f'没有算出要出什么牌，手牌：{tiles_str}')
            return

        # 可以立直的话先点立直再出牌
        if box:= self.find_one('maj_riichi'): # 设定box
            self.click(box)
            self.sleep(0.5)

        # 双击要出的牌
        if box:= self.find_one('maj_' + best_discard, box=self.box_of_screen(0.193, 0.87, 0.875, 1.00), threshold=0.95):
            self.click(box)
            self.sleep(0.01)
            self.click(box)
            self.info['出牌'] = best_discard
            self.discarded_tiles.append(best_discard)
        else:
            self.log_error('出牌时没有找到' + best_discard)

    def get_tiles(self):
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

        for _ in range(4):
            draw = self.find_one(tiles_features, box=self.box_of_screen(0.828, 0.87, 0.875, 1.00), threshold=0.95)
            if draw:
                tiles.append(draw)
                break
            self.sleep(0.5)
            self.next_frame()

        for hand_box in hand_boxes_list:
            for _ in range(4):
                hand = self.find_one(tiles_features, box=hand_box, threshold=0.95)
                if hand:
                    tiles.append(hand)
                    tiles_features = tiles_features[tiles_features.index(hand.name):]
                    break
                self.sleep(0.5)
                self.next_frame()

        return tiles