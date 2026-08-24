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
        self.actor_state = None
        self.actor_state_update_time = 0.0
        self.skill_cooldowns = {}
        self.player_attributes = {}
        self.fight_resource_ids = []
        self.fight_resources = {}
        self.temp_attributes = {}
        self.monitor_update_time = 0.0

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

    def update_actor_state(self, actor_state):
        with self._lock:
            self.actor_state = int(actor_state)
            self.actor_state_update_time = time.time()

    def get_actor_state(self):
        with self._lock:
            return self.actor_state

    def update_monitor_state(self, snapshot):
        with self._lock:
            self.player_attributes = {
                int(key): int(value)
                for key, value in snapshot.get("player_attributes", {}).items()
            }
            self.skill_cooldowns = {
                int(key): dict(value)
                for key, value in snapshot.get("skill_cooldowns", {}).items()
            }
            self.fight_resource_ids = list(snapshot.get("fight_resource_ids", ()))
            self.fight_resources = {
                int(key): int(value)
                for key, value in snapshot.get("fight_resources", {}).items()
            }
            self.temp_attributes = {
                int(key): int(value)
                for key, value in snapshot.get("temp_attributes", {}).items()
            }
            self.monitor_update_time = time.time()

    def get_skill_cooldowns(self):
        with self._lock:
            return {key: dict(value) for key, value in self.skill_cooldowns.items()}

    def get_player_attributes(self):
        with self._lock:
            return dict(self.player_attributes)

    def get_player_attribute(self, attr_id, default=0):
        with self._lock:
            return int(self.player_attributes.get(int(attr_id), default))

    def get_fight_resources(self):
        with self._lock:
            return dict(self.fight_resources)

    def get_fight_resource_layout(self):
        with self._lock:
            return list(self.fight_resource_ids)

    def get_fight_resource_layout(self):
        with self._lock:
            return list(self.fight_resource_ids)

    def get_temp_attributes(self):
        with self._lock:
            return dict(self.temp_attributes)

    def get_skill_enhancement(self, enhancement_id):
        """Return a synchronized enhancement temporary-attribute value."""
        with self._lock:
            return int(self.temp_attributes.get(int(enhancement_id), 0))

    def get_entity_buffs(self, entity_uuid=None):
        with self._lock:
            if entity_uuid is not None:
                entity = self.nearby_entities.get(int(entity_uuid), {})
                return {
                    key: dict(value)
                    for key, value in entity.get("buffs", {}).items()
                }
            return {
                uuid: {
                    key: dict(value)
                    for key, value in entity.get("buffs", {}).items()
                }
                for uuid, entity in self.nearby_entities.items()
                if entity.get("buffs")
            }
