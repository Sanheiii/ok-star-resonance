import time
import heapq
import numpy as np
from numpy._typing import NDArray
from itertools import groupby
from ok import BaseTask, Box


class OtogeTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "音游考核"
        self.description = "自动打音游"
        self.default_config.update({})
        self.executed = False

        # 按键在屏幕横向位置的范围
        self.notes = {
            'z': [0.003, 0.046], '1': [0.039, 0.061], 'x': [0.051, 0.094], '2': [0.086, 0.107],
            'c': [0.097, 0.140], 'v': [0.147, 0.188], '3': [0.182, 0.203], 'b': [0.194, 0.236],
            '4': [0.230, 0.249], 'n': [0.243, 0.283], '5': [0.277, 0.298], 'm': [0.290, 0.329],

            'a': [0.338, 0.378], '6': [0.372, 0.392], 's': [0.386, 0.425], '7': [0.419, 0.440],
            'd': [0.433, 0.472], 'f': [0.480, 0.520], '8': [0.514, 0.535], 'g': [0.528, 0.567],
            '9': [0.561, 0.583], 'h': [0.575, 0.615], '0': [0.609, 0.630], 'j': [0.623, 0.663],

            'q': [0.670, 0.710], 'i': [0.704, 0.725], 'w': [0.718, 0.758], 'o': [0.752, 0.773],
            'e': [0.766, 0.806], 'r': [0.813, 0.853], 'p': [0.847, 0.869], 't': [0.861, 0.901],
            '[': [0.894, 0.915], 'y': [0.908, 0.948], ']': [0.942, 0.964], 'u': [0.956, 0.996],
        }
        self.height_threshold = 0.15
        self.diff_threshold = 3

    def run(self):
        self.info['status'] = '等待开始'
        while(True):
            self.next_frame()
            if self.find_one('timestamp_zero'):
                break
            self.sleep(0.016)

        self.info['status'] = '演奏中'
        # 截取检测区域并获取背景图作为参照
        roi = self.box_of_screen(0.237, 0.044, 0.954, 0.091)
        self.next_frame()
        bg: NDArray = roi.crop_frame(self.frame)

        roi_h, roi_w = bg.shape[:2]
        min_h_pixels = int(self.height_threshold * roi_h)
        h_window = max(1, int(roi_h * 0.15))

        # 预计算各按键的像素坐标范围，避免在循环里重复算
        key_pixel_ranges = {}
        for k, (x_start, x_end) in self.notes.items():
            key_pixel_ranges[k] = (int(x_start * roi_w), int(x_end * roi_w))

        current_key_state = {k: False for k in self.notes}
        pure_block_records = {k: None for k in self.notes}

        # 允许的抖动容差
        tolerance = max(2, int(roi_h * 0.2))
        event_queue = []

        while True:
            self.next_frame()
            current_frame: NDArray = roi.crop_frame(self.frame)

            # 帧差法检测动态物体
            diff = np.abs(current_frame.astype(np.int16) - bg.astype(np.int16))
            mask = np.mean(diff, axis=2) > self.diff_threshold
            current_time = time.time()

            for key, (x_start, x_end) in key_pixel_ranges.items():
                key_width = x_end - x_start
                key_region_mask = mask[:, x_start:x_end]

                # 检查每一行是否有足够的填充率（认为是有效 Note 像素）
                active_rows = np.sum(key_region_mask, axis=1) >= (key_width * 0.85)

                # 计算最大连续高度
                max_continuous_height = max(
                    (sum(1 for _ in g) for k, g in groupby(active_rows) if k),
                    default=0
                )

                is_condition_met = max_continuous_height >= min_h_pixels

                # 按下与松开，延时 3.35s 是根据音游流速推测的硬编码
                if is_condition_met and not current_key_state[key]:
                    heapq.heappush(event_queue, (current_time + 3.35, 'down', key))
                    current_key_state[key] = True
                elif not is_condition_met and current_key_state[key]:
                    heapq.heappush(event_queue, (current_time + 3.15, 'up', key))
                    current_key_state[key] = False

                # 处理连在一起没有间隙的 Note
                if current_key_state[key]:
                    key_frame = current_frame[:, x_start:x_end]
                    top_y = None
                    center_y_offset = h_window // 2
                    center_x_offset = key_width // 2

                    # 扫描纯色块寻找 Note 的顶端坐标
                    for y in range(roi_h - h_window + 1):
                        window = key_frame[y:y + h_window, :]
                        ref_color = window[center_y_offset, center_x_offset]

                        # 只要 90% 像素颜色一致就认为是纯色块
                        color_diffs = np.max(np.abs(window.astype(np.int16) - ref_color.astype(np.int16)), axis=2)
                        if np.sum(color_diffs == 0) >= 0.9 * h_window * key_width:
                            top_y = y
                            break

                    if top_y is not None:
                        recorded_y = pure_block_records[key]

                        if recorded_y is None:
                            # 第一次抓到Note头
                            pure_block_records[key] = top_y
                        elif top_y < recorded_y - tolerance:
                            # 如果出现了比追踪过的note头更靠上的，说明后面又跟了一个新 Note
                            if hasattr(self, 'log_debug'):
                                self.log_debug(f"[{key}] New note detected, resetting...")
                            heapq.heappush(event_queue, (current_time + 3.3, 'up', key))
                            heapq.heappush(event_queue, (current_time + 3.35, 'down', key))
                            pure_block_records[key] = top_y
                        else:
                            # 持续追踪已发现的note头
                            pure_block_records[key] = max(recorded_y, top_y)
                    else:
                        # 没扫到note头说明note脱离了检测区域，标记为一个极大值
                        pure_block_records[key] = 65535
                else:
                    pure_block_records[key] = None

            # 处理时间队列里的按键事件
            while event_queue and event_queue[0][0] <= time.time():
                exec_time, ev_type, key = heapq.heappop(event_queue)
                if ev_type == 'down':
                    self.send_key_down(key)
                elif ev_type == 'up':
                    self.send_key_up(key)

            if not self.find_one('keyboard'):
                self.info['status'] = '已完成'
                return