import time
from threading import RLock


class PacketCaptureData:
    """Thread-safe data decoded from the packet capture stream."""

    def __init__(self):
        self._lock = RLock()
        self.server_position = None
        self.facing = None
        self.server_update_time = 0.0
        self.local_position = None
        self.local_update_time = 0.0
        self.scene_id = None
        self.player_id = None
        self.player_uuid = None
        self.nearby_entities = {}
        self.combat_state = None
        self.combat_state_update_time = 0.0

    def update_server_transform(self, position=None, facing=None):
        with self._lock:
            if position is not None:
                self.server_position = tuple(float(value) for value in position)
            if facing is not None:
                self.facing = float(facing) % 360.0
            self.server_update_time = time.time()

    def get_server_transform(self):
        with self._lock:
            return self.server_position, self.facing

    def update_local_position(self, position):
        with self._lock:
            self.local_position = tuple(float(value) for value in position)
            self.local_update_time = time.time()

    def get_local_position(self):
        with self._lock:
            return self.local_position

    def update_world(self, scene_id, player_id, player_uuid, nearby_entities):
        with self._lock:
            self.scene_id = scene_id
            self.player_id = player_id
            self.player_uuid = player_uuid
            self.nearby_entities = nearby_entities

    def get_world(self):
        with self._lock:
            return self.scene_id, self.player_id, self.player_uuid, dict(self.nearby_entities)

    def update_combat_state(self, value):
        with self._lock:
            self.combat_state = int(value)
            self.combat_state_update_time = time.time()

    def get_combat_state(self):
        with self._lock:
            return self.combat_state
