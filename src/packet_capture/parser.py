"""Star Resonance packet framing and local-player transform decoder.

Only protobuf declarations are intentionally external. Put protoc's Python
output in ``src/packet_capture/proto``; see that directory's README.
"""

from __future__ import annotations

import io
import importlib
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum

from ok import Logger

logger = Logger.get_logger(__name__)

WORLD_NTF_SERVICE_ID = 1_664_308_034
WORLD_CALL_SERVICE_ID = 103_198_054
MSG_NEW_MOVE = 0x20005
MSG_ENTER_SCENE = 0x03
MSG_SYNC_NEAR_ENTITIES = 0x06
MSG_SYNC_CONTAINER_DATA = 0x15
MSG_SYNC_NEAR_DELTA_INFO = 0x2D
MSG_SYNC_TO_ME_DELTA_INFO = 0x2E
ATTR_SCENE_BASIC_ID = 0x155
ATTR_ENTITY_ID = 0x0A
ATTR_FACING = 0x32
ATTR_POSITION = 0x34
ATTR_COMBAT_STATE = 104
ATTR_ACTOR_STATE = 11


class ActorState(IntEnum):
    DEFAULT = 0
    SINGING = 1
    SKILL = 2
    JUMP = 3
    RUSH = 4
    CLIMB = 5
    SWIM = 6
    FISHING = 7
    ACTION = 8
    DEAD = 9
    STIFF = 10
    SWIM_STIFF = 11
    BORN = 12
    TELEPORT = 13
    FALL = 14
    FLOW = 16
    GLIDE = 17
    PEDAL_WALL = 18
    FALL_TELEPORT = 19
    SELF_PHOTO = 20
    COLLECTION = 21
    RESET = 22
    BREAKING = 23
    WEAKNESS = 24
    FRACTURE = 25
    ABNORMAL = 26
    RESURRECTION = 27
    INTERACTION = 28
    SCENE_INTERACTION = 29
    TUNNEL_FLY = 30
    LEVITATION = 31
    HOMELAND_EDIT = 32
    RIDE = 33
    RIDE_CONTROL = 34
    INSTRUMENT = 35
    FIXED = 36
    ALL = 37


ENTITY_TYPE_CHAR = 10
ENTITY_TYPE_SHIFT = 6
ENTITY_UID_SHIFT = 16
ENTITY_TYPE_MASK = 0xFF
ENTITY_SUMMON_BIT = 15
ENTITY_CLIENT_BIT = 14
MAX_FRAME_SIZE = 10 * 1024 * 1024


def _load_proto_module():
    try:
        return importlib.import_module("src.packet_capture.proto.BlueProtobuf_pb2")
    except ImportError:
        return None


def _decode_varint(data):
    # Attribute values use the protobuf default representation for zero: an
    # explicitly present rawData field may therefore contain no bytes.
    if not data:
        return 0
    value = 0
    for index, byte in enumerate(data[:10]):
        value |= (byte & 0x7F) << (index * 7)
        if byte < 0x80:
            return value
    return None


@dataclass
class _TcpStream:
    next_sequence: int | None = None
    pending: dict[int, bytes] = field(default_factory=dict)
    application: bytearray = field(default_factory=bytearray)
    last_seen: float = field(default_factory=time.monotonic)

    def add(self, sequence, payload, syn=False):
        if syn:
            self.next_sequence = (sequence + 1) & 0xFFFFFFFF
            self.pending.clear()
            self.application.clear()
        if not payload:
            return
        if self.next_sequence is None:
            self.next_sequence = sequence
        delta = (sequence - self.next_sequence) & 0xFFFFFFFF
        if delta >= 0x80000000:  # retransmission/overlap before next_sequence
            overlap = (self.next_sequence - sequence) & 0xFFFFFFFF
            if overlap >= len(payload):
                return
            payload = payload[overlap:]
            sequence = self.next_sequence
        self.pending.setdefault(sequence, payload)
        while self.next_sequence in self.pending:
            chunk = self.pending.pop(self.next_sequence)
            self.application.extend(chunk)
            self.next_sequence = (self.next_sequence + len(chunk)) & 0xFFFFFFFF
        self.last_seen = time.monotonic()

    def frames(self):
        while len(self.application) >= 4:
            size = int.from_bytes(self.application[:4], "big")
            if size < 6 or size > MAX_FRAME_SIZE:
                # Capture may start mid-stream. Scan forward until a plausible
                # application frame boundary is found.
                del self.application[0]
                continue
            if len(self.application) < size:
                break
            frame = bytes(self.application[:size])
            del self.application[:size]
            yield frame


