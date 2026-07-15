import ctypes
import math
from ctypes import wintypes

from ok import og, BaseTask

from src.MinimapSectorAngleDetector import MinimapSectorAngleDetector


_INPUT_MOUSE = 0
_MOUSEEVENTF_MOVE = 0x0001


class _MouseInput(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouse_data", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra_info", ctypes.c_size_t),
    )


class _InputUnion(ctypes.Union):
    _fields_ = (("mouse", _MouseInput),)


class _Input(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = (
        ("type", wintypes.DWORD),
        ("data", _InputUnion),
    )


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT


class PacketCaptureRequiredError(RuntimeError):
    pass


class SRTaskBase(BaseTask):
    """Shared Star Resonance helpers for one-shot and trigger tasks."""

    _CAMERA_PIXELS_PER_DEGREE = 10
    # 以镜头朝向为基准，每 45 度对应一个移动方向；斜向移动需要同时按下两个键。
    _MOVE_KEYS = (
        ("w",), ("w", "d"), ("d",), ("s", "d"),
        ("s",), ("s", "a"), ("a",), ("w", "a"),
    )
    _MOVE_DURATION = 0.05

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_direction = 0
        self._movement_session_depth = 0
        self._move_frame_count = 0
        self._shift_on_second_move_frame = False
        self._held_move_keys = ()

    @property
    def packet_capture_tool(self):
        return getattr(og, "packet_capture_tool", None)

    @property
    def packet_capture(self):
        return self.packet_capture_tool

    @property
    def position(self):
        return og.packet_capture_data.get_local_position()

    @property
    def scene_id(self):
        return og.packet_capture_data.scene_id

    @property
    def player_id(self):
        return og.packet_capture_data.player_id

    @property
    def player_uuid(self):
        return og.packet_capture_data.player_uuid

    @property
    def nearby_entities(self):
        return og.packet_capture_data.get_world()[3]

    def _require_packet_capture(self):
        tool = self.packet_capture_tool
        if tool is None or not tool.is_capturing:
            raise PacketCaptureRequiredError("Packet capture must be started before using movement helpers.")
        return tool

    def detect_camera_direction(self):
        """Detect camera yaw from the translucent sector in the current minimap."""
        result = MinimapSectorAngleDetector.detect(self.frame)
        if result is not None:
            self.camera_direction = result[0]
        return self.camera_direction

    def rotate_camera(self, degrees):
        """Rotate the camera horizontally; positive values turn right."""
        pixels = round(float(degrees) * self._CAMERA_PIXELS_PER_DEGREE)
        self._move_mouse_relative(pixels, 0)

    @staticmethod
    def _move_mouse_relative(dx, dy):
        event = _Input(
            type=_INPUT_MOUSE,
            mouse=_MouseInput(
                dx=dx,
                dy=dy,
                mouse_data=0,
                flags=_MOUSEEVENTF_MOVE,
                time=0,
                extra_info=0,
            ),
        )
        sent = _user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_Input))
        if sent != 1:
            raise ctypes.WinError(ctypes.get_last_error())

    def move_to_position(self, start_position, target_position, line_tolerance=0.5, target_tolerance=1):
        """Join the start/target line first, then follow it to the target."""
        start_x, start_z = self._xz(start_position)
        target_x, target_z = self._xz(target_position)
        self._begin_movement_session(math.hypot(target_x - start_x, target_z - start_z))
        try:
            self._require_packet_capture()
            current = self.position
            if current is None:
                raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
            current_x, current_z = self._xz(current)
            line_x, line_z = target_x - start_x, target_z - start_z
            line_length_squared = line_x * line_x + line_z * line_z
            if line_length_squared:
                # 将当前位置投影到规划线段上：先回到路线附近，再沿路线前往终点，减少累计偏移。
                projection = ((current_x - start_x) * line_x + (current_z - start_z) * line_z) / line_length_squared
                projection = max(0.0, min(1.0, projection))
                line_position = (start_x + projection * line_x, start_z + projection * line_z)
                self._move_direct(line_position, line_tolerance)
            return self._move_direct(target_position, target_tolerance)
        finally:
            self._end_movement_session()

    def move_to_positions(self, positions, line_tolerance=0.5, node_tolerance=1):
        """Move through positions, using the player's position for the first segment."""
        positions = list(positions)
        start = self.position
        if start is None:
            raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
        route_points = [start, *positions]
        total_distance = sum(
            math.hypot(self._xz(end)[0] - self._xz(begin)[0],
                       self._xz(end)[1] - self._xz(begin)[1])
            for begin, end in zip(route_points, route_points[1:])
        )
        self._begin_movement_session(total_distance)
        try:
            previous = None
            for target in positions:
                segment_start = previous if previous is not None else start
                self.move_to_position(segment_start, target, line_tolerance=line_tolerance,
                                      target_tolerance=node_tolerance)
                previous = target
            return self.position
        finally:
            self._end_movement_session()

    def _begin_movement_session(self, total_distance):
        if self._movement_session_depth == 0:
            self._move_frame_count = 0
            self._shift_on_second_move_frame = total_distance > 10
        self._movement_session_depth += 1

    def _end_movement_session(self):
        self._movement_session_depth -= 1
        if self._movement_session_depth == 0:
            self._release_move_keys()

    def _release_move_keys(self):
        for key in reversed(self._held_move_keys):
            self.send_key_up(key)
        self._held_move_keys = ()

    def _move_direct(self, target_position, tolerance):
        target_x, target_z = self._xz(target_position)
        previous_position = None

        while True:
            self._require_packet_capture()
            self.next_frame()
            self.detect_camera_direction()
            current = self.position
            if current is None:
                raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
            current_x, current_z = self._xz(current)
            dx, dz = target_x - current_x, target_z - current_z
            remaining_distance = math.hypot(dx, dz)
            self.info["Current Position"] = f"({current_x:.2f}, {current_z:.2f})"
            self.info["Target Position"] = f"({target_x:.2f}, {target_z:.2f})"
            self.info["Remaining Distance"] = f"{remaining_distance:.2f}"
            reached_target = remaining_distance <= tolerance
            if previous_position is not None:
                reached_target = reached_target or self._segment_reaches_target(
                    previous_position,
                    (current_x, current_z),
                    (target_x, target_z),
                    tolerance,
                )
            if reached_target:
                return current
            previous_position = (current_x, current_z)

            target_heading = math.degrees(math.atan2(dx, dz)) % 360.0
            relative = self._angle_delta(target_heading, self.camera_direction)
            # 将目标相对镜头的角度量化为最近的八方向按键组合。
            direction_index = round(relative / 45.0) % 8
            keys = self._MOVE_KEYS[direction_index]
            self._release_move_keys()
            for key in keys:
                self.send_key_down(key)
            self._held_move_keys = keys
            self._move_frame_count += 1
            if self._shift_on_second_move_frame and self._move_frame_count == 2:
                self.send_key("shift", 0.1)
            self.sleep(self._MOVE_DURATION)

    @staticmethod
    def _xz(position):
        if len(position) >= 3:
            return float(position[0]), float(position[2])
        if len(position) == 2:
            return float(position[0]), float(position[1])
        raise ValueError("position must contain X/Z or X/Y/Z")

    @staticmethod
    def _segment_reaches_target(start, end, target, tolerance):
        closest = SRTaskBase._closest_point_on_segment(target, start, end)
        return math.hypot(target[0] - closest[0], target[1] - closest[1]) <= tolerance

    @staticmethod
    def _closest_point_on_segment(point, start, end):
        segment_x = end[0] - start[0]
        segment_z = end[1] - start[1]
        segment_length_squared = segment_x * segment_x + segment_z * segment_z
        if segment_length_squared == 0:
            return start

        projection = (
            (point[0] - start[0]) * segment_x
            + (point[1] - start[1]) * segment_z
        ) / segment_length_squared
        projection = max(0.0, min(1.0, projection))
        return start[0] + projection * segment_x, start[1] + projection * segment_z

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
