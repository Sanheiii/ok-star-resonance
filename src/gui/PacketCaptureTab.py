import math
import threading
from collections import Counter
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, PrimaryPushButton, PushButton

from ok import Config, og
from ok.gui.Communicate import communicate
from ok.gui.widget.CustomTab import CustomTab
from src.packet_capture import NpcapCapture, WinDivertCapture, list_devices
from src.packet_capture.adapter_detection import detect_process_device, game_window_pid
from src.packet_capture.parser import ActorState, GamePacketParser


ACTOR_STATE_NAMES = {
    ActorState.DEFAULT: "Default",
    ActorState.SINGING: "Singing",
    ActorState.SKILL: "Skill action",
    ActorState.JUMP: "Jump",
    ActorState.RUSH: "Rush",
    ActorState.CLIMB: "Climb",
    ActorState.SWIM: "Swim",
    ActorState.FISHING: "Fishing",
    ActorState.ACTION: "Action",
    ActorState.DEAD: "Dead",
    ActorState.STIFF: "Stiff",
    ActorState.SWIM_STIFF: "Swim stiff",
    ActorState.BORN: "Born",
    ActorState.TELEPORT: "Teleport",
    ActorState.FALL: "Fall",
    ActorState.FLOW: "Flow",
    ActorState.GLIDE: "Glide",
    ActorState.PEDAL_WALL: "Pedal wall",
    ActorState.FALL_TELEPORT: "Fall teleport",
    ActorState.SELF_PHOTO: "Self photo",
    ActorState.COLLECTION: "Collecting",
    ActorState.RESET: "Reset",
    ActorState.BREAKING: "Breaking",
    ActorState.WEAKNESS: "Weakness",
    ActorState.FRACTURE: "Fracture",
    ActorState.ABNORMAL: "Abnormal",
    ActorState.RESURRECTION: "Resurrection",
    ActorState.INTERACTION: "Interaction",
    ActorState.SCENE_INTERACTION: "Scene interaction",
    ActorState.TUNNEL_FLY: "Tunnel fly",
    ActorState.LEVITATION: "Levitation",
    ActorState.HOMELAND_EDIT: "Homeland edit",
    ActorState.RIDE: "Ride",
    ActorState.RIDE_CONTROL: "Ride control",
    ActorState.INSTRUMENT: "Instrument",
    ActorState.FIXED: "Fixed",
    ActorState.ALL: "All",
}

ENTITY_TYPE_NAMES = {
    0: "Unknown",
    1: "Monster",
    2: "NPC",
    3: "Scene object",
    5: "Zone",
    6: "Bullet",
    7: "Client bullet",
    8: "Pet",
    10: "Player",
    11: "Dummy",
    12: "Drop",
    14: "Field",
    15: "Trap",
    16: "Collection",
    18: "Static object",
    19: "Vehicle",
    20: "Toy",
    21: "Community house",
    22: "House item",
}

DIRECTION_NAMES = (
    "Front",
    "Front right",
    "Right",
    "Back right",
    "Back",
    "Back left",
    "Left",
    "Front left",
)

