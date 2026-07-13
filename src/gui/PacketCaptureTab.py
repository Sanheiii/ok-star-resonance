import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, PrimaryPushButton, PushButton

from ok import og
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

        controls = QWidget(self.view)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.device_combo = ComboBox(controls)
        self.refresh_button = PushButton(FluentIcon.SYNC, self.tr("刷新网卡"), controls)
        self.capture_button = PrimaryPushButton(self.tr("开始抓包"), controls)
        controls_layout.addWidget(BodyLabel(self.tr("网卡"), controls))
        controls_layout.addWidget(self.device_combo, 1)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.capture_button)
        self.add_widget(controls)

        state = QWidget(self.view)
        state_layout = QVBoxLayout(state)
        state_layout.setContentsMargins(0, 12, 0, 0)
        self.status_label = BodyLabel(self.tr("未开始抓包"), state)
        self.position_label = QLabel(self.tr("位置：未知"), state)
        self.facing_label = QLabel(self.tr("面向：未知"), state)
        self.copy_button = PushButton(FluentIcon.COPY, self.tr("复制位置"), state)
        self.copy_button.setEnabled(False)
        state_layout.addWidget(self.status_label)
        state_layout.addWidget(self.position_label)
        state_layout.addWidget(self.facing_label)
        state_layout.addWidget(self.copy_button)
        state_layout.addStretch(1)
        self.add_widget(state, 1)

        self.refresh_button.clicked.connect(self._refresh_devices)
        self.capture_button.clicked.connect(self._toggle_capture)
        self.copy_button.clicked.connect(self._copy_position)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_transform)
        self._timer.start(200)
        QTimer.singleShot(0, self._refresh_devices)

    @property
    def name(self):
        return self.tr("抓包工具")

    @property
    def icon(self):
        return FluentIcon.DEVELOPER_TOOLS

    def _refresh_devices(self):
        try:
            self._devices = list_devices()
            self.device_combo.clear()
            self.device_combo.addItems([device.display_name for device in self._devices])
            self.status_label.setText(self.tr("请选择网卡并开始抓包"))
        except Exception as exc:
            self._devices = []
            self.device_combo.clear()
            self.status_label.setText(str(exc))

    def _toggle_capture(self):
        if self.capture_button.text() == self.tr("结束抓包"):
            self._stop_capture()
            return
        index = self.device_combo.currentIndex()
        if index < 0 or index >= len(self._devices):
            self.status_label.setText(self.tr("请先选择网卡"))
            return
        self.device_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.capture_button.setText(self.tr("结束抓包"))
        self.status_label.setText(self.tr("正在抓包"))
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
            og.my_app.update_player_transform(position, facing)

    def _stop_capture(self):
        self._stop_requested = True
        if self._capture:
            self._capture.stop()
        self._set_idle(self.tr("已结束抓包"))

    def _capture_failed(self, message):
        self._set_idle(message)

    def _set_idle(self, message):
        self.capture_button.setText(self.tr("开始抓包"))
        self.device_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.status_label.setText(message)

    def _refresh_transform(self):
        if (self._capture_thread and not self._capture_thread.is_alive()
                and self.capture_button.text() == self.tr("结束抓包")):
            self._set_idle(self._capture_error or self.tr("已结束抓包"))
        position, facing = og.my_app.get_player_transform()
        if position is None:
            self.position_label.setText(self.tr("位置：未知"))
            self.copy_button.setEnabled(False)
        else:
            text = ", ".join(f"{value:.3f}" for value in position)
            self.position_label.setText(self.tr("位置：") + text)
            self.copy_button.setEnabled(True)
        self.facing_label.setText(self.tr("面向：未知") if facing is None else self.tr("面向：") + f"{facing:.2f}°")

    def _copy_position(self):
        position, _ = og.my_app.get_player_transform()
        if position is not None:
            QApplication.clipboard().setText(", ".join(f"{value:.3f}" for value in position))

    def closeEvent(self, event):
        self._stop_capture()
        super().closeEvent(event)
