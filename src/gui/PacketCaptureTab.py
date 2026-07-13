import math
import threading
import time
from collections import Counter, deque

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, PrimaryPushButton, PushButton

from ok import Config, og
from ok.gui.widget.CustomTab import CustomTab
from src.packet_capture import NpcapCapture, list_devices
from src.packet_capture.parser import GamePacketParser


class PacketCaptureTab(CustomTab):
    def __init__(self):
        super().__init__()
        self._devices = []
        self._capture = None
        self._capture_thread = None
        self._stop_requested = False
        self._capture_error = None
        self._parser = GamePacketParser()
        self._config = Config("packet_capture", {"device_name": ""})
        self._refreshing_devices = False
        self._speed_samples = deque()
        self._last_speed_sample_time = 0.0
        og.packet_capture_tool = self

        controls = QWidget(self.view)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.device_combo = ComboBox(controls)
        self.refresh_button = PushButton(FluentIcon.SYNC, og.app.tr("Refresh adapters"), controls)
        self.capture_button = PrimaryPushButton(og.app.tr("Start capture"), controls)
        controls_layout.addWidget(BodyLabel(og.app.tr("Network adapter"), controls))
        controls_layout.addWidget(self.device_combo, 1)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.capture_button)
        self.add_widget(controls)

        state = QWidget(self.view)
        state_layout = QVBoxLayout(state)
        state_layout.setContentsMargins(0, 12, 0, 0)
        self.status_label = BodyLabel(og.app.tr("Capture has not started"), state)
        self.position_label = BodyLabel(og.app.tr("Position: Unknown"), state)
        self.facing_label = BodyLabel(og.app.tr("Facing: Unknown"), state)
        self.speed_label = BodyLabel(og.app.tr("Speed: Unknown"), state)
        self.copy_button = PushButton(FluentIcon.COPY, og.app.tr("Copy position"), state)
        self.copy_button.setEnabled(False)
        state_layout.addWidget(self.status_label)
        state_layout.addWidget(self.position_label)
        state_layout.addWidget(self.facing_label)
        state_layout.addWidget(self.speed_label)
        state_layout.addWidget(self.copy_button)
        state_layout.addStretch(1)
        self.add_widget(state, 1)

        self.refresh_button.clicked.connect(self._refresh_devices)
        self.device_combo.currentIndexChanged.connect(self._save_selected_device)
        self.capture_button.clicked.connect(self._toggle_capture)
        self.copy_button.clicked.connect(self._copy_position)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_transform)
        self._timer.start(200)
        self._speed_timer = QTimer(self)
        self._speed_timer.timeout.connect(self._refresh_speed)
        self._speed_timer.start(1000)
        QTimer.singleShot(0, self._refresh_devices)

    @property
    def name(self):
        return og.app.tr("Packet Capture")

    @property
    def icon(self):
        return FluentIcon.DEVELOPER_TOOLS

    @property
    def is_capturing(self):
        return bool(self._capture_thread and self._capture_thread.is_alive() and not self._stop_requested)

    def _refresh_devices(self):
        try:
            self._refreshing_devices = True
            self._devices = list_devices()
            self.device_combo.clear()
            self.device_combo.addItems(self._device_labels(self._devices))
            saved_name = self._config.get("device_name")
            saved_index = next((i for i, device in enumerate(self._devices) if device.name == saved_name), -1)
            if saved_index >= 0:
                self.device_combo.setCurrentIndex(saved_index)
            self.status_label.setText(og.app.tr("Select an adapter and start capture"))
        except Exception as exc:
            self._devices = []
            self.device_combo.clear()
            self.status_label.setText(str(exc))
        finally:
            self._refreshing_devices = False

    @staticmethod
    def _device_labels(devices):
        """Return unique labels because ComboBox resolves clicks by displayed text."""
        display_names = [(device.display_name or device.name).strip() for device in devices]
        duplicate_counts = Counter(display_names)
        labels = []
        used_labels = set()
        for device, display_name in zip(devices, display_names):
            label = f"{display_name} ({device.name})" if duplicate_counts[display_name] > 1 else display_name
            unique_label = label
            suffix = 2
            while unique_label in used_labels:
                unique_label = f"{label} #{suffix}"
                suffix += 1
            used_labels.add(unique_label)
            labels.append(unique_label)
        return labels

    def _save_selected_device(self, index):
        if not self._refreshing_devices and 0 <= index < len(self._devices):
            self._config["device_name"] = self._devices[index].name

    def _toggle_capture(self):
        if self.capture_button.text() == og.app.tr("Stop capture"):
            self._stop_capture()
            return
        index = self.device_combo.currentIndex()
        if index < 0 or index >= len(self._devices):
            self.status_label.setText(og.app.tr("Select a network adapter first"))
            return
        self.device_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.capture_button.setText(og.app.tr("Stop capture"))
        self.status_label.setText(og.app.tr("Capturing"))
        self._stop_requested = False
        self._capture_error = None
        self._capture_thread = threading.Thread(
            target=self._capture_loop, args=(self._devices[index].name,), daemon=True, name="NpcapCapture"
        )
        self._capture_thread.start()

    def _capture_loop(self, device_name):
        try:
            self._capture = NpcapCapture(device_name)
            if self._stop_requested:
                self._capture.stop()
            self._parser.set_datalink(self._capture.datalink)
            self._capture.run(self._on_packet)
        except Exception as exc:
            self.logger.error(f"Npcap capture failed: {exc}")
            self._capture_error = str(exc)
        finally:
            if self._capture:
                self._capture.close()
            self._capture = None

    def _on_packet(self, packet):
        transform = self._parser.feed_packet(packet)
        if transform:
            position, facing = transform
            og.packet_capture_data.update_transform(position, facing)

    def _stop_capture(self):
        self._stop_requested = True
        if self._capture:
            self._capture.stop()
        self._set_idle(og.app.tr("Capture stopped"))

    def _capture_failed(self, message):
        self._set_idle(message)

    def _set_idle(self, message):
        self.capture_button.setText(og.app.tr("Start capture"))
        self.device_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.status_label.setText(message)

    def _refresh_transform(self):
        if (self._capture_thread and not self._capture_thread.is_alive()
                and self.capture_button.text() == og.app.tr("Stop capture")):
            self._set_idle(self._capture_error or og.app.tr("Capture stopped"))
        position, facing = og.packet_capture_data.get_transform()
        update_time = og.packet_capture_data.update_time
        if position is None:
            self.position_label.setText(og.app.tr("Position: Unknown"))
            self.copy_button.setEnabled(False)
        else:
            text = ", ".join(f"{value:.3f}" for value in position)
            self.position_label.setText(og.app.tr("Position: ") + text)
            self.copy_button.setEnabled(True)
        self.facing_label.setText(
            og.app.tr("Facing: Unknown") if facing is None
            else og.app.tr("Facing: ") + f"{facing:.2f}\N{DEGREE SIGN}"
        )
        self._record_speed_sample(position, update_time)

    def _record_speed_sample(self, position, update_time):
        if position is not None and update_time > self._last_speed_sample_time:
            self._speed_samples.append((update_time, position))
            self._last_speed_sample_time = update_time

    def _refresh_speed(self):
        if not self._speed_samples:
            self.speed_label.setText(og.app.tr("Speed: Unknown"))
            return

        now = time.time()
        cutoff = now - 1.0
        while len(self._speed_samples) > 1 and self._speed_samples[1][0] <= cutoff:
            self._speed_samples.popleft()

        samples = list(self._speed_samples)
        if samples[-1][0] <= cutoff:
            speed = 0.0
        else:
            if samples[0][0] < cutoff:
                before_time, before_position = samples[0]
                after_time, after_position = samples[1]
                ratio = (cutoff - before_time) / (after_time - before_time)
                cutoff_position = tuple(
                    before + (after - before) * ratio
                    for before, after in zip(before_position, after_position)
                )
                samples[0] = (cutoff, cutoff_position)
            samples.append((now, samples[-1][1]))
            distance = sum(
                math.hypot(current[1][0] - previous[1][0], current[1][2] - previous[1][2])
                for previous, current in zip(samples, samples[1:])
            )
            elapsed = max(now - samples[0][0], 0.001)
            speed = distance / elapsed
        self.speed_label.setText(og.app.tr("Speed: ") + f"{speed:.2f} u/s")

    def _copy_position(self):
        position, _ = og.packet_capture_data.get_transform()
        if position is not None:
            QApplication.clipboard().setText(", ".join(f"{value:.3f}" for value in position))

    def closeEvent(self, event):
        self._stop_capture()
        super().closeEvent(event)
