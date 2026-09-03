import os
import threading
import time
import mido
import numpy as np
import win32con
import win32file

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QVBoxLayout, QWidget
from numpy import ndarray
from ok.task.exceptions import TaskDisabledException
from qfluentwidgets import MessageBoxBase, SubtitleLabel, CheckBox, SmoothScrollArea, FluentIcon

from ok import BaseTask, og
from ok.gui.common.design_system import control_width
from ok.gui.tasks.LabelAndDropDown import LabelAndDropDown
from ok.util.collection import find_index_in_list
from src.gui.MidiVisualizerDialog import MidiVisualizerDialog

FILE_LIST_DIRECTORY = 0x0001


class TrackSelectionDialog(MessageBoxBase):
    def __init__(self, tracks, selected_indices, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(og.app.tr("Track Selection"), self)
        self.viewLayout.addWidget(self.titleLabel)
        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_widget.setStyleSheet("QWidget { background: transparent; }")

        self.checkboxes = []
        for i, track in enumerate(tracks):
            track_name = og.app.tr("Track {}").format(i)
            for msg in track:
                if msg.type == 'track_name':
                    track_name = og.app.tr("Track {}: {}").format(i, msg.name)
                    break
            cb = CheckBox(track_name)
            # 如果之前没有选过，则默认全选
            cb.setChecked(selected_indices is None or i in selected_indices)
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append((i, cb))
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)
        self.viewLayout.addWidget(self.scroll_area)
        self.yesButton.setText(og.app.tr("OK"))
        self.cancelButton.setText(og.app.tr("Cancel"))
        self.widget.setMinimumSize(350, 450)

    def get_selected_tracks(self):
        return [i for i, cb in self.checkboxes if cb.isChecked()]

class MidiPlayerTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "MIDI Player"
        self.description = "Plays MIDI files using in-game instruments."
        self.group_name = 'Band'
        self.group_icon = FluentIcon.MUSIC
        self.midi_list = None

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

        self.midi_dir = './midi/'
        if not os.path.exists(self.midi_dir):
            os.makedirs(self.midi_dir)

        self.default_config.update({'MIDI File': ''})
        self.default_config.update({'Mute Pedal': False})
        self.default_config.update({'Ensemble Mode': False})
        self.default_config.update({'Delay (ms)': 0})
        self.default_config.update({'_track_selections': {}})
        self.config_description['Ensemble Mode'] = 'Start this task before clicking the in-game Ensemble Start'
        self.load_config()
        self.refresh_midi_list()

        self.config_type['Tracks'] = {'type': "button", 'buttons': [
            {'icon': FluentIcon.MENU, 'text': og.app.tr('Select'), 'callback': self.open_track_selector},
        ]}
        self.config_type['MIDI Folder'] = {'type': "button", 'buttons': [
            {'icon': FluentIcon.FOLDER, 'text': og.app.tr('Locate'), 'callback': lambda: os.startfile(os.path.abspath(self.midi_dir))},
            {'icon': FluentIcon.SYNC, 'text': og.app.tr('Reload'), 'callback': self.reload_options},
        ]}
        self.config_type['Visualization'] = {'type': "button", 'buttons': [
            {'icon': FluentIcon.MUSIC, 'text': og.app.tr('Visualize'), 'callback': self.open_visualizer},
        ]}

        # 启动后台守护线程监听文件夹变动
        # self.monitor_thread = threading.Thread(target=self._monitor_directory, daemon=True)
        # self.monitor_thread.start()

    def open_track_selector(self):
        midi_file_name = self.config.get('MIDI File')
        if not midi_file_name or midi_file_name == 'No MIDI files found.':
            if hasattr(self, 'log_error'):
                self.log_error(og.app.tr("Please select a valid MIDI file first."))
            return

        file_path = os.path.join(self.midi_dir, midi_file_name)
        if not os.path.exists(file_path):
            return

        try:
            mid = mido.MidiFile(file_path)
        except Exception as e:
            if hasattr(self, 'log_error'):
                self.log_error(og.app.tr("Cannot read MIDI file: {}").format(e))
            return

        selections = self.config.get('_track_selections', {})
        current_selection = selections.get(midi_file_name)

        dialog = TrackSelectionDialog(mid.tracks, current_selection, parent=og.app.main_window)
        if dialog.exec():
            selected = dialog.get_selected_tracks()
            selections[midi_file_name] = selected
            self.config['_track_selections'] = selections
            self.log_info(og.app.tr("Selected {} tracks for {}.").format(len(selected), midi_file_name))
            self.config.save_file()

    def open_visualizer(self):
        """Open the MIDI visualizer dialog."""
        midi_file_name = self.config.get('MIDI File')
        if not midi_file_name or midi_file_name == 'No MIDI files found.':
            if hasattr(self, 'log_error'):
                self.log_error(og.app.tr("Please select a valid MIDI file first."))
            return

        file_path = os.path.join(self.midi_dir, midi_file_name)
        if not os.path.exists(file_path):
            if hasattr(self, 'log_error'):
                self.log_error(og.app.tr("MIDI file does not exist: {}").format(file_path))
            return

        # Get selected tracks
        selections = self.config.get('_track_selections', {})
        selected_tracks = set(selections.get(midi_file_name, []))

        # Open visualizer dialog with overall playable range (A0-C8)
        dialog = MidiVisualizerDialog(
            midi_path=file_path,
            playable_range=(self.OVERALL_MIN_PITCH, self.OVERALL_MAX_PITCH),
            selected_tracks=selected_tracks,
            parent=og.app.main_window
        )
        dialog.exec()

    def _monitor_directory(self):
        """在后台线程中阻塞监听文件夹"""
        h_dir = win32file.CreateFile(
            self.midi_dir,
            FILE_LIST_DIRECTORY,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None
        )

        while True:
            try:
                # 阻塞等待文件增删改名
                results = win32file.ReadDirectoryChangesW(
                    h_dir,
                    1024,
                    False,  # 不需要递归子文件夹
                    win32con.FILE_NOTIFY_CHANGE_FILE_NAME | win32con.FILE_NOTIFY_CHANGE_DIR_NAME,
                    None,
                    None
                )
                if results:
                    print(results)
                    # 稍微等待一下，防止系统还在进行 I/O 操作（比如大文件还没拷贝完）
                    time.sleep(0.5)
                    self.reload_options()
            except Exception as e:
                if hasattr(self, 'log_error'):
                    self.log_error(og.app.tr("Directory monitoring stopped: {}").format(e))
                break

    def refresh_midi_list(self):
        files = [f for f in os.listdir(self.midi_dir) if f.lower().endswith(('.mid', '.midi'))]
        self.midi_list = files if files else ['No MIDI files found.']

        if 'MIDI File' in self.config_type:
            self.config_type['MIDI File']['options'] = self.midi_list
        else:
            self.config_type['MIDI File'] = {'type': "drop_down", 'options': self.midi_list}
        self.default_config.update({'MIDI File': self.midi_list[0]})
        # 如果之前的默认Midi文件已被删除则重置选择
        current_midi = self.config.get('MIDI File')
        if current_midi is not None and current_midi not in self.midi_list:
            self.config.pop('MIDI File', None)

        # 如果某个MIDI文件已不存在，删除音轨选择中对应的记录
        selections = self.config.get('_track_selections', {})
        missing_files = [midi_name for midi_name in selections.keys() if midi_name not in files]
        if missing_files:
            for midi_name in missing_files:
                selections.pop(midi_name, None)
            self.config['_track_selections'] = selections
            self.config.save_file()

    def reload_options(self):
        self.refresh_midi_list()
        main_window = og.app.main_window
        tabs = [getattr(main_window, 'onetime_tab', None)]
        tabs.extend(getattr(main_window, 'grouped_task_tabs', []))

        for tab in filter(None, tabs):
            for widget in getattr(tab, 'card_widgets', []):
                if getattr(widget, 'task', None) is not self:
                    continue

                config_widget = getattr(widget, 'config_widget_by_key', {}).get('MIDI File')
                if isinstance(config_widget, LabelAndDropDown):
                    self._reload_midi_dropdown(config_widget)
                    widget.update_config()
                return

    def _reload_midi_dropdown(self, config_widget):
        """更新 MIDI 下拉框，不让 clear/addItems 的中间信号覆盖当前配置。"""
        options = self.config_type['MIDI File']['options']
        current_val = self.config.get('MIDI File')
        index = find_index_in_list(options, current_val, -1)
        if index == -1 and options:
            index = 0
            self.config['MIDI File'] = options[0]

        config_widget.config = self.config
        config_widget.tr_dict.clear()
        config_widget.tr_options.clear()
        for option in options:
            translated = og.app.tr(option)
            config_widget.tr_options.append(translated)
            config_widget.tr_dict[translated] = option

        blocker = QSignalBlocker(config_widget.combo_box)
        try:
            config_widget.combo_box.clear()
            config_widget.combo_box.addItems(config_widget.tr_options)
            config_widget.combo_box.setCurrentIndex(index)
        finally:
            del blocker

        fm = QFontMetrics(config_widget.combo_box.font())
        max_width = max((fm.horizontalAdvance(option) for option in config_widget.tr_options), default=0)
        config_widget.combo_box.setFixedWidth(control_width(max_width + 50))

    def tap_key(self, key):
        """模拟短按按键"""
        self.send_key_down(key)
        time.sleep(0.01)
        self.send_key_up(key)
        time.sleep(0.01)

    # Playable range constants (A0=21 to C8=108)
    OVERALL_MIN_PITCH = 21  # A0
    OVERALL_MAX_PITCH = 108  # C8
    # Keyboard range (3 octaves: C3-B5 = 48-83)
    KEYBOARD_MIN = 48  # C3
    KEYBOARD_MAX = 83  # B5

    def is_in_range(self, note, page, octave):
        """Check if a note is playable in the specified (page, octave) state.

        The keyboard plays 3 octaves (Cx to Bx+2) at a time.
        Page shifts by 3 octaves, octave modifier shifts by 1 octave.
        Overall playable range is A0 (21) to C8 (108).
        """
        # First check overall playable bounds
        if note < self.OVERALL_MIN_PITCH or note > self.OVERALL_MAX_PITCH:
            return False

        # Calculate base note for this state
        base_note = note - (page - 1) * 36 - octave * 12
        return self.KEYBOARD_MIN <= base_note <= self.KEYBOARD_MAX

    def is_note_playable(self, note):
        """Check if a note is within overall playable range (A0-C8)."""
        return self.OVERALL_MIN_PITCH <= note <= self.OVERALL_MAX_PITCH

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
            for j in range(start_idx + 1, len(events)):
                evt_time, evt_msg = events[j]
                if evt_msg.type == 'note_on' and evt_msg.velocity > 0:
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
            print(og.app.tr("Error: Invalid MIDI file"))
            return

        try:
            mid = mido.MidiFile(file_path)
            self.log_info(og.app.tr("Starting playback: {}").format(midi_file_name))

            # 过滤未选中的音轨
            selections = self.config.get('_track_selections', {})
            current_selection = selections.get(midi_file_name)
            if current_selection is not None:
                for i, track in enumerate(mid.tracks):
                    if i not in current_selection:
                        # 清空未选音轨中的发声及控制消息
                        track[:] = [msg for msg in track if msg.is_meta]

            # 提取音符和控制信息
            raw_events = []
            abs_time = 0.0
            allowed_types = {'note_on', 'note_off'}
            # 如果忽视延音踏板则不关注control_change
            if not self.config['Mute Pedal']:
                allowed_types.add('control_change')

            for msg in mid:
                abs_time += msg.time
                if msg.type in allowed_types:
                    raw_events.append({'time': abs_time, 'msg': msg})

            # 预处理音符防止连续的音符只按下一次
            # 记录每个 pitch 上一次 note_off 事件的引用
            last_off_event = {}
            # 记录每个 pitch 上一次 note_on 的时间，防止 note_off 提前过头导致持续时间变为负数
            last_on_time = {}

            MIN_GAP = 0.033

            for evt in raw_events:
                msg = evt['msg']
                if msg.type == 'note_on' and msg.velocity > 0:
                    pitch = msg.note
                    # 检查是否存在前一个相同的音符
                    if pitch in last_off_event:
                        prev_off_evt = last_off_event[pitch]
                        gap = evt['time'] - prev_off_evt['time']

                        if gap < MIN_GAP:
                            # 将前一个 off 时间提前且至少保留 1ms 持续时间
                            new_off_time = max(last_on_time.get(pitch, 0) + 0.001, evt['time'] - MIN_GAP)
                            prev_off_evt['time'] = new_off_time

                    last_on_time[pitch] = evt['time']

                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # 记录下这个 off 事件，供下一个相同的 note_on 参考
                    last_off_event[msg.note] = evt

            # 3. 重新排序事件
            raw_events.sort(key=lambda x: x['time'])
            events = [(e['time'], e['msg']) for e in raw_events]

            # 初始化游戏内部钢琴状态
            self.current_page = 1  # 默认在中间页面: 1 (对应 C3~B5)
            self.current_octave = 0  # 默认无修饰键: 0 (正常), 1 (Shift), -1 (Ctrl)
            playing_notes = {}  # 记录当前按下的键，方便正确释放
            is_pedal_on = False  # 记录当前踏板状态

            # 合奏模式需要等待节拍器
            if self.config['Ensemble Mode']:
                while True:
                    self.next_frame()
                    frame: ndarray = self.frame
                    if frame is None:
                        continue
                    # 计算并转换坐标为整数
                    x1, x2 = int(self.width_of_screen(0.02)), int(self.width_of_screen(0.07))
                    y1, y2 = int(self.height_of_screen(0.22)), int(self.height_of_screen(0.24))

                    # 截取目标区域
                    roi = frame[y1:y2, x1:x2]

                    target_color = [93, 93, 218]
                    if np.any(np.all(np.abs(roi - target_color) < 2, axis=-1)):
                        break

            # 如果设定了延迟先等一下
            delay = self.config['Delay (ms)']
            if delay > 0:
                self.sleep(delay/1000)

            start_time = time.time()

            for i, (msg_time, msg) in enumerate(events):
                if not self.running:
                    break

                # 暂停期间冻结 MIDI 时间轴，避免恢复后瞬间补播积压事件
                if self.paused:
                    for key in playing_notes.values():
                        self.send_key_up(key)
                    playing_notes.clear()
                    paused_at = time.time()
                    while self.running and self.paused:
                        time.sleep(0.05)
                    start_time += time.time() - paused_at
                    if not self.running:
                        break

                # 处理延音踏板 (Control Change 64)
                if msg.type == 'control_change' and msg.control == 64:
                    # MIDI 标准：value >= 64 为踩下，< 64 为松开
                    if msg.value >= 64 and not is_pedal_on:
                        self.tap_key('space')
                        is_pedal_on = True
                    elif msg.value < 64 and is_pedal_on:
                        self.tap_key('space')
                        is_pedal_on = False
                    continue # 踏板事件不涉及音域检查，直接跳到下一个

                is_note_on = msg.type == 'note_on' and msg.velocity > 0

                # 如果是弹下新音符，检查并切换音域
                if is_note_on:
                    if not self.is_in_range(msg.note, self.current_page, self.current_octave):
                        # 触发前瞻预测
                        best_state = self.get_best_state(events, i, msg.note)
                        if best_state:
                            self.switch_state(best_state[0], best_state[1])
                        else:
                            self.log_error(og.app.tr("Cannot play pitch: {}").format(msg.note))

                # 基于全局的绝对时间进行延迟等待
                # 把切换按键耗费的时间算进去，多退少补
                target_time = start_time + msg_time
                while self.running:
                    if self.paused:
                        for key in playing_notes.values():
                            self.send_key_up(key)
                        playing_notes.clear()
                        paused_at = time.time()
                        while self.running and self.paused:
                            time.sleep(0.05)
                        paused_duration = time.time() - paused_at
                        start_time += paused_duration
                        target_time += paused_duration
                        continue

                    remaining = target_time - time.time()
                    if remaining <= 0:
                        break
                    time.sleep(min(remaining, 0.05))

                if not self.running:
                    break

                # 实际演奏
                if is_note_on:
                    key = self.get_key(msg.note, self.current_page, self.current_octave)
                    if key:
                        self.send_key_down(key)
                        playing_notes[msg.note] = key
                elif msg.type in ('note_off', 'note_on'): # note_off 或 velocity == 0
                    key = playing_notes.get(msg.note)
                    if key:
                        self.send_key_up(key)
                        del playing_notes[msg.note]

            # 演奏结束后清理，清理修饰键状态，松开空格
            if is_pedal_on:
                self.tap_key('space')
            self.switch_state(1, 0)

        except Exception as e:
            if type(e) is TaskDisabledException:
                return
            if locals().get('is_pedal_on'):
                self.tap_key('space')
            self.switch_state(1, 0)
            self.log_error(og.app.tr("Playback error: {}").format(e), notify=True)
