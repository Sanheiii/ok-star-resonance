import time
import datetime
import re
import threading

from ok import og
from pypushdeer import PushDeer

from src.tasks.SRTriggerTask import SRTriggerTask

class FishingTask(SRTriggerTask):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Fish"
        self.description = "Auto fish after interaction"
        
        self.default_config.update({
            'Always Rapid Click': False,
            'Switch Pole Key': 'm',
            'Fishing Interruption Notice': False,
            'PushDeer Server': 'Put your server url here if not using official server',
            'PushDeer ApiKey': 'Get from your PushDeer app'
        })
        
        self.trigger_count = 0

        # "溜鱼"小游戏的状态变量
        self.pos = 0
        self.last_update_time = None
        self.key_a_pressed = False
        self.key_d_pressed = False
        self.fish_pos_from_game = 0

        self.last_start_time = None
        self.last_reeling_time = None
        self.last_continue_time = None
        self.last_switch_time = None
        self.pushdeer = None
        self.start_message_sent = False
        self.interrupted_message_sent = False

        # 用于异步查找水花
        self._splash_finder_thread = None
        self._fish_pos_lock = threading.Lock()

        self.regex_map = {
            'zhs': {
                'pole': re.compile('添加鱼竿'),
                'continue_fishing': re.compile('继续钓鱼'),
                'use': re.compile('使用'),
            },
            'zht': {
                'pole': re.compile('添加魚竿'),
                'continue_fishing': re.compile('續[钓釣]魚'),
                'use': re.compile('使用'),
            },
            'en': {
                'pole': re.compile('pole'),
                'continue_fishing': re.compile('Continue fishing'),
                'use': re.compile('Use'),
            }
        }

        self.run_count = 0
        self.yolo_count = 0
        self.last_stat_time = time.time()
        self.stat_lock = threading.Lock()

    def _splash_finder_worker(self, frame):
        """
        异步查找水花的任务。
        """
        splash_box = self.find_splash(frame)
        if splash_box:
            with self._fish_pos_lock:
                self.fish_pos_from_game = splash_box[0].center()[0] / (self.width / 2) - 1 + 0.04

    def run(self):
        """
        钓鱼任务的主执行循环。
        根据当前的游戏状态调用对应的处理函数。
        """
        # self._print_stats()

        if self._handle_minigame():
            return
        if self._handle_interruption_notice():
            return
        if self._handle_start_and_pole_change():
            return
        if self._handle_hook_fish():
            return
        if self._handle_continue_fishing():
            return

    def _handle_start_and_pole_change(self) -> bool:
        """检查初始的钓鱼界面，以便抛竿或更换损坏的鱼竿。"""
        now = time.time()
        if self.last_start_time is not None and now - self.last_start_time <= 3:
            return False
        if self._find_fishing_level():
            self.sleep(0.5)
            # 检查鱼竿是否损坏
            if self.ocr(0.90, 0.92, 0.96, 0.96, match=self.get_regex('pole')):
                self.log_info('更换鱼竿', notify=False)
                self.send_key(self.config.get('Switch Pole Key'))
                use_boxes = self.wait_ocr(box=None, match=self.get_regex('use'), log=False, threshold=0.8, time_out=15)
                if use_boxes:
                    self.log_info('点击使用鱼竿', notify=False)
                    center = use_boxes[0].center()
                    self.click(center[0] / self.width, center[1] / self.height)
                else:
                    self.log_info('没有鱼竿了', notify=True)
                    self.screenshot()
                    raise Exception("没有鱼竿了,需要实现买鱼竿")
            else:
                self.log_info('抛竿', notify=False)
                self.click(0.5, 0.5)
                self.last_start_time = now
            return True
        return False

    def _handle_hook_fish(self) -> bool:
        """检查鱼上钩的提示，并点击开始收线。"""
        now = time.time()
        if self.last_reeling_time is not None and now - self.last_reeling_time <= 3:
            return False
        if self.find_one("hint_fishing_click", threshold=0.5):
            self.log_info('鱼上钩了', notify=False)
            self.my_mouse_down(0.5, 0.5)
            self.last_update_time = time.time()
            self.pos = 0
            self.last_reeling_time = now
            return True
        return False

    def _handle_continue_fishing(self) -> bool:
        # 每秒最多点击一次继续钓鱼
        now = time.time()
        if self.last_continue_time is not None and now - self.last_continue_time <= 1:
            return False
        if self._match_continue_fishing():
            self.log_info('点击继续钓鱼', notify=False)
            self.click(0.82, 0.90)
            self.last_continue_time = now
            return True
        return False

    def _handle_minigame(self) -> bool:
        """管理收线和溜鱼"""
        # 如果“鱼线张力”文本可见，则需要收线。
        if self.find_one("box_fishing_icon", box=self.box_of_screen(0.33, 0.80, 0.37, 0.87)):
            if self.config.get('Always Rapid Click') or self.find_one("box_stop_pull", box=self.box_of_screen(0.50, 0.75, 0.70, 0.92), threshold=0.5):
                now = time.time()
                if self.last_switch_time is None or now - self.last_switch_time >= 0.05:
                    self.my_mouse_switch(0.5, 0.5)
                    self.last_switch_time = now
            else:
                self.my_mouse_down(0.5, 0.5)
            # 获取鱼的实际位置
            if self._splash_finder_thread is None or not self._splash_finder_thread.is_alive():
                self._splash_finder_thread = threading.Thread(target=self._splash_finder_worker, args=(self.frame,))
                self._splash_finder_thread.start()
            fish_pos_for_minigame = 0
            with self._fish_pos_lock:
                fish_pos_for_minigame = self.fish_pos_from_game
            self._play_the_fish(fish_pos_for_minigame)
            return True
        elif self.last_update_time:
            # 如果小游戏未激活，确保松开鼠标和按键。
            self._reset_minigame_state()
            return True
        return False

    def _handle_interruption_notice(self) -> bool:
        server = self.config.get('PushDeer Server')
        key = self.config.get('PushDeer ApiKey')

        if not self.config.get('Fishing Interruption Notice'):
            return False

        regex = re.compile(
            r'^(https?|ftp)://'  # 协议 http, https, ftp
            r'([A-Z0-9_]([A-Z0-9-_]{0,61}[A-Z0-9_])?\.)+[A-Z]{2,6}\.?'  # 域名
            r'|'  # 或者
            r'localhost'  # localhost
            r'|'  # 或者
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'  # IP 地址
            r'(:\d+)?'  # 可选的端口号
            r'(/?|[/?]\S+)$', re.IGNORECASE)  # 可选的路径和查询参数

        if self.pushdeer is None:
            if regex.fullmatch(server) is not None and 'PDU' in key:
                self.pushdeer = PushDeer(server = server, pushkey= key)
            elif 'PDU' in key:
                self.pushdeer = PushDeer(pushkey= key)

        if self.pushdeer:
            now = time.time()
            if self.start_message_sent == False and self.last_start_time is not None and self.last_continue_time is None:
                self.pushdeer.send_text('开始钓鱼')
                self.start_message_sent = True
                self.interrupted_message_sent = False
                return True
            elif self.interrupted_message_sent == False and self.last_start_time is not None and now - self.last_start_time > 300:
                self.pushdeer.send_text('钓鱼被打断')
                self.last_continue_time = None
                self.last_start_time = None
                self.interrupted_message_sent = True
                self.start_message_sent = False
                return True
            else:
                return False
        else:
            raise Exception('未设置正确的PushDeer参数')


    def _play_the_fish(self, fish_pos: float):
        delta_time = self._update_time()

        normalized_fish_pos = min(max(fish_pos / 0.7, -1.3), 1.3)

        self._update_buoy_position(delta_time)
        self._update_key_presses(normalized_fish_pos)

    def _update_time(self) -> float:
        """计算并返回自上次更新以来的时间差（delta_time）。"""
        current_time = time.time()
        if self.last_update_time is None:
            self.last_update_time = current_time
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time
        return delta_time

    def _update_key_presses(self, normalized_fish_pos: float):
        """根据鱼的位置决定按下或释放哪个按键。"""
        if abs(self.pos - normalized_fish_pos) < 0.06:
            return
        if normalized_fish_pos < self.pos:
            # 鱼在竿左边，竿在屏幕右边松开D键
            if self.pos > 0 and self.key_d_pressed:
                self.send_key_up('d')
                self.key_d_pressed = False
            # 鱼在竿左边，竿在屏幕左边按下A键
            if self.pos <= 0 and not self.key_a_pressed:
                self.send_key_down('a')
                self.key_a_pressed = True
        else: 
            # 鱼在竿右边，竿在屏幕左边松开A键
            if self.pos < 0 and self.key_a_pressed:
                self.send_key_up('a')
                self.key_a_pressed = False
            # 鱼在竿右边，竿在屏幕右边按下D键
            if self.pos >= 0 and not self.key_d_pressed:
                self.send_key_down('d')
                self.key_d_pressed = True

    def _update_buoy_position(self, delta_time: float):
        """更新鱼竿的位置。"""
        # 未按任何键时，向中心点漂移
        if not self.key_a_pressed and not self.key_d_pressed:
            if self.pos > 0: 
                self.pos -= 1.0 * delta_time
                if self.pos < 0: self.pos = 0
            else : 
                self.pos += 1.0 * delta_time
                if self.pos > 0: self.pos = 0
        
        # 当按下 'A' 键且 pos < 0 时，向 -1 移动
        if self.key_a_pressed and self.pos <= 0:
            self.pos -= 0.5 * delta_time
            
        # 当按下 'D' 键且 pos > 0 时，向 1 移动
        if self.key_d_pressed and self.pos >= 0:
            self.pos += 0.5 * delta_time
            
        # 将位置限制在 [-1, 1] 的范围内
        self.pos = min(max(self.pos, -1.0), 1.0)
    
    def _reset_minigame_state(self):
        """在拉鱼结束时重置溜鱼状态。"""
        self.log_info('重置溜鱼', notify=False)
        self.my_mouse_up()
        if self.key_a_pressed:
            self.send_key_up('a')
            self.key_a_pressed = False
        if self.key_d_pressed:
            self.send_key_up('d')
            self.key_d_pressed = False
        self.last_update_time = None
        self.fish_pos_from_game = 0

    def find_splash(self, frame, threshold=0.5):
        ret = og.my_app.yolo_detect(frame, threshold=threshold, label=0)

        with self.stat_lock:
            self.yolo_count += 1

        return ret

    def _find_fishing_level(self):
        if self.get_game_language() == 'zhs' or self.get_game_language() == 'zht':
            return self.find_one("box_fishing_level", box=self.box_of_screen(0.56, 0.91, 0.60, 0.96))
        else:
            return self.find_one("box_fishing_level_eng", box=self.box_of_screen(0.56, 0.91, 0.60, 0.96))

    def _match_continue_fishing(self):
        lang = self.get_game_language()
        if lang == 'zhs' or lang == 'zht':
            return self.ocr(0.79, 0.88, 0.87, 0.93, match=self.get_regex('continue_fishing'))
        else:
            return self.ocr(0.76, 0.88, 0.90, 0.93, match=self.get_regex('continue_fishing'))

    def on_enabled(self) -> None:
        self.clean_pushdeer_related_resources()

    def clean_pushdeer_related_resources(self):
        self.last_start_time = None
        self.last_continue_time = None
        self.start_message_sent = False
        self.interrupted_message_sent = False
        self.pushdeer = None
        self.log_info('real function executed')

    def _print_stats(self):
        now = time.time()
        with self.stat_lock:
            self.run_count += 1
            elapsed = now - self.last_stat_time
            if elapsed >= 1.0:
                run_rate = self.run_count / elapsed
                yolo_rate = self.yolo_count / elapsed
                self.log_info(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 每秒运行次数={run_rate:.2f}, 水花识别次数={yolo_rate:.2f}")
                self.run_count = 0
                self.yolo_count = 0
                self.last_stat_time = now