CAPTURE_METHOD_NPCAP = "Npcap"
CAPTURE_METHOD_WINDIVERT = "WinDivert"


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
        self._actor_state_revision = -1
        self._sequence_scene_id = None
        self._has_sequence_scene = False
        self._entity_sequences = {}
        self._next_sequence_by_attr_id = {}
        self._visible_entity_details = {}
        self._entity_list_signature = None
        self._config = Config(
            "packet_capture",
            {"capture_method": CAPTURE_METHOD_NPCAP, "device_name": ""},
        )
        self._refreshing_devices = False
        og.packet_capture_tool = self

        controls = QWidget(self.view)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.capture_method_combo = ComboBox(controls)
        self.capture_method_combo.addItems(
            [CAPTURE_METHOD_NPCAP, CAPTURE_METHOD_WINDIVERT]
        )
        self.device_combo = ComboBox(controls)
        self.refresh_button = PushButton(FluentIcon.SYNC, og.app.tr("Refresh adapters"), controls)
        self.auto_select_button = PushButton(og.app.tr("Auto select"), controls)
        self.capture_button = PrimaryPushButton(og.app.tr("Start capture"), controls)
        controls_layout.addWidget(BodyLabel(og.app.tr("Capture method"), controls))
        controls_layout.addWidget(self.capture_method_combo)
        controls_layout.addWidget(BodyLabel(og.app.tr("Network adapter"), controls))
        controls_layout.addWidget(self.device_combo, 1)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.auto_select_button)
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
            og.app.tr("Combat status: {status}").format(status=unknown), state
        )
        self.actor_state_label = BodyLabel(
            og.app.tr("Actor state: {state}").format(state=unknown), state
        )
        self.nearby_title = BodyLabel(og.app.tr("Nearby entities"), state)
        self.nearby_entities = QListWidget(state)
        self.nearby_entities.setMinimumHeight(180)
        self._set_entity_list([])
        self.copy_button = PushButton(
            FluentIcon.COPY, og.app.tr("Copy local position XZ"), state
        )
        self.copy_button.setEnabled(False)
        state_layout.addWidget(self.status_label)
        state_layout.addWidget(self.server_position_label)
        state_layout.addWidget(self.local_position_label)
        state_layout.addWidget(self.facing_label)
        state_layout.addWidget(self.player_id_label)
        state_layout.addWidget(self.scene_id_label)
        state_layout.addWidget(self.combat_state_label)
        state_layout.addWidget(self.actor_state_label)
        state_layout.addWidget(self.copy_button)
        state_layout.addWidget(self.nearby_title)
        state_layout.addWidget(self.nearby_entities)
        state_layout.addStretch(1)
        self.add_widget(state, 1)

        saved_method = self._config.get("capture_method")
        method_index = self.capture_method_combo.findText(saved_method)
        self.capture_method_combo.setCurrentIndex(max(method_index, 0))
        self.capture_method_combo.currentIndexChanged.connect(self._capture_method_changed)
        self.refresh_button.clicked.connect(self._refresh_devices)
        self.auto_select_button.clicked.connect(self._auto_select_device)
        self.device_combo.currentIndexChanged.connect(self._save_selected_device)
        self.capture_button.clicked.connect(self._toggle_capture)
        self.copy_button.clicked.connect(self._copy_position)
        self.nearby_entities.itemClicked.connect(self._show_entity_details)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_transform)
        self._timer.start(200)
        self._update_adapter_controls()
        if self._uses_npcap():
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

    def _uses_npcap(self):
        return self.capture_method_combo.currentText() == CAPTURE_METHOD_NPCAP

    def _capture_method_changed(self, _index):
        method = self.capture_method_combo.currentText()
        self._config["capture_method"] = method
        self._update_adapter_controls()
        if method == CAPTURE_METHOD_NPCAP and not self._devices:
            self._refresh_devices()
        elif method == CAPTURE_METHOD_WINDIVERT:
            self.status_label.setText(og.app.tr("WinDivert does not require an adapter"))

    def _update_adapter_controls(self):
        enabled = self._uses_npcap() and not self.is_capturing
        self.device_combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.auto_select_button.setEnabled(enabled)

    def _refresh_devices(self):
        if not self._uses_npcap():
            return
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

    def _auto_select_device(self):
        if self.is_capturing:
            return
        try:
            hwnd_window = getattr(og.device_manager, "hwnd_window", None)
            pid = game_window_pid(getattr(hwnd_window, "hwnd", 0))
            if not pid:
                self._show_auto_select_error("Connect to the game window first")
                return
            device = detect_process_device(pid, self._devices)
            if device is None:
                self._show_auto_select_error("No active game network adapter was detected")
                return
            index = next(
                (i for i, candidate in enumerate(self._devices) if candidate.name == device.name),
                -1,
            )
            if index < 0:
                self._show_auto_select_error("The detected adapter is unavailable in Npcap")
                return
            self.device_combo.setCurrentIndex(index)
            self._config["device_name"] = device.name
            self._show_auto_select_message(
                "Selected adapter: {adapter}",
                error=False,
                adapter=device.display_name,
            )
        except Exception as exc:
            self.logger.warning(f"Automatic adapter detection failed: {exc}")
            self._show_auto_select_error("Failed to detect the game network adapter")

    @staticmethod
    def _show_auto_select_error(message):
        PacketCaptureTab._show_auto_select_message(message, error=True)

    @staticmethod
    def _show_auto_select_message(message, error=False, **params):
        communicate.notification.emit(
            og.app.tr(message).format(**params),
            og.app.tr("Auto select"),
            error,
            False,
            None,
            None,
        )

    def _toggle_capture(self):
        if self.capture_button.text() == og.app.tr("Stop capture"):
            self._stop_capture()
            return
        method = self.capture_method_combo.currentText()
        device_name = None
        if method == CAPTURE_METHOD_NPCAP:
            index = self.device_combo.currentIndex()
            if index < 0 or index >= len(self._devices):
                self.status_label.setText(og.app.tr("Select a network adapter first"))
                return
            device_name = self._devices[index].name
        self.capture_method_combo.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.auto_select_button.setEnabled(False)
        self.capture_button.setText(og.app.tr("Stop capture"))
        self.status_label.setText(og.app.tr("Capturing"))
        self._stop_requested = False
        self._capture_error = None
        self._parser.reset_transport()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(method, device_name),
            daemon=True,
            name=f"{method}Capture",
        )
        self._capture_thread.start()

    def _capture_loop(self, method, device_name):
        capture = None
        try:
            capture = (
                NpcapCapture(device_name)
                if method == CAPTURE_METHOD_NPCAP
                else WinDivertCapture()
            )
            self._capture = capture
            if self._stop_requested:
                return
            self._parser.set_datalink(capture.datalink)
            capture.run(self._on_packet)
        except Exception as exc:
            self.logger.error(f"{method} capture failed: {exc}")
            self._capture_error = str(exc)
        finally:
            if capture:
                capture.close()
            if self._capture is capture:
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
        if self._actor_state_revision != self._parser.actor_state_revision:
            if self._parser.actor_state is not None:
                og.packet_capture_data.update_actor_state(self._parser.actor_state)
            self._actor_state_revision = self._parser.actor_state_revision

    def _stop_capture(self):
        self._stop_requested = True
        if self._capture:
            self._capture.stop()
        self.capture_button.setEnabled(False)
        self.status_label.setText(og.app.tr("Capture stopped"))

    def _capture_failed(self, message):
        self._set_idle(message)

    def _set_idle(self, message):
        self.capture_button.setText(og.app.tr("Start capture"))
        self.capture_button.setEnabled(True)
        self.capture_method_combo.setEnabled(True)
        self._update_adapter_controls()
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
        self._refresh_world_state(server_position, facing)

    def _refresh_world_state(self, player_position, player_facing):
        scene_id, player_id, player_uuid, entities = og.packet_capture_data.get_world()
        self._reset_entity_sequences_if_scene_changed(scene_id)
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
        if combat_state is None:
            combat_status = og.app.tr("Unknown")
        elif combat_state == 1:
            combat_status = og.app.tr("In combat")
        elif combat_state == 0:
            combat_status = og.app.tr("Out of combat")
        else:
            combat_status = og.app.tr("Unknown value: {value}").format(
                value=combat_state
            )
        self.combat_state_label.setText(
            og.app.tr("Combat status: {status}").format(status=combat_status)
        )
        actor_state = og.packet_capture_data.get_actor_state()
        if actor_state is None:
            actor_state_text = og.app.tr("Unknown")
        else:
            try:
                state_name = ACTOR_STATE_NAMES[ActorState(actor_state)]
                actor_state_text = f"{state_name} ({actor_state})"
            except (ValueError, KeyError):
                actor_state_text = og.app.tr("Unknown value: {value}").format(
                    value=actor_state
                )
        self.actor_state_label.setText(
            og.app.tr("Actor state: {state}").format(state=actor_state_text)
        )
        rows = []
        visible_details = {}
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
                type_name = (
                    "Teammate"
                    if entity_type == 10 and entity.get("is_teammate")
                    else ENTITY_TYPE_NAMES.get(entity_type, "Unknown")
                )
                translated_type = og.app.tr(type_name)
                attr_id = entity.get("attr_id")
                sequence = self._entity_sequence(entity_id, attr_id)
                direction = self._relative_direction(
                    player_position, player_facing, entity_position
                )
                direction_text = (
                    og.app.tr("Unknown") if direction is None else og.app.tr(direction)
                )
                attr_id_text = og.app.tr("Unknown") if attr_id is None else str(attr_id)
                text = og.app.tr(
                    "{type}: {id}({index})-{direction}{distance}"
                ).format(
                    type=translated_type,
                    id=attr_id_text,
                    index=sequence,
                    direction=direction_text,
                    distance=f"{distance:.3f}",
                )
                rows.append((distance, sequence, entity_id, text))
                visible_details[entity_id] = {
                    **entity,
                    "uuid": entity_id,
                    "sequence": sequence,
                    "direction": direction_text,
                    "distance": distance,
                    "type_name": translated_type,
                }
        rows.sort(key=lambda item: (item[0], item[1]))
        self._visible_entity_details = visible_details
        self._set_entity_list([(row[2], row[3]) for row in rows])

    def _reset_entity_sequences_if_scene_changed(self, scene_id):
        if not self._has_sequence_scene:
            self._sequence_scene_id = scene_id
            self._has_sequence_scene = True
            return
        if scene_id == self._sequence_scene_id:
            return
        self._sequence_scene_id = scene_id
        self._entity_sequences.clear()
        self._next_sequence_by_attr_id.clear()

    def _entity_sequence(self, entity_uuid, attr_id):
        existing = self._entity_sequences.get(entity_uuid)
        if existing is not None and existing[0] == attr_id:
            return existing[1]
        sequence = self._next_sequence_by_attr_id.get(attr_id, 0) + 1
        self._next_sequence_by_attr_id[attr_id] = sequence
        self._entity_sequences[entity_uuid] = (attr_id, sequence)
        return sequence

    @staticmethod
    def _relative_direction(player_position, player_facing, entity_position):
        if player_position is None or player_facing is None or entity_position is None:
            return None
        delta_x = entity_position[0] - player_position[0]
        delta_z = entity_position[2] - player_position[2]
        if math.isclose(delta_x, 0.0) and math.isclose(delta_z, 0.0):
            return DIRECTION_NAMES[0]
        bearing = math.degrees(math.atan2(delta_x, delta_z)) % 360.0
        relative_angle = (bearing - player_facing) % 360.0
        direction_index = int((relative_angle + 22.5) // 45.0) % 8
        return DIRECTION_NAMES[direction_index]

    def _set_entity_list(self, rows):
        signature = tuple(rows)
        if signature == self._entity_list_signature:
            return
        self._entity_list_signature = signature
        self.nearby_entities.clear()
        if not rows:
            item = QListWidgetItem(og.app.tr("No nearby entities"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.nearby_entities.addItem(item)
            return
        for entity_uuid, text in rows:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entity_uuid)
            self.nearby_entities.addItem(item)

    def _show_entity_details(self, item):
        entity_uuid = item.data(Qt.ItemDataRole.UserRole)
        entity = self._visible_entity_details.get(entity_uuid)
        if entity is None:
            return
        position = entity.get("position")
        flags = []
        if entity.get("is_summoned"):
            flags.append(og.app.tr("Summoned"))
        if entity.get("is_client_created"):
            flags.append(og.app.tr("Client-created"))
        flag_text = ", ".join(flags) if flags else og.app.tr("None")
        attr_id = entity.get("attr_id")
        entity_facing = entity.get("facing")
        updated_at = entity.get("updated_at")
        try:
            updated_at_text = datetime.fromtimestamp(updated_at).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except (OSError, OverflowError, TypeError, ValueError):
            updated_at_text = og.app.tr("Unknown")
        details = og.app.tr(
            "UUID: {uuid}\nUID: {uid}\nType: {type} ({type_id})\n"
            "Attr ID: {attr_id}\nSequence: {sequence}\n"
            "XZ: {x}, {z}\nY: {y}\nEntity facing: {facing}\n"
            "Relative direction: {direction}\nDistance: {distance}\n"
            "Flags: {flags}\nUpdated at: {updated_at}"
        ).format(
            uuid=entity_uuid,
            uid=entity_uuid >> 16,
            type=entity["type_name"],
            type_id=entity.get("entity_type", 0),
            attr_id=og.app.tr("Unknown") if attr_id is None else attr_id,
            sequence=entity["sequence"],
            x=f"{position[0]:.3f}",
            z=f"{position[2]:.3f}",
            y=f"{position[1]:.3f}",
            facing=(og.app.tr("Unknown") if entity_facing is None
                    else f"{entity_facing:.2f}\N{DEGREE SIGN}"),
            direction=entity["direction"],
            distance=f"{entity['distance']:.3f}",
            flags=flag_text,
            updated_at=updated_at_text,
        )
        dialog = QMessageBox(self)
        dialog.setWindowTitle(og.app.tr("Entity details"))
        dialog.setText(details)
        copy_button = dialog.addButton(
            og.app.tr("Copy XZ"), QMessageBox.ButtonRole.ActionRole
        )
        dialog.addButton(QMessageBox.StandardButton.Close)
        dialog.exec()
        if dialog.clickedButton() is copy_button:
            QApplication.clipboard().setText(
                f"{position[0]:.3f}, {position[2]:.3f}"
            )

    def _copy_position(self):
        position = og.packet_capture_data.get_local_position()
        if position is not None:
            QApplication.clipboard().setText(f"{position[0]:.3f}, {position[2]:.3f}")

    def closeEvent(self, event):
        self._stop_capture()
        super().closeEvent(event)
