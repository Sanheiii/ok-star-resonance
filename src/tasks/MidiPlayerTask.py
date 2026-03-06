import os
import time
import mido

from ok import BaseTask


class MidiPlayerTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "MIDI Player"
        self.description = "Plays MIDI files using in-game instruments."

        self.pitch_to_key = {
            # C3 - B3: 48-59
            48: 'z', 49: '1', 50: 'x', 51: '2', 52: 'c', 53: 'v',
            54: '3', 55: 'b', 56: '4', 57: 'n', 58: '5', 59: 'm',

            # C4 - B4: 60-71
            60: 'a', 61: '6', 62: 's', 63: '7', 64: 'd', 65: 'f',
            66: '8', 67: 'g', 68: '9', 69: 'h', 70: '0', 71: 'j',

            # C5 - B5: 72-83
            72: 'q', 73: 'i', 74: 'w', 75: 'o', 76: 'e', 77: "r",
            78: 'p', 79: 't', 80: '[', 81: 'y', 82: ']', 83: 'u',
        }

        midi_dir = './midi/'
        if not os.path.exists(midi_dir):
            os.makedirs(midi_dir)

        self.midi_list = [f for f in os.listdir(midi_dir) if f.lower().endswith(('.mid', '.midi'))]
        if not self.midi_list:
            self.midi_list = ['No MIDI files found.']

        self.default_config.update({'MIDI File': self.midi_list[0]})
        self.config_description.update({'MIDI File': 'Drop .mid files into ./midi/ and restart.'})
        self.config_type['MIDI File'] = {'type': "drop_down", 'options': self.midi_list}

        self.load_config()

    def tap_key(self, key):
        """模拟短按按键"""
        self.send_key_down(key)
        time.sleep(0.01)
        self.send_key_up(key)
        time.sleep(0.01)

    def is_in_range(self, note, page, octave):
        """判断音符是否在指定的 (页面, 八度) 状态内"""
        # page: 0 (C0~B2), 1 (C3~B5), 2 (C6~B8)
        # octave: -1 (降八度/Ctrl), 0 (正常), 1 (升八度/Shift)
        base_note = note - (page - 1) * 36 - octave * 12
        return 48 <= base_note <= 83

    def get_key(self, note, page, octave):
        """根据当前状态计算目标键位"""
        base_note = note - (page - 1) * 36 - octave * 12
        return self.pitch_to_key.get(base_note)

    def switch_state(self, target_page, target_octave):
        """切换到目标页面和目标八度"""
        # 切换页面 (使用 < 和 >)
        while self.current_page < target_page:
            self.tap_key('.')
            self.current_page += 1
        while self.current_page > target_page:
            self.tap_key(',')
            self.current_page -= 1

        # 切换八度 (使用 Shift 和 Ctrl)
        if self.current_octave != target_octave:
            if target_octave == 1:
                self.tap_key('shift')
            elif target_octave == -1:
                self.tap_key('ctrl')
            elif target_octave == 0:
                # 目标是正常音域，根据当前状态取消修饰键
                if self.current_octave == 1:
                    self.tap_key('shift')
                elif self.current_octave == -1:
                    self.tap_key('ctrl')
            self.current_octave = target_octave

    def get_best_state(self, events, start_idx, note):
        """向前推导，寻找能正常演奏最久的下一个音域状态"""
        candidates = []
        for p in (0, 1, 2):
            for o in (-1, 0, 1):
                if self.is_in_range(note, p, o):
                    candidates.append((p, o))

        if not candidates:
            return None

        best_state = candidates[0]
        max_forward_notes = -1

        for p, o in candidates:
            forward_notes = 0
            checked = 0
            for j in range(start_idx + 1, len(events)):
                evt_time, evt_msg = events[j]
                if evt_msg.type == 'note_on' and evt_msg.velocity > 0:
                    checked += 1
                    if self.is_in_range(evt_msg.note, p, o):
                        forward_notes += 1
                    else:
                        break

            if forward_notes > max_forward_notes:
                max_forward_notes = forward_notes
                best_state = (p, o)

        return best_state

    def run(self):
        midi_file_name = self.config.get('MIDI File')
        file_path = os.path.join('./midi/', midi_file_name)

        if not os.path.exists(file_path) or midi_file_name == 'No MIDI files found.':
            print("错误: 无效的 MIDI 文件")
            return

        try:
            mid = mido.MidiFile(file_path)
            self.log_info(f"开始播放: {midi_file_name}")

            # 预处理：将所有音符提取并赋予全局绝对时间
            events = []
            abs_time = 0.0
            for msg in mid:
                abs_time += msg.time
                if msg.type in ('note_on', 'note_off'):
                    events.append((abs_time, msg))

            # 初始化游戏内部钢琴状态
            self.current_page = 1  # 默认在中间页面: 1 (对应 C3~B5)
            self.current_octave = 0  # 默认无修饰键: 0 (正常), 1 (Shift), -1 (Ctrl)
            playing_notes = {}  # 记录当前按下的键，方便正确释放

            start_time = time.time()

            for i, (msg_time, msg) in enumerate(events):
                if not self.running:
                    break

                is_note_on = msg.type == 'note_on' and msg.velocity > 0

                # 如果是弹下新音符，检查并切换音域
                if is_note_on:
                    if not self.is_in_range(msg.note, self.current_page, self.current_octave):
                        # 触发前瞻预测
                        best_state = self.get_best_state(events, i, msg.note)
                        if best_state:
                            self.switch_state(best_state[0], best_state[1])
                        else:
                            self.log_error(f"无法演奏音高: {msg.note}")

                # 基于全局的绝对时间进行延迟等待
                # 把切换按键耗费的时间算进去，多退少补
                target_time = start_time + msg_time
                now = time.time()
                if target_time > now:
                    time.sleep(target_time - now)

                # 实际演奏
                if is_note_on:
                    key = self.get_key(msg.note, self.current_page, self.current_octave)
                    if key:
                        self.send_key_down(key)
                        playing_notes[msg.note] = key
                else:
                    # note_off 或 velocity == 0
                    key = playing_notes.get(msg.note)
                    if key:
                        self.send_key_up(key)
                        del playing_notes[msg.note]

            # 演奏结束后，清理修饰键状态恢复到正常 (页面1，八度0)
            self.switch_state(1, 0)

        except Exception as e:
            self.log_error(f"播放出错: {e}", notify=True)