class GamePacketParser:
    def __init__(self):
        self.datalink = 1  # DLT_EN10MB
        self.streams = {}
        self.local_player_uuid = None
        self.player_id = None
        self.scene_id = None
        self.scene_guid = None
        self.connect_guid = None
        self.nearby_entities = {}
        self.metadata_revision = 0
        self.server_position = None
        self.facing = None
        self.local_position = None
        self.local_position_revision = 0
        self.combat_state = None
        self.combat_state_revision = 0
        self.actor_state = None
        self.actor_state_revision = 0
        self._proto = _load_proto_module()
        self._warned_proto = False

    def reset_transport(self):
        """Discard TCP reassembly state before starting a new capture session."""
        self.streams.clear()

    def set_datalink(self, datalink):
        self.datalink = datalink

    def feed_packet(self, packet):
        if self._proto is None:
            self._proto = _load_proto_module()
            if self._proto is None:
                if not self._warned_proto:
                    logger.warning("protobuf generated module is not installed; packet decoding is disabled")
                    self._warned_proto = True
                return None
        tcp = self._tcp_payload(packet)
        if tcp is None:
            return None
        flow, sequence, payload, syn, closed = tcp
        stream = self.streams.setdefault(flow, _TcpStream())
        stream.add(sequence, payload, syn)
        changed = False
        for frame in stream.frames():
            changed |= self._process_fragments(frame)
        if closed:
            self.streams.pop(flow, None)
        if len(self.streams) > 128:
            cutoff = time.monotonic() - 90
            self.streams = {key: value for key, value in self.streams.items() if value.last_seen >= cutoff}
        return (self.server_position, self.facing) if changed and self.server_position is not None else None

    def _tcp_payload(self, packet):
        if self.datalink == 1:  # Ethernet, including one or more VLAN tags
            if len(packet) < 14:
                return None
            offset = 14
            ether_type = int.from_bytes(packet[12:14], "big")
            while ether_type in (0x8100, 0x88A8, 0x9100):
                if len(packet) < offset + 4:
                    return None
                ether_type = int.from_bytes(packet[offset + 2:offset + 4], "big")
                offset += 4
            if ether_type != 0x0800:
                return None
        elif self.datalink in (0, 108):
            if len(packet) < 4:
                return None
            offset = 4
        elif self.datalink == 12:
            offset = 0
        else:
            return None
        if len(packet) < offset + 20 or packet[offset] >> 4 != 4:
            return None
        ihl = (packet[offset] & 0x0F) * 4
        if ihl < 20 or packet[offset + 9] != 6 or len(packet) < offset + ihl + 20:
            return None
        total_length = int.from_bytes(packet[offset + 2:offset + 4], "big")
        ip_end = min(len(packet), offset + total_length)
        tcp_offset = offset + ihl
        tcp_header = (packet[tcp_offset + 12] >> 4) * 4
        if tcp_header < 20 or tcp_offset + tcp_header > ip_end:
            return None
        source = packet[offset + 12:offset + 16]
        destination = packet[offset + 16:offset + 20]
        source_port, destination_port = struct.unpack_from("!HH", packet, tcp_offset)
        sequence = struct.unpack_from("!I", packet, tcp_offset + 4)[0]
        flags = packet[tcp_offset + 13]
        flow = (source, source_port, destination, destination_port)
        return flow, sequence, packet[tcp_offset + tcp_header:ip_end], bool(flags & 0x02), bool(flags & 0x05)

    def _process_fragments(self, frame):
        changed = False
        offset = 0
        while offset + 6 <= len(frame):
            size = int.from_bytes(frame[offset:offset + 4], "big")
            if size < 6 or offset + size > len(frame):
                break
            fragment_type = int.from_bytes(frame[offset + 4:offset + 6], "big")
            compressed = bool(fragment_type & 0x8000)
            kind = fragment_type & 0x7FFF
            payload = frame[offset + 6:offset + size]
            if kind in (5, 6):
                nested = payload[4:] if len(payload) >= 4 else b""
                nested = self._decompress(nested) if compressed else nested
                if nested is not None:
                    changed |= self._process_fragments(nested)
            elif kind == 1 and len(payload) >= 20:
                service_id = int.from_bytes(payload[:8], "big")
                method_id = int.from_bytes(payload[16:20], "big")
                body = payload[20:]
                body = self._decompress(body) if compressed else body
                if (service_id == WORLD_CALL_SERVICE_ID and method_id == MSG_NEW_MOVE
                        and body is not None):
                    self._decode_new_move(body)
            elif kind == 2 and len(payload) >= 16:
                service_id = int.from_bytes(payload[:8], "big")
                method_id = int.from_bytes(payload[12:16], "big")
                body = payload[16:]
                body = self._decompress(body) if compressed else body
                if body is not None:
                    if service_id == WORLD_NTF_SERVICE_ID:
                        changed |= self._decode_notify(method_id, body)
                    elif service_id == WORLD_CALL_SERVICE_ID and method_id == MSG_NEW_MOVE:
                        self._decode_new_move(body)
            offset += size
        return changed

    def _decode_new_move(self, body):
        message = self._proto.NewMove()
        try:
            message.ParseFromString(body)
        except Exception as exc:
            logger.warning(f"failed to decode NewMove: {exc}")
            return False
        if not message.HasField("info") or not message.info.HasField("destPos"):
            return False
        position = message.info.destPos
        self.local_position = (float(position.x), float(position.y), float(position.z))
        self.local_position_revision += 1
        return True

    @staticmethod
    def _decompress(data):
        try:
            import zstandard
            # Game frames do not always advertise their decompressed size.
            # stream_reader handles those frames, unlike decompress(), which
            # raises "could not determine content size in frame header".
            with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)) as reader:
                return reader.read()
        except Exception as exc:
            logger.warning(f"zstd decompression failed: {exc}")
            return None

    def _decode_notify(self, method_id, body):
        if method_id == MSG_SYNC_NEAR_ENTITIES:
            message_class = getattr(self._proto, "SyncNearEntities", None)
            message_name = "SyncNearEntities"
        else:
            message_name = {
                MSG_ENTER_SCENE: "EnterScene",
                MSG_SYNC_CONTAINER_DATA: "SyncContainerData",
                MSG_SYNC_TO_ME_DELTA_INFO: "SyncToMeDeltaInfo",
                MSG_SYNC_NEAR_DELTA_INFO: "SyncNearDeltaInfo",
            }.get(method_id)
            message_class = (
                getattr(self._proto.WorldNtf, message_name, None)
                if self._proto and message_name else None
            )
        if message_class is None:
            return False
        message = message_class()
        try:
            message.ParseFromString(body)
        except Exception as exc:
            logger.warning(f"failed to decode {message_name}: {exc}")
            return False
        if method_id == MSG_ENTER_SCENE:
            return self._decode_enter_scene(message)
        if method_id == MSG_SYNC_NEAR_ENTITIES:
            for entity in message.appear:
                self._record_appeared_entity(entity)
            removed = False
            for entity in message.disappear:
                if entity.HasField("uuid") and entity.uuid:
                    removed |= (
                        self.nearby_entities.pop(int(entity.uuid), None) is not None
                    )
            if removed:
                self.metadata_revision += 1
            return False
        if method_id == MSG_SYNC_CONTAINER_DATA:
            data = message.vData
            char_id = data.charId
            if char_id:
                self.player_id = int(char_id)
                self.local_player_uuid = (int(char_id) << 16) | (ENTITY_TYPE_CHAR << 6)
            if data.HasField("sceneData"):
                next_scene_id = int(data.sceneData.mapId)
                if self.scene_id is not None and next_scene_id != self.scene_id:
                    self.nearby_entities.clear()
                self.scene_id = next_scene_id
                self.metadata_revision += 1
            if not data.HasField("sceneData") or not data.sceneData.HasField("pos"):
                return False
            changed = self._apply_position(data.sceneData.pos, include_direction=True)
            self._store_entity(self.local_player_uuid, self.server_position, self.facing)
            return changed
        if method_id == MSG_SYNC_TO_ME_DELTA_INFO:
            if not message.HasField("deltaInfo"):
                return False
            delta_info = message.deltaInfo
            if delta_info.HasField("uuid") and delta_info.uuid:
                self.local_player_uuid = int(delta_info.uuid)
            if not delta_info.HasField("baseDelta"):
                return False
            self._record_entity_delta(delta_info.baseDelta)
            return self._decode_delta(delta_info.baseDelta, force_local=True)
        changed = False
        for delta in message.deltaInfos:
            self._record_entity_delta(delta)
            if self.local_player_uuid and delta.HasField("uuid") and delta.uuid == self.local_player_uuid:
                changed |= self._decode_delta(delta, force_local=True)
        return changed

    def _decode_enter_scene(self, message):
        has_info = message.HasField("enterSceneInfo")
        if not has_info:
            return False
        info = message.enterSceneInfo
        has_scene_attrs = info.HasField("sceneAttrs")
        self.nearby_entities.clear()
        self.scene_guid = info.sceneGuid if info.HasField("sceneGuid") else None
        self.connect_guid = info.connectGuid if info.HasField("connectGuid") else None

        if has_scene_attrs:
            scene_id = self._find_varint_attr(info.sceneAttrs, ATTR_SCENE_BASIC_ID)
            if scene_id is not None:
                self.scene_id = int(scene_id)
            else:
                logger.warning(
                    "EnterScene sceneAttrs does not contain "
                    f"AttrSceneBasicId({ATTR_SCENE_BASIC_ID})"
                )

        changed = False
        if info.HasField("playerEnt"):
            player = info.playerEnt
            if player.HasField("uuid") and player.uuid:
                self.local_player_uuid = int(player.uuid)
                self.player_id = self.local_player_uuid >> ENTITY_UID_SHIFT
            if player.HasField("attrs"):
                self._decode_combat_state_attr(player.attrs)
                self._decode_actor_state_attr(player.attrs)
                changed |= self._decode_transform_attrs(
                    player.attrs, include_position_direction=True
                )
            self._store_entity(self.local_player_uuid, self.server_position, self.facing)
        if self.server_position is not None:
            self.local_position = self.server_position
            self.local_position_revision += 1
        self.metadata_revision += 1
        return changed

    @staticmethod
    def _find_varint_attr(collection, attr_id):
        for attr in collection.attrs:
            if attr.HasField("id") and attr.id == attr_id:
                # Protobuf omits fields carrying their default value. The game
                # therefore represents an integer attribute reset to zero as
                # either an empty rawData field or no rawData field at all.
                raw_data = attr.rawData if attr.HasField("rawData") else b""
                return _decode_varint(raw_data)
        return None

    def _decode_transform_attrs(self, collection, include_position_direction=False):
        changed = False
        has_facing_attr = any(
            attr.HasField("id") and attr.id == ATTR_FACING
            and attr.HasField("rawData")
            for attr in collection.attrs
        )
        for attr in collection.attrs:
            attr_id = attr.id if attr.HasField("id") else None
            raw = attr.rawData if attr.HasField("rawData") else None
            if attr_id == ATTR_POSITION and raw:
                position = self._proto.Position()
                try:
                    position.ParseFromString(raw)
                    changed |= self._apply_position(
                        position,
                        include_direction=(include_position_direction and not has_facing_attr),
                    )
                except Exception as exc:
                    logger.debug(f"failed to decode position: {exc}")
            elif attr_id == ATTR_FACING and raw is not None:
                raw_facing = _decode_varint(raw)
                if raw_facing is not None:
                    facing = (raw_facing / 100.0) % 360.0
                    if facing != self.facing:
                        self.facing = facing
                        changed = True
        return changed

    def _decode_combat_state_attr(self, collection):
        value = self._find_varint_attr(collection, ATTR_COMBAT_STATE)
        if value is None:
            return False
        value = int(value)
        if value == self.combat_state:
            return False
        self.combat_state = value
        self.combat_state_revision += 1
        return True

    def _decode_actor_state_attr(self, collection):
        actor_state = self._find_varint_attr(collection, ATTR_ACTOR_STATE)
        if actor_state is None:
            return False
        actor_state = int(actor_state)
        if actor_state == self.actor_state:
            return False
        self.actor_state = actor_state
        self.actor_state_revision += 1
        return True

    def _decode_delta(self, delta, force_local=False):
        if delta is None:
            return False
        uuid = delta.uuid if delta.HasField("uuid") else None
        if not force_local and (not self.local_player_uuid or uuid != self.local_player_uuid):
            return False
        if not delta.HasField("attrs"):
            return False
        self._decode_combat_state_attr(delta.attrs)
        self._decode_actor_state_attr(delta.attrs)
        return self._decode_transform_attrs(delta.attrs)

    def _record_appeared_entity(self, entity):
        if not entity.HasField("uuid") or not entity.uuid:
            return
        entity_uuid = int(entity.uuid)
        previous = self.nearby_entities.get(entity_uuid, {})
        position = previous.get("position")
        facing = previous.get("facing")
        attr_id = previous.get("attr_id")
        if entity.HasField("attrs"):
            for attr in entity.attrs.attrs:
                if not attr.HasField("id") or not attr.HasField("rawData"):
                    continue
                if attr.id == ATTR_POSITION and attr.rawData:
                    value = self._proto.Position()
                    try:
                        value.ParseFromString(attr.rawData)
                        position = (
                            float(value.x), float(value.y), float(value.z)
                        )
                    except Exception as exc:
                        logger.debug(f"failed to decode appeared entity position: {exc}")
                elif attr.id == ATTR_FACING:
                    raw_facing = _decode_varint(attr.rawData)
                    if raw_facing is not None:
                        facing = (raw_facing / 100.0) % 360.0
                elif attr.id == ATTR_ENTITY_ID:
                    raw_attr_id = _decode_varint(attr.rawData)
                    if raw_attr_id is not None:
                        attr_id = raw_attr_id
        entity_type = int(entity.entType) if entity.HasField("entType") else None
        self._store_entity(entity_uuid, position, facing, entity_type, attr_id)

    def _apply_position(self, position, include_direction=False):
        if position is None:
            return False
        coordinates = (position.x, position.y, position.z)
        changed = self._set_server_position(coordinates)
        if include_direction:
            facing = float(position.dir) % 360.0
            if facing != self.facing:
                self.facing = facing
                changed = True
        return changed

    def _set_server_position(self, coordinates):
        values = tuple(float(value) for value in coordinates)
        if values == self.server_position:
            return False
        self.server_position = values
        return True

    def _record_entity_delta(self, delta):
        if not delta.HasField("uuid") or not delta.HasField("attrs"):
            return
        entity_uuid = int(delta.uuid)
        previous = self.nearby_entities.get(entity_uuid, {})
        position = previous.get("position")
        facing = previous.get("facing")
        attr_id = previous.get("attr_id")
        changed = False
        for attr in delta.attrs.attrs:
            if not attr.HasField("id") or not attr.HasField("rawData"):
                continue
            if attr.id == ATTR_POSITION and attr.rawData:
                value = self._proto.Position()
                try:
                    value.ParseFromString(attr.rawData)
                    position = (float(value.x), float(value.y), float(value.z))
                    changed = True
                except Exception as exc:
                    logger.debug(f"failed to decode entity position: {exc}")
            elif attr.id == ATTR_FACING:
                raw_facing = _decode_varint(attr.rawData)
                if raw_facing is not None:
                    facing = (raw_facing / 100.0) % 360.0
                    changed = True
            elif attr.id == ATTR_ENTITY_ID:
                raw_attr_id = _decode_varint(attr.rawData)
                if raw_attr_id is not None and raw_attr_id != attr_id:
                    attr_id = raw_attr_id
                    changed = True
        if changed:
            self._store_entity(entity_uuid, position, facing, attr_id=attr_id)

    def _store_entity(
        self, entity_uuid, position, facing, entity_type=None, attr_id=None
    ):
        if not entity_uuid:
            return
        entity_uuid = int(entity_uuid)
        previous = self.nearby_entities.get(entity_uuid, {})
        if entity_type is None:
            entity_type = (entity_uuid >> ENTITY_TYPE_SHIFT) & ENTITY_TYPE_MASK
        if attr_id is None:
            attr_id = previous.get("attr_id")
        self.nearby_entities[entity_uuid] = {
            "position": position,
            "facing": facing,
            "entity_type": entity_type,
            "attr_id": attr_id,
            "is_summoned": bool(entity_uuid & (1 << ENTITY_SUMMON_BIT)),
            "is_client_created": bool(entity_uuid & (1 << ENTITY_CLIENT_BIT)),
            "updated_at": time.time(),
        }
        self.metadata_revision += 1

    def world_state(self):
        return self.scene_id, self.player_id, self.local_player_uuid, {
            uuid: dict(entity) for uuid, entity in self.nearby_entities.items()
        }
