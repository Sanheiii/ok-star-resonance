import math
import threading
from collections import Counter

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, PlainTextEdit, PrimaryPushButton, PushButton

from ok import Config, og
from ok.gui.widget.CustomTab import CustomTab
from src.packet_capture import NpcapCapture, list_devices
from src.packet_capture.parser import ENTITY_TYPE_NAMES, GamePacketParser


class PacketCaptureTab(CustomTab):
    def __init__(self):
        super().__init__()
        self._devices = []
        self._capture = None
        self._capture_thread = None
        self._stop_requested = False
        self._capture_error = None
        self._parser = GamePacketParser()
        self._metadata_revision = -1
        self._local_position_revision = -1
        self._combat_state_revision = -1
        self._config = Config("packet_capture", {"device_name": ""})
        self._refreshing_devices = False
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
        unknown = og.app.tr("Unknown")
        self.server_position_label = BodyLabel(
            og.app.tr("Server position: {position}").format(position=unknown), state
        )
        self.local_position_label = BodyLabel(
            og.app.tr("Local position: {position}").format(position=unknown), state
        )
        self.facing_label = BodyLabel(
            og.app.tr("Character facing: {facing}").format(facing=unknown), state
        )
        self.player_id_label = BodyLabel(
            og.app.tr("Character ID: {id}").format(id=unknown), state
        )
        self.scene_id_label = BodyLabel(
            og.app.tr("Scene ID: {id}").format(id=unknown), state
        )
        self.combat_state_label = BodyLabel(
            og.app.tr("Attribute 104: {value}").format(value=unknown), state
        )
        self.nearby_title = BodyLabel(og.app.tr("Nearby entities"), state)
        self.nearby_entities = PlainTextEdit(state)
        self.nearby_entities.setReadOnly(True)
        self.nearby_entities.setMinimumHeight(180)
        self.nearby_entities.setPlainText(og.app.tr("No nearby entities"))
        self.copy_button = PushButton(
            FluentIcon.COPY, og.app.tr("Copy local position XY"), state
        )
        self.copy_button.setEnabled(False)
        state_layout.addWidget(self.status_label)
        state_layout.addWidget(self.server_position_label)
        state_layout.addWidget(self.local_position_label)
        state_layout.addWidget(self.facing_label)
        state_layout.addWidget(self.player_id_label)
        state_layout.addWidget(self.scene_id_label)
        state_layout.addWidget(self.combat_state_label)
        state_layout.addWidget(self.copy_button)
        state_layout.addWidget(self.nearby_title)
        state_layout.addWidget(self.nearby_entities)
        state_layout.addStretch(1)
        self.add_widget(state, 1)

        self.refresh_button.clicked.connect(self._refresh_devices)
        self.device_combo.currentIndexChanged.connect(self._save_selected_device)
        self.capture_button.clicked.connect(self._toggle_capture)
        self.copy_button.clicked.connect(self._copy_position)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_transform)
        self._timer.start(200)
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
            og.packet_capture_data.update_server_transform(position, facing)
        if self._metadata_revision != self._parser.metadata_revision:
            og.packet_capture_data.update_world(*self._parser.world_state())
            self._metadata_revision = self._parser.metadata_revision
        if self._local_position_revision != self._parser.local_position_revision:
            if self._parser.local_position is not None:
                og.packet_capture_data.update_local_position(self._parser.local_position)
            self._local_position_revision = self._parser.local_position_revision
        if self._combat_state_revision != self._parser.combat_state_revision:
            if self._parser.combat_state is not None:
                og.packet_capture_data.update_combat_state(self._parser.combat_state)
            self._combat_state_revision = self._parser.combat_state_revision

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
        server_position, facing = og.packet_capture_data.get_server_transform()
        local_position = og.packet_capture_data.get_local_position()
        unknown = og.app.tr("Unknown")
        if server_position is None:
            server_position_text = unknown
        else:
            server_position_text = "XZ: {x}, {z}, Y: {y}".format(
                x=f"{server_position[0]:.3f}",
                z=f"{server_position[2]:.3f}",
                y=f"{server_position[1]:.3f}",
            )
        self.server_position_label.setText(
            og.app.tr("Server position: {position}").format(
                position=server_position_text
            )
        )
        self.copy_button.setEnabled(local_position is not None)
        self.facing_label.setText(
            og.app.tr("Character facing: {facing}").format(
                facing=unknown if facing is None
                else f"{facing:.2f}\N{DEGREE SIGN}"
            )
        )
        local_position_text = unknown if local_position is None else (
            "XZ: {x}, {z}, Y: {y}".format(
                x=f"{local_position[0]:.3f}",
                z=f"{local_position[2]:.3f}",
                y=f"{local_position[1]:.3f}",
            )
        )
        self.local_position_label.setText(
            og.app.tr("Local position: {position}").format(
                position=local_position_text
            )
        )
        self._refresh_world_state(server_position)

    def _refresh_world_state(self, player_position):
        scene_id, player_id, player_uuid, entities = og.packet_capture_data.get_world()
        self.player_id_label.setText(
            og.app.tr("Character ID: {id}").format(
                id=og.app.tr("Unknown") if player_id is None else player_id
            )
        )
        self.scene_id_label.setText(
            og.app.tr("Scene ID: {id}").format(
                id=og.app.tr("Unknown") if scene_id is None else scene_id
            )
        )
        combat_state = og.packet_capture_data.get_combat_state()
        self.combat_state_label.setText(
            og.app.tr("Attribute 104: {value}").format(
                value=og.app.tr("Unknown") if combat_state is None else combat_state
            )
        )
        rows = []
        if player_position is not None:
            for entity_id, entity in entities.items():
                entity_position = entity.get("position")
                if entity_id == player_uuid or entity_position is None:
                    continue
                distance = math.hypot(
                    entity_position[0] - player_position[0],
                    entity_position[2] - player_position[2],
                )
                entity_type = entity.get("entity_type", 0)
                type_name = ENTITY_TYPE_NAMES.get(entity_type, "Unknown")
                translated_type = og.app.tr(type_name)
                flags = []
                if entity.get("is_summoned"):
                    flags.append(og.app.tr("Summoned"))
                if entity.get("is_client_created"):
                    flags.append(og.app.tr("Client-created"))
                flag_text = f" [{', '.join(flags)}]" if flags else ""
                rows.append((distance, og.app.tr(
                    "Entity {id}: Type {type} ({type_id}){flags}, XZ ({x}, {z}), Y {y}, Distance {distance}"
                ).format(
                    id=entity_id,
                    type=translated_type,
                    type_id=entity_type,
                    flags=flag_text,
                    x=f"{entity_position[0]:.3f}",
                    z=f"{entity_position[2]:.3f}",
                    y=f"{entity_position[1]:.3f}",
                    distance=f"{distance:.3f}",
                )))
        rows.sort(key=lambda item: item[0])
        text = "\n".join(row for _, row in rows) if rows else og.app.tr("No nearby entities")
        if self.nearby_entities.toPlainText() != text:
            self.nearby_entities.setPlainText(text)

    def _copy_position(self):
        position = og.packet_capture_data.get_local_position()
        if position is not None:
            QApplication.clipboard().setText(f"{position[0]:.3f}, {position[1]:.3f}")

    def closeEvent(self, event):
        self._stop_capture()
        super().closeEvent(event)
