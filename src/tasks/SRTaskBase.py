import ctypes
import math
import time
from numbers import Real
from ctypes import wintypes

import cv2
import numpy as np
from ok import og, BaseTask

from src.MinimapSectorAngleDetector import MinimapSectorAngleDetector
from src.key_config import KEY_SETTINGS
from src.packet_capture.parser import ActorState


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

    _CAMERA_PIXELS_PER_DEGREE = 9.8
    # 以镜头朝向为基准，每 45 度对应一个移动方向；斜向移动需要同时按下两个键。
    _MOVE_KEYS = (
        ("w",), ("w", "d"), ("d",), ("s", "d"),
        ("s",), ("s", "a"), ("a",), ("w", "a"),
    )
    _MOVE_DURATION = 0.05
    _CAMERA_CORRECTION_THRESHOLD = 5
    _SPRINT_PROMPT_POSITION = (0.628, 0.968)
    _SPRINT_PROMPT_BGR = (0x35, 0xAE, 0xFF)
    _SPRINT_COOLDOWN = 1
    _SPRINT_MIN_DISTANCE = 10
    _MOVE_STALL_TIMEOUT = 15
    _MOVE_RESULT_SUCCESS = 0
    _MOVE_RESULT_DEATH = 1
    _MOVE_RESULT_TIMEOUT = 2
    _MOVE_RESULT_PATH_DEVIATION = 3
    _MOVE_RESULT_LOADING = 4
    _MOVE_RESULT_SCENE_CHANGED = 5
    _MOVE_BLOCKED_ACTOR_STATES = frozenset((
        ActorState.FALL,
        ActorState.TELEPORT,
        ActorState.FALL_TELEPORT,
    ))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_direction = 0
        self._camera_direction_detected = False
        self._movement_session_depth = 0
        self._movement_scene_id = None
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

    @property
    def in_combat(self):
        """Return 0 out of combat, 1 in combat, or ``None`` before first sync."""
        return og.packet_capture_data.get_combat_state() or og.packet_capture_data.get_actor_state() in [ActorState.DEAD, ActorState.RESURRECTION, ActorState.SKILL]

    @property
    def actor_state(self):
        """Return the captured actor state, or ``None`` before its first sync."""
        return og.packet_capture_data.get_actor_state()

    @property
    def is_dead(self):
        """Return whether the captured actor state is ``DEAD`` or ``RESURRECTION``."""
        actor_state = self.actor_state
        return actor_state is not None and actor_state in [ActorState.DEAD, ActorState.RESURRECTION]

    def _require_packet_capture(self):
        tool = self.packet_capture_tool
        if tool is None or not tool.is_capturing:
            raise PacketCaptureRequiredError("Packet capture must be started before using movement helpers.")
        return tool

    def detect_camera_direction(self):
        """Detect camera yaw from the translucent sector in the current minimap."""
        result = MinimapSectorAngleDetector.detect(self.frame)
        self._camera_direction_detected = result is not None
        if result is not None:
            self.camera_direction = result[0]
        return self.camera_direction

    def rotate_camera(self, degrees):
        """Rotate the camera horizontally; positive values turn right."""
        target_direction = (self.camera_direction + degrees) % 360.0
        pixels = round(float(degrees) * self._CAMERA_PIXELS_PER_DEGREE)
        self._move_mouse_relative(pixels, 0)
        self.camera_direction = target_direction
        self._camera_direction_detected = True

    def look_at(self, target):
        """Turn the camera toward an absolute yaw or a world position.

        ``target`` may be a numeric yaw in degrees, where 0 points along the
        positive Z axis and 90 points along the positive X axis, or an X/Z or
        X/Y/Z position. Return ``False`` without rotating when the camera
        direction cannot be detected; otherwise return ``True``.
        """
        if isinstance(target, Real) and not isinstance(target, bool):
            target_heading = float(target) % 360.0
        else:
            self._require_packet_capture()
            current = self.position
            if current is None:
                raise PacketCaptureRequiredError(
                    "Player position has not been received from packet capture."
                )
            current_x, current_z = self._xz(current)
            target_x, target_z = self._xz(target)
            dx, dz = target_x - current_x, target_z - current_z
            if dx == 0 and dz == 0:
                return True
            target_heading = math.degrees(math.atan2(dx, dz)) % 360.0

        self.next_frame()
        self.detect_camera_direction()
        if not self._camera_direction_detected:
            return False
        self.rotate_camera(self._angle_delta(target_heading, self.camera_direction))
        return True

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

    def move_to_position(
            self,
            start_position,
            target_position,
            line_tolerance=2,
            target_tolerance=2,
            max_path_deviation=None,
            enable_sprint=False,
            rotate_camera=True,
    ):
        """Move to one target, with optional sprinting and camera rotation."""
        target_x, target_z = self._xz(target_position)
        while True:
            start_x, start_z = self._xz(start_position)
            self._begin_movement_session()
            try:
                self._require_packet_capture()
                current = self.position
                if current is None:
                    raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
                current_x, current_z = self._xz(current)
                line_x, line_z = target_x - start_x, target_z - start_z
                line_length_squared = line_x * line_x + line_z * line_z
                move_result = self._MOVE_RESULT_SUCCESS
                if line_length_squared:
                    # 将当前位置投影到规划线段上：先回到路线附近，再沿路线前往终点，减少累计偏移。
                    projection = ((current_x - start_x) * line_x + (current_z - start_z) * line_z) / line_length_squared
                    projection = max(0.0, min(1.0, projection))
                    line_position = (start_x + projection * line_x, start_z + projection * line_z)
                    move_result = self._move_direct(
                        line_position,
                        line_tolerance,
                        enable_sprint=enable_sprint,
                        rotate_camera=rotate_camera,
                    )
                if move_result == self._MOVE_RESULT_SUCCESS:
                    move_result = self._move_direct(
                        target_position,
                        target_tolerance,
                        line_start=start_position,
                        line_tolerance=line_tolerance,
                        max_path_deviation=max_path_deviation,
                        enable_sprint=enable_sprint,
                        rotate_camera=rotate_camera,
                    )
            finally:
                self._end_movement_session()

            if move_result == self._MOVE_RESULT_SUCCESS:
                return True
            if move_result != self._MOVE_RESULT_DEATH:
                return False
            self.handle_death()
            start_position = self.position
            if start_position is None:
                raise PacketCaptureRequiredError("Player position has not been received from packet capture.")

    def handle_death(self, time_out=45):
        if not self.is_dead:
            return
        self._release_move_keys()
        start_time = time.monotonic()
        while self.is_dead:
            if time.monotonic() - start_time >= time_out:
                return
            self.next_frame()
            # 点击复活
            if (box := self.find_one(
                    'revive',
                    box=self.box_of_screen(0.81, 0.84, 0.94, 0.92))) and self.is_colorful(box):
                self.click(box)
            # 不小心点到用复活豆点取消
            if self.find_one('msg_use_bean'):
                self.click(0.37, 0.74)
            self.sleep(1)
        self.sleep(1)

    def move_to_positions(
            self,
            positions,
            line_tolerance=2,
            node_tolerance=2,
            max_path_deviation=None,
            enable_sprint=False,
            rotate_camera=True,
    ):
        """Move a path; return remaining nodes on movement failure, otherwise ``None``."""
        positions = list(positions)
        start = self.position
        if start is None:
            raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
        self._begin_movement_session()
        try:
            previous = None
            for index, target in enumerate(positions):
                segment_start = previous if previous is not None else start
                completed = self.move_to_position(
                    segment_start,
                    target,
                    line_tolerance=line_tolerance,
                    target_tolerance=node_tolerance,
                    max_path_deviation=max_path_deviation,
                    enable_sprint=enable_sprint,
                    rotate_camera=rotate_camera,
                )
                if not completed:
                    return positions[index:]
                previous = target
                if index < len(positions) - 1:
                    self._release_move_keys()
                    self.sleep(1)
            return None
        finally:
            self._end_movement_session()

    def get_custom_key(self, action):
        """Return a configured game hotkey, falling back to its default."""
        default = KEY_SETTINGS.default_config[action]
        get_global_config = getattr(self, 'get_global_config', None)
        if get_global_config is None:
            return default
        return get_global_config(KEY_SETTINGS).get(action, default)

    def _begin_movement_session(self):
        if self._movement_session_depth == 0:
            self._movement_scene_id = self.scene_id
        self._movement_session_depth += 1

    def _end_movement_session(self):
        self._movement_session_depth -= 1
        if self._movement_session_depth == 0:
            self._release_move_keys()
            self._movement_scene_id = None

    def _movement_scene_changed(self):
        return (
            getattr(self, '_movement_session_depth', 0) > 0
            and self.scene_id != self._movement_scene_id
        )

    def _release_move_keys(self):
        for key in reversed(self._held_move_keys):
            self.send_key_up(key)
        self._held_move_keys = ()

    def is_colorful(self, box, min_saturation=50):
        roi = box.crop_frame(self.frame)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        s_channel = hsv[:, :, 1]
        avg_saturation = np.mean(s_channel)
        return avg_saturation > min_saturation

    def _move_direct(
            self,
            target_position,
            tolerance,
            line_start=None,
            line_tolerance=None,
            max_path_deviation=None,
            enable_sprint=False,
            rotate_camera=True,
    ) -> int:
        """Move directly to a target and return a ``_MOVE_RESULT_*`` status."""
        target = self._xz(target_position)
        line_start_xz = self._xz(line_start) if line_start is not None else None
        previous_position = None
        line_correction_done = False
        # 移动开始即进入冲刺冷却，避免启用冲刺后立刻触发 Shift。
        last_sprint_at = time.monotonic()
        last_camera_correction_at = float("-inf")
        camera_deviation_frame_count = 0

        # 每段移动开始前先停止旧输入，并按需面向目标。
        self._release_move_keys()
        self._require_packet_capture()
        self.next_frame()
        if self._movement_scene_changed():
            return self._MOVE_RESULT_SCENE_CHANGED
        if getattr(self, 'frame', None) is not None and self.find_one('loading'):
            self._release_move_keys()
            return self._MOVE_RESULT_LOADING
        self.detect_camera_direction()
        current, delta, closest_distance = self._movement_position(target)
        closest_distance_at = time.monotonic()
        if rotate_camera and closest_distance > tolerance:
            self.rotate_camera(self._relative_target_angle(delta))
            last_camera_correction_at = closest_distance_at

        while True:
            self._require_packet_capture()
            self.next_frame()
            if self._movement_scene_changed():
                self._release_move_keys()
                return self._MOVE_RESULT_SCENE_CHANGED
            if self.is_dead:
                self._release_move_keys()
                return self._MOVE_RESULT_DEATH
            if getattr(self, 'frame', None) is not None and self.find_one('loading'):
                self._release_move_keys()
                return self._MOVE_RESULT_LOADING
            self.detect_camera_direction()

            # 刷新位置，并同时处理正常到达和跨过目标点的情况。
            current, delta, remaining_distance = self._movement_position(target)
            self._update_movement_info(current, target, remaining_distance)
            if self._movement_target_reached(
                    previous_position, current, target, remaining_distance, tolerance):
                return self._MOVE_RESULT_SUCCESS
            previous_position = current

            # 超出规划路径的最大允许范围时立即停止。
            if line_start_xz is not None and max_path_deviation is not None:
                path_deviation = self._path_deviation(current, line_start_xz, target)
                self.info["Path Deviation"] = f"{path_deviation:.2f}"
                if path_deviation > max_path_deviation:
                    self._release_move_keys()
                    return self._MOVE_RESULT_PATH_DEVIATION

            # 只要距离持续缩短就刷新停滞计时。
            now = time.monotonic()
            if remaining_distance < closest_distance:
                closest_distance = remaining_distance
                closest_distance_at = now
            elif now - closest_distance_at >= self._MOVE_STALL_TIMEOUT:
                self._release_move_keys()
                return self._MOVE_RESULT_TIMEOUT

            # 下落或传送期间暂停输入，避免移动键干扰状态切换。
            if self.actor_state in self._MOVE_BLOCKED_ACTOR_STATES:
                self._release_move_keys()
                self.sleep(self._MOVE_DURATION)
                continue

            # 根据镜头相对目标的角度选择移动键，并修正持续偏航。
            relative = self._relative_target_angle(delta)
            (
                relative,
                camera_aligned,
                camera_deviation_frame_count,
                last_camera_correction_at,
            ) = self._correct_camera_direction(
                relative,
                camera_deviation_frame_count,
                last_camera_correction_at,
                now,
                rotate_camera,
            )
            keys, line_correction_done = self._movement_keys(
                relative,
                current,
                target,
                line_start_xz,
                line_tolerance,
                line_correction_done,
            )
            self._hold_move_keys(keys)
            last_sprint_at = self._try_sprint(
                enable_sprint,
                camera_aligned,
                keys,
                now,
                last_sprint_at,
                remaining_distance,
            )
            self.sleep(self._MOVE_DURATION)

    def _movement_position(self, target):
        """读取当前位置，并返回目标方向和剩余距离。"""
        current = self.position
        if current is None:
            raise PacketCaptureRequiredError(
                "Player position has not been received from packet capture."
            )
        current = self._xz(current)
        delta = target[0] - current[0], target[1] - current[1]
        return current, delta, math.hypot(*delta)

    def _update_movement_info(self, current, target, remaining_distance):
        self.info["Current Position"] = f"({current[0]:.2f}, {current[1]:.2f})"
        self.info["Target Position"] = f"({target[0]:.2f}, {target[1]:.2f})"
        self.info["Remaining Distance"] = f"{remaining_distance:.2f}"

    def _movement_target_reached(
            self, previous, current, target, remaining_distance, tolerance):
        """判断当前点已到达，或本帧移动线段已穿过目标范围。"""
        if remaining_distance <= tolerance:
            return True
        return previous is not None and self._segment_reaches_target(
            previous, current, target, tolerance,
        )

    def _path_deviation(self, current, line_start, target):
        path_position = self._closest_point_on_segment(current, line_start, target)
        return math.hypot(
            current[0] - path_position[0],
            current[1] - path_position[1],
        )

    def _relative_target_angle(self, delta):
        target_heading = math.degrees(math.atan2(delta[0], delta[1])) % 360.0
        return self._angle_delta(target_heading, self.camera_direction)

    def _correct_camera_direction(
            self,
            relative,
            deviation_frame_count,
            last_correction_at,
            now,
            rotate_camera,
    ):
        """累计镜头偏差帧，并在满足条件时执行一次修正。"""
        camera_aligned = (
            self._camera_direction_detected
            and abs(relative) < self._CAMERA_CORRECTION_THRESHOLD
        )
        if (not self._camera_direction_detected
                or abs(relative) <= self._CAMERA_CORRECTION_THRESHOLD):
            deviation_frame_count = 0
        else:
            deviation_frame_count += 1

        should_correct = (
            rotate_camera
            and deviation_frame_count >= 3
            and now - last_correction_at >= 1
        )
        if should_correct:
            self.rotate_camera(relative)
            return 0.0, camera_aligned, 0, now
        return relative, camera_aligned, deviation_frame_count, last_correction_at

    def _movement_keys(
            self,
            relative,
            current,
            target,
            line_start,
            line_tolerance,
            line_correction_done,
    ):
        """把目标方向转换为移动键，并进行一次路线横向纠偏。"""
        direction_index = round(relative / 45.0) % 8
        keys = self._MOVE_KEYS[direction_index]
        should_correct_line = (
            not line_correction_done
            and keys == ("w",)
            and line_start is not None
            and line_tolerance is not None
        )
        if not should_correct_line:
            return keys, line_correction_done

        line_offset = self._signed_distance_to_line(current, line_start, target)
        self.info["Line Offset"] = f"{abs(line_offset):.2f}"
        if line_offset < -line_tolerance:
            return ("w", "a"), line_correction_done
        if line_offset > line_tolerance:
            return ("w", "d"), line_correction_done
        return keys, True

    def _hold_move_keys(self, keys):
        self._release_move_keys()
        for key in keys:
            self.send_key_down(key)
        self._held_move_keys = keys

    def _try_sprint(
            self,
            enable_sprint,
            camera_aligned,
            keys,
            now,
            last_sprint_at,
            remaining_distance,
    ):
        """满足冲刺提示、朝向和冷却条件时触发冲刺。"""
        should_sprint = (
            enable_sprint
            and remaining_distance > self._SPRINT_MIN_DISTANCE
            and self._sprint_prompt_visible()
            and camera_aligned
            and keys == ("w",)
            and now - last_sprint_at >= self._SPRINT_COOLDOWN
        )
        if should_sprint:
            self.send_key("shift", 0.5)
            return now
        return last_sprint_at

    def _sprint_prompt_visible(self):
        """检测是否能冲刺"""
        if self.frame is None or self.frame.size == 0:
            return False
        height, width = self.frame.shape[:2]
        x_ratio, y_ratio = self._SPRINT_PROMPT_POSITION
        x = min(width - 1, max(0, int(width * x_ratio)))
        y = min(height - 1, max(0, int(height * y_ratio)))
        return tuple(int(channel) for channel in self.frame[y, x][:3]) == self._SPRINT_PROMPT_BGR

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
    def _signed_distance_to_line(point, start, end):
        line_x = end[0] - start[0]
        line_z = end[1] - start[1]
        line_length = math.hypot(line_x, line_z)
        if line_length == 0:
            return 0.0
        return (
            line_x * (point[1] - start[1])
            - line_z * (point[0] - start[0])
        ) / line_length

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
