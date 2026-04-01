from datetime import datetime, timedelta

from mahjong_utils.models.tile import parse_tiles
from mahjong_utils.shanten import shanten, regular_shanten

from ok import BaseTask

from src.tasks.ClaimMonthlyPassTask import ClaimMonthlyPassTask


class MahjongTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Mahjong'

        self.default_config.update({'Pure Tsumogiri': False})
        self.default_config.update({'Anti-Renchan': False})

        # 记录已打出的牌
        self.discarded_tiles = []
        # 记录上一次对局点确定的时间，防止过快开始卡副本
        self.last_confirm = datetime.min
        # 防止打牌失败重复打牌多次将牌添加到 discard_tiles
        self.allow_discard_record = True
    def run(self):
        self.discarded_tiles.clear()
        self.last_confirm = datetime.min
        self.info['Hora Count'] = 0
        while True:
            self.next_frame()
            self.run_game()
            if (box:=self.find_one('mahjong_match', box=self.box_of_screen(0.73, 0.5, 0.77, 0.68))) and not self.find_one('mahjong_matching'):
                if datetime.now() - self.last_confirm > timedelta(seconds=30):
                    self.send_key_down('lalt')
                    self.sleep(0.1)
                    self.click(box)
                    self.sleep(0.1)
                    self.send_key_up('lalt')
                    self.sleep(1)
            elif box:=self.find_one('accept'):
                self.click(box)
            # 自动点击下一步
            if box:=self.find_one('confirm', box=self.box_of_screen(0.46,0.89,0.54,0.95)):
                self.click(box)
                self.discarded_tiles.clear()
                self.last_confirm=datetime.now()
            if box := self.find_one('confirm', box=self.box_of_screen(0.86, 0.89, 0.93, 0.95)):
                self.click(box)

            # 如果触发任务中勾了自动领取月卡则检查月卡
            claim_monthly_pass_task = self.get_task_by_class(ClaimMonthlyPassTask)
            if claim_monthly_pass_task.enabled:
                claim_monthly_pass_task.run()


    def run_game(self):
        if skip_box:=self.find_one(['maj_skip'], box=self.box_of_screen(0.48,0.75,0.89,0.85)):
            self.sleep(0.2)
            self.next_frame()
            if self.find_one(['maj_riichi'], box=self.box_of_screen(0.48, 0.75, 0.89, 0.85)):
                pass
            elif box := self.find_one(['maj_tsumo', 'maj_ron'], box=self.box_of_screen(0.48, 0.75, 0.89, 0.85)):
                self.click(box)
                self.info_incr('Hora Count')
                self.sleep(2)
            else:
                self.click(skip_box)
                self.sleep(1)
        # 检测到摸牌区有牌并且手牌区第一和最后一张都有牌，进入出牌方法
        if (self.find_one('maj_tile', box=self.box_of_screen(0.81, 0.87, 0.875, 1.00), threshold=0.95)
                and self.find_one('maj_tile', box=self.box_of_screen(0.193, 0.87, 0.239, 1.0), threshold=0.95)
                and self.find_one('maj_tile', box=self.box_of_screen(0.755, 0.87, 0.802, 1.0), threshold=0.95)):
            self.sleep(0.2)
            self.next_frame()
            self.info['test'] = self.calculate_color_percentage({'r':(140,158), 'g': (208, 226), 'b': (213, 231)}, 'maj_auto_tsumogiri')
            # 开了摸切模式
            if self.config['Pure Tsumogiri']:
                if self.calculate_color_percentage({'r':(140,158), 'g': (208, 226), 'b': (213, 231)}, 'maj_auto_tsumogiri') < 0.05:
                     self.click_box('maj_auto_tsumogiri')
            # 开了防止连庄并且检测到玩家是庄家
            elif self.config['Anti-Renchan'] and self.find_one('maj_east'):
                if self.calculate_color_percentage({'r':(140,158), 'g': (208, 226), 'b': (213, 231)}, 'maj_auto_tsumogiri') < 0.05:
                     self.click_box('maj_auto_tsumogiri')
            else:
                self.discard_tile()
            self.sleep(1)
        else:
            self.allow_discard_record = True
            return

    def discard_tile(self):
        tiles = self.get_tiles()
        tiles_str = "".join(tile.name.removeprefix('maj_') for tile in tiles)
        if not len(tiles) == 14:
            # 手牌检测出错了，跳过本轮检测
            self.log_info(f'检出手牌：{tiles_str}')
            self.log_error(f'没有检测到全部手牌，如果无法正常打牌，请将游戏设置为1920*1080，FSR3效果挡')
            self.sleep(0.5)
            self.next_frame()
            return

        # 手牌传入mahjong_utils
        self.info['Tiles'] = tiles_str
        t = parse_tiles(tiles_str)
        regular = regular_shanten(t)
        result = shanten(t)
        if regular.shanten - result.shanten < 2:
            result = regular

        self.info['Shanten'] = result.shanten

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
                if current_advance >= max_advance:
                    max_advance = current_advance
                    best_discard = str(tile_name)

        if not best_discard:
            self.log_error(f'没有算出要出什么牌，手牌：{tiles_str}')
            return

        # 可以立直的话先点立直再出牌
        if box:= self.find_one('maj_riichi', box=self.box_of_screen(0.48,0.75,0.89,0.85)):
            self.sleep(0.3)
            self.click(box)
            self.sleep(0.3)

        # 双击要出的牌
        tiles=['maj_' + best_discard]
        if best_discard in {'5m','5s','5p'}:
            red_tile = 'maj_' + best_discard.replace('5', '0')
            tiles.append(red_tile)

        if box:= self.find_one(tiles, box=self.box_of_screen(0.193, 0.87, 0.875, 1.00), threshold=0.95):
            self.click(box)
            self.sleep(0.02)
            self.click(box)
            self.sleep(0.02)
            self.move_relative(0.5,0.5)
            self.info['Discard'] = best_discard
            if self.allow_discard_record:
                self.discarded_tiles.append(best_discard)
                self.allow_discard_record = False
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
            draw = self.find_one(tiles_features, box=self.box_of_screen(0.81, 0.87, 0.875, 1.00), threshold=0.95)
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

    def tsumogiri(self):
        if box:=self.find_one('maj_tile', box=self.box_of_screen(0.81, 0.87, 0.875, 1.00), threshold=0.95):
            self.click(box)
            self.sleep(0.02)
            self.click(box)
            self.sleep(0.02)
            self.move_relative(0.5,0.5)