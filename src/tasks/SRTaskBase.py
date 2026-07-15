import math

from ok import og, BaseTask

from src.MinimapSectorAngleDetector import MinimapSectorAngleDetector


class PacketCaptureRequiredError(RuntimeError):
    pass


class SRTaskBase(BaseTask):
    """Shared Star Resonance helpers for one-shot and trigger tasks."""

    # 以镜头朝向为基准，每 45 度对应一个移动方向；斜向移动需要同时按下两个键。
    _MOVE_KEYS = (
        ("w",), ("w", "d"), ("d",), ("s", "d"),
        ("s",), ("s", "a"), ("a",), ("w", "a"),
    )
    _MOVE_DURATION = 0.2
    _DEFAULT_MOVE_SPEED = 3.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_direction = 0
        self._estimated_position = None
        self._estimated_position_confirmed = False
        self._last_server_position = None
        self._last_server_update_time = 0.0
        self._last_move_speed = self._DEFAULT_MOVE_SPEED
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
        return og.packet_capture_data.get_transform()[0]

    @property
    def last_position_update_time(self):
        return og.packet_capture_data.update_time

    @property
    def last_refresh_time(self):
        return self.last_position_update_time

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

    def move_to_position(self, start_position, target_position, line_tolerance=0.5, target_tolerance=1):
        """Join the start/target line first, then follow it to the target."""
        start_x, start_z = self._xz(start_position)
        target_x, target_z = self._xz(target_position)
        self._begin_movement_session(math.hypot(target_x - start_x, target_z - start_z))
        try:
            self._require_packet_capture()
            current = self._movement_position()
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
        start = self._movement_position()
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
            return self._movement_position()
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

        # 每轮只执行一次短移动，并在移动后用服务端坐标修正本地估算。
        while True:
            self._require_packet_capture()
            self.next_frame()
            self.detect_camera_direction()
            # 上一轮的方向键保持到新一帧采集完成，缩短松开与重新按下之间的停顿。
            self._release_move_keys()
            current = self._movement_position()
            if current is None:
                raise PacketCaptureRequiredError("Player position has not been received from packet capture.")
            current_x, current_z = self._xz(current)
            dx, dz = target_x - current_x, target_z - current_z
            if math.hypot(dx, dz) <= tolerance:
                if self._estimated_position_confirmed:
                    return current
                self._wait_for_server_position()
                continue

            target_heading = math.degrees(math.atan2(dx, dz)) % 360.0
            relative = self._angle_delta(target_heading, self.camera_direction)
            # 将目标相对镜头的角度量化为最近的八方向按键组合。
            direction_index = round(relative / 45.0) % 8
            keys = self._MOVE_KEYS[direction_index]
            expected_heading = (self.camera_direction + direction_index * 45.0) % 360.0
            for key in keys:
                self.send_key_down(key)
            self._held_move_keys = keys
            self._move_frame_count += 1
            if self._shift_on_second_move_frame and self._move_frame_count == 2:
                self.send_key("shift", 0.1)
            self.sleep(self._MOVE_DURATION)

            after_position = self.position
            server_update_time = self.last_position_update_time
            position_updated = (after_position is not None and
                                server_update_time > self._last_server_update_time)
            if position_updated:
                # 抓包数据优先级最高，同时用连续的服务端采样更新实际移动速度。
                self._accept_server_position(after_position, server_update_time)
                after_x, after_z = self._estimated_position

            if not position_updated:
                # 服务端坐标尚未刷新时，根据最近速度暂时推算位置，避免移动流程停顿。
                heading_radians = math.radians(expected_heading)
                estimated_distance = self._last_move_speed * self._MOVE_DURATION
                after_x = current_x + math.sin(heading_radians) * estimated_distance
                after_z = current_z + math.cos(heading_radians) * estimated_distance

            self._estimated_position = (after_x, after_z)
            self._estimated_position_confirmed = position_updated
            # 短移动可能跨过目标点，因此检查整段轨迹，而不只检查移动后的端点。
            if self._segment_reaches_target(
                    (current_x, current_z), (after_x, after_z), (target_x, target_z), tolerance):
                if position_updated:
                    return self._estimated_position
                self._wait_for_server_position()

    def _movement_position(self):
        """Prefer a newly received server position, otherwise retain the movement estimate."""
        server_position = self.position
        server_update_time = self.last_position_update_time
        if server_position is not None and server_update_time > self._last_server_update_time:
            self._accept_server_position(server_position, server_update_time)
        return self._estimated_position or server_position

    def _accept_server_position(self, server_position, update_time):
        """Use a fresh server position and derive speed only from consecutive server samples."""
        server_x, server_z = self._xz(server_position)
        # 只有两个真实服务端采样点才能用于测速，避免把本地估算误差带入速度。
        if self._last_server_position is not None and self._last_server_update_time:
            previous_x, previous_z = self._xz(self._last_server_position)
            elapsed = update_time - self._last_server_update_time
            moved_distance = math.hypot(server_x - previous_x, server_z - previous_z)
            if elapsed > 0 and moved_distance >= 0.01:
                self._last_move_speed = moved_distance / elapsed

        self._last_server_position = server_position
        self._last_server_update_time = update_time
        self._estimated_position = (server_x, server_z)
        self._estimated_position_confirmed = True

    def _wait_for_server_position(self):
        """Tap each movement key until a fresh server position confirms or corrects the estimate."""
        previous_update_time = self._last_server_update_time
        # 依次轻点移动键以触发位置包，直到服务端确认或纠正当前估算位置。
        while True:
            for key in ("w", "a", "s", "d"):
                self._require_packet_capture()
                server_position = self.position
                server_update_time = self.last_position_update_time
                if server_position is not None and server_update_time > previous_update_time:
                    self._accept_server_position(server_position, server_update_time)
                    return self._estimated_position
                self.send_key(key, down_time=0.1)
                self.sleep(0.1)

    @staticmethod
    def _segment_reaches_target(start, end, target, tolerance):
        """Return whether a movement segment reaches or passes close enough to a target."""
        segment_x, segment_z = end[0] - start[0], end[1] - start[1]
        length_squared = segment_x * segment_x + segment_z * segment_z
        if not length_squared:
            return math.hypot(target[0] - start[0], target[1] - start[1]) <= tolerance
        projection = ((target[0] - start[0]) * segment_x +
                      (target[1] - start[1]) * segment_z) / length_squared
        projection = max(0.0, min(1.0, projection))
        closest_x = start[0] + projection * segment_x
        closest_z = start[1] + projection * segment_z
        return math.hypot(target[0] - closest_x, target[1] - closest_z) <= tolerance

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
