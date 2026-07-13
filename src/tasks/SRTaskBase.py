import math

from ok import og


class PacketCaptureRequiredError(RuntimeError):
    pass


class SRTaskBase:
    """Shared Star Resonance helpers for one-shot and trigger tasks."""

    _MOVE_KEYS = (
        ("w",), ("w", "d"), ("d",), ("s", "d"),
        ("s",), ("s", "a"), ("a",), ("w", "a"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_direction = None

    @property
    def packet_capture_tool(self):
        return getattr(og, "packet_capture_tool", None)

    @property
    def packet_capture(self):
        return self.packet_capture_tool

    @property
    def position(self):
        return og.packet_capture_data.get_transform()[0]

    @property
    def facing(self):
        return og.packet_capture_data.get_transform()[1]

    @property
    def last_position_update_time(self):
        return og.packet_capture_data.update_time

    @property
    def last_refresh_time(self):
        return self.last_position_update_time

    def _require_packet_capture(self):
        tool = self.packet_capture_tool
        if tool is None or not tool.is_capturing:
            raise PacketCaptureRequiredError("Packet capture must be started before using movement helpers.")
        return tool

    def detect_camera_direction(self):
        """Walk forward briefly and use the resulting character facing as camera yaw."""
        self._require_packet_capture()
        self.send_key_down("w")
        try:
            self.sleep(0.5)
        finally:
            self.send_key_up("w")
        facing = self.facing
        if facing is None:
            raise PacketCaptureRequiredError("Player facing has not been received from packet capture.")
        self.camera_direction = facing % 360.0
        return self.camera_direction

    def set_camera_direction(self, direction):
        self.camera_direction = float(direction) % 360.0

    def move_to_position(self, start_position, target_position, line_tolerance=0.5, target_tolerance=0.2):
        """Join the start/target line first, then follow it to the target."""
        self._require_packet_capture()
        if self.camera_direction is None:
            self.detect_camera_direction()
        start_x, start_z = self._xz(start_position)
        target_x, target_z = self._xz(target_position)

        current = self.position
        if current is None:
            raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
        current_x, current_z = self._xz(current)
        line_x, line_z = target_x - start_x, target_z - start_z
        line_length_squared = line_x * line_x + line_z * line_z
        if line_length_squared:
            projection = ((current_x - start_x) * line_x + (current_z - start_z) * line_z) / line_length_squared
            projection = max(0.0, min(1.0, projection))
            line_position = (start_x + projection * line_x, start_z + projection * line_z)
            self._move_direct(line_position, line_tolerance)
        return self._move_direct(target_position, target_tolerance)

    def move_to_positions(self, positions, node_tolerance=0.2, line_tolerance=0.5):
        """Move through positions, using the player's position for the first segment."""
        previous = None
        for target in positions:
            start = previous if previous is not None else self.position
            if start is None:
                raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
            self.move_to_position(start, target, line_tolerance=line_tolerance,
                                  target_tolerance=node_tolerance)
            previous = target
        return self.position

    def _move_direct(self, target_position, tolerance):
        target_x, target_z = self._xz(target_position)

        while True:
            self._require_packet_capture()
            current = self.position
            if current is None:
                raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
            current_x, current_z = self._xz(current)
            dx, dz = target_x - current_x, target_z - current_z
            if math.hypot(dx, dz) <= tolerance:
                return current

            target_heading = math.degrees(math.atan2(dx, dz)) % 360.0
            relative = self._angle_delta(target_heading, self.camera_direction)
            direction_index = round(relative / 45.0) % 8
            keys = self._MOVE_KEYS[direction_index]
            expected_heading = (self.camera_direction + direction_index * 45.0) % 360.0
            before_update = self.last_position_update_time

            for key in keys:
                self.send_key_down(key)
            try:
                self.sleep(0.1)
            finally:
                for key in reversed(keys):
                    self.send_key_up(key)

            after_position = self.position
            if after_position is None or self.last_position_update_time <= before_update:
                continue
            after_x, after_z = self._xz(after_position)
            moved_x, moved_z = after_x - current_x, after_z - current_z
            if math.hypot(moved_x, moved_z) < 0.01:
                continue
            actual_heading = math.degrees(math.atan2(moved_x, moved_z)) % 360.0
            if abs(self._angle_delta(actual_heading, expected_heading)) > 35.0:
                self.camera_direction = (actual_heading - direction_index * 45.0) % 360.0

    @staticmethod
    def _xz(position):
        if len(position) >= 3:
            return float(position[0]), float(position[2])
        if len(position) == 2:
            return float(position[0]), float(position[1])
        raise ValueError("position must contain X/Z or X/Y/Z")

    @staticmethod
    def _angle_delta(target, origin):
        return (target - origin + 180.0) % 360.0 - 180.0

    def get_game_language(self):
        lang = self.get_global_config("Game Settings").get("Game Language")
        if lang == "简体中文":
            return "zhs"
        if lang == "繁體中文":
            return "zht"
        if lang == "日本語":
            return "jp"
        return "en"
