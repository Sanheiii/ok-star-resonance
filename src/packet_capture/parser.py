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
TEAM_NTF_SERVICE_ID = 966_773_353
MSG_NEW_MOVE = 0x20005
MSG_ENTER_SCENE = 0x03
MSG_SYNC_NEAR_ENTITIES = 0x06
MSG_SYNC_CONTAINER_DATA = 0x15
MSG_SYNC_NEAR_DELTA_INFO = 0x2D
MSG_SYNC_TO_ME_DELTA_INFO = 0x2E
MSG_UPDATE_TEAM_INFO = 0x01
MSG_UPDATE_TEAM_MEMBER_INFO = 0x02
MSG_JOIN_TEAM = 0x03
MSG_LEAVE_TEAM = 0x04
MSG_TEAM_DISSOLVE = 0x0D
ATTR_SCENE_BASIC_ID = 0x155
ATTR_ENTITY_ID = 0x0A
ATTR_FACING = 0x32
ATTR_POSITION = 0x34
ATTR_COMBAT_STATE = 104
ATTR_ACTOR_STATE = 11
ATTR_CURRENT_HP = 0x2C2E
ATTR_MAX_HP = 0x2C38
ATTR_PROFESSION_ID = 0xDC
ATTR_FIGHT_RESOURCE_IDS = 0xC351
ATTR_FIGHT_RESOURCES = 0xC352
ATTR_SKILL_CD = 0x2DE6
ATTR_SKILL_CD_PCT = 0x2DF0
ATTR_CD_ACCELERATE_PCT = 0x2EB8
# Integer attributes identified by resonance-logs-cn. Special structured
# payloads such as position and fight-resource arrays are intentionally absent.
KNOWN_PLAYER_INTEGER_ATTR_IDS = {
    0x01, 0x0A, 0x0B, 0x1E, 0x32, 0x33, 0x35, 0x46, 0x47, 0x5B,
    0x64, 0x65, 0x67, 0x68, 0x6A, 0x6C, 0x6F, 0x71, 0x72, 0x74,
    0x76, 0x78, 0x79, 0xB6, ATTR_PROFESSION_ID, 0xE2, 0xF9, 0x105, 0x106,
    0x107, 0x108, 0x226, 0x228, 0x22A, 0x22D, 0x2710, 0x272E,
    0x274C, 0x2B66, 0x2B7A, 0x2B84, 0x2B8E, 0x2C2E, 0x2C38,
    0x2C39, 0x2C3C, 0x2C3D, 0x2C42, 0x2C43, 0x2C46, 0x2CB0,
    0x2DC8, 0x2DD2, ATTR_SKILL_CD, ATTR_SKILL_CD_PCT,
    ATTR_CD_ACCELERATE_PCT, 0x3372, 0x3373, 0x3374, 0x64696D,
    0x646D6C, 0xEA92, 0x543CD3C6,
}
BUFF_EVENT_REMOVE = 2
BUFF_EFFECT_ADD = 18
BUFF_EFFECT_CHANGE = 19


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


def _decode_varints(data):
    """Decode the packed-varint arrays used by fight-resource attributes."""
    # rawData contains a tiny protobuf message whose field 1 is a packed
    # repeated int64: 0x0a, byte length, then the packed values.
    if not data or data[0] != 0x0A:
        return None
    length = _decode_varint(data[1:])
    if length is None:
        return None
    length_size = 1
    while 1 + length_size <= len(data) and data[length_size] & 0x80:
        length_size += 1
    start = 1 + length_size
    if start + length > len(data):
        return None
    data = data[start:start + length]
    values = []
    offset = 0
    while offset < len(data):
        value = 0
        for shift in range(0, 70, 7):
            byte = data[offset]
            offset += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                values.append(value)
                break
            if offset >= len(data):
                return None
        else:
            return None
    return values


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
        self.team_member_uuids = set()
        self.metadata_revision = 0
        self.server_position = None
        self.facing = None
        self.local_position = None
        self.local_position_revision = 0
        self.combat_state = None
        self.combat_state_revision = 0
        self.actor_state = None
        self.actor_state_revision = 0
        self.skill_cooldowns = {}
        self.player_attributes = {}
        self.fight_resource_ids = []
        self.fight_resources = {}
        self.temp_attributes = {}
        self.monitor_revision = 0
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
                    elif service_id == TEAM_NTF_SERVICE_ID:
                        self._decode_team_notify(method_id, body)
                    elif service_id == WORLD_CALL_SERVICE_ID and method_id == MSG_NEW_MOVE:
                        self._decode_new_move(body)
            offset += size
        return changed

    def _decode_team_notify(self, method_id, body):
        message_name = {
            MSG_UPDATE_TEAM_INFO: "NoticeUpdateTeamInfo",
            MSG_UPDATE_TEAM_MEMBER_INFO: "NoticeUpdateTeamMemberInfo",
            MSG_JOIN_TEAM: "NotifyJoinTeam",
            MSG_LEAVE_TEAM: "NotifyLeaveTeam",
            MSG_TEAM_DISSOLVE: "NoticeTeamDissolve",
        }.get(method_id)
        message_class = getattr(self._proto, message_name, None) if message_name else None
        if message_class is None:
            return False
        message = message_class()
        try:
            message.ParseFromString(body)
        except Exception as exc:
            logger.warning(f"failed to decode {message_name}: {exc}")
            return False

        previous = set(self.team_member_uuids)
        if method_id == MSG_TEAM_DISSOLVE:
            self.team_member_uuids.clear()
        elif not message.HasField("vRequest"):
            return False
        elif method_id == MSG_JOIN_TEAM:
            self.team_member_uuids.clear()
            if message.vRequest.HasField("baseInfo"):
                self._add_team_member(message.vRequest.baseInfo.leaderId)
            for member in message.vRequest.memberData:
                self._add_team_member(member.charId)
            for char_id, member in message.vRequest.memberSyncDatas.items():
                self._add_team_member(char_id)
                self._add_team_member(member.charId)
        elif method_id == MSG_UPDATE_TEAM_INFO:
            if message.vRequest.HasField("baseInfo"):
                self._add_team_member(message.vRequest.baseInfo.leaderId)
        elif method_id == MSG_UPDATE_TEAM_MEMBER_INFO:
            for member in message.vRequest.teamMemberSocialDatas:
                self._add_team_member(member.charId)
            for member in message.vRequest.teamMemberSyncDatas:
                self._add_team_member(member.charId)
        elif method_id == MSG_LEAVE_TEAM:
            member_uuid = self._player_uuid(message.vRequest.charId)
            if member_uuid == self.local_player_uuid:
                self.team_member_uuids.clear()
            else:
                self.team_member_uuids.discard(member_uuid)

        if previous != self.team_member_uuids:
            self.metadata_revision += 1
            return True
        return False

    def _add_team_member(self, char_id):
        if char_id:
            self.team_member_uuids.add(self._player_uuid(char_id))

    @staticmethod
    def _player_uuid(char_id):
        return (
            (int(char_id) << ENTITY_UID_SHIFT)
            | (ENTITY_TYPE_CHAR << ENTITY_TYPE_SHIFT)
        )

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
                    entity_uuid = int(entity.uuid)
                    removed |= self.nearby_entities.pop(entity_uuid, None) is not None
                    self.temp_attributes.pop(entity_uuid, None)
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
            self._record_skill_cooldowns(delta_info.syncSkillCDs)
            if not delta_info.HasField("baseDelta"):
                return False
            self._record_entity_delta(delta_info.baseDelta, self.local_player_uuid)
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
        self.skill_cooldowns.clear()
        self.player_attributes.clear()
        self.fight_resource_ids.clear()
        self.fight_resources.clear()
        self.temp_attributes.clear()
        self.monitor_revision += 1
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
                self._record_player_attributes(player.attrs)
                self._decode_combat_state_attr(player.attrs)
                self._decode_actor_state_attr(player.attrs)
                changed |= self._decode_transform_attrs(
                    player.attrs, include_position_direction=True
                )
            self._record_appeared_entity(player)
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
        actor_state = previous.get("actor_state")
        combat_state = previous.get("combat_state")
        current_hp = previous.get("current_hp")
        max_hp = previous.get("max_hp")
        if entity.HasField("attrs"):
            for attr in entity.attrs.attrs:
                if not attr.HasField("id"):
                    continue
                raw_data = attr.rawData if attr.HasField("rawData") else b""
                if attr.id == ATTR_POSITION and raw_data:
                    value = self._proto.Position()
                    try:
                        value.ParseFromString(raw_data)
                        position = (
                            float(value.x), float(value.y), float(value.z)
                        )
                    except Exception as exc:
                        logger.debug(f"failed to decode appeared entity position: {exc}")
                elif attr.id == ATTR_FACING:
                    raw_facing = _decode_varint(raw_data)
                    if raw_facing is not None:
                        facing = (raw_facing / 100.0) % 360.0
                elif attr.id == ATTR_ENTITY_ID:
                    raw_attr_id = _decode_varint(raw_data)
                    if raw_attr_id is not None:
                        attr_id = raw_attr_id
                elif attr.id == ATTR_ACTOR_STATE:
                    actor_state = _decode_varint(raw_data)
                elif attr.id == ATTR_COMBAT_STATE:
                    combat_state = _decode_varint(raw_data)
                elif attr.id == ATTR_CURRENT_HP:
                    current_hp = _decode_varint(raw_data)
                elif attr.id == ATTR_MAX_HP:
                    max_hp = _decode_varint(raw_data)
        entity_type = int(entity.entType) if entity.HasField("entType") else None
        self._store_entity(
            entity_uuid,
            position,
            facing,
            entity_type,
            attr_id,
            actor_state,
            combat_state,
            current_hp,
            max_hp,
        )
        if entity.HasField("tempAttrs"):
            self._record_temp_attrs(entity_uuid, entity.tempAttrs)
        if entity.HasField("attrs") and entity_uuid == self.local_player_uuid:
            self._record_player_attributes(entity.attrs)
            self._record_fight_resources(entity.attrs)
        if entity.HasField("buffInfos"):
            self._replace_buffs(entity_uuid, entity.buffInfos)
        if entity.HasField("buffEffect"):
            self._apply_buff_effects(entity_uuid, entity.buffEffect)

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

    def _record_entity_delta(self, delta, fallback_uuid=None):
        if not delta.HasField("uuid") and not fallback_uuid:
            return
        entity_uuid = (
            int(delta.uuid) if delta.HasField("uuid") else int(fallback_uuid)
        )
        if delta.HasField("tempAttrs"):
            self._record_temp_attrs(entity_uuid, delta.tempAttrs)
        if delta.HasField("buffEffect") and delta.buffEffect:
            effects = self._proto.BuffEffectSync()
            try:
                effects.ParseFromString(delta.buffEffect)
                self._apply_buff_effects(entity_uuid, effects)
            except Exception as exc:
                logger.debug(f"failed to decode buff effects: {exc}")
        if not delta.HasField("attrs"):
            return
        if entity_uuid == self.local_player_uuid:
            self._record_player_attributes(delta.attrs)
            self._record_fight_resources(delta.attrs)
        previous = self.nearby_entities.get(entity_uuid, {})
        position = previous.get("position")
        facing = previous.get("facing")
        attr_id = previous.get("attr_id")
        actor_state = previous.get("actor_state")
        combat_state = previous.get("combat_state")
        current_hp = previous.get("current_hp")
        max_hp = previous.get("max_hp")
        changed = False
        for attr in delta.attrs.attrs:
            if not attr.HasField("id"):
                continue
            raw_data = attr.rawData if attr.HasField("rawData") else b""
            if attr.id == ATTR_POSITION and raw_data:
                value = self._proto.Position()
                try:
                    value.ParseFromString(raw_data)
                    position = (float(value.x), float(value.y), float(value.z))
                    changed = True
                except Exception as exc:
                    logger.debug(f"failed to decode entity position: {exc}")
            elif attr.id == ATTR_FACING:
                raw_facing = _decode_varint(raw_data)
                if raw_facing is not None:
                    facing = (raw_facing / 100.0) % 360.0
                    changed = True
            elif attr.id == ATTR_ENTITY_ID:
                raw_attr_id = _decode_varint(raw_data)
                if raw_attr_id is not None and raw_attr_id != attr_id:
                    attr_id = raw_attr_id
                    changed = True
            elif attr.id == ATTR_ACTOR_STATE:
                value = _decode_varint(raw_data)
                if value is not None and value != actor_state:
                    actor_state = value
                    changed = True
            elif attr.id == ATTR_COMBAT_STATE:
                value = _decode_varint(raw_data)
                if value is not None and value != combat_state:
                    combat_state = value
                    changed = True
            elif attr.id == ATTR_CURRENT_HP:
                value = _decode_varint(raw_data)
                if value is not None and value != current_hp:
                    current_hp = value
                    changed = True
            elif attr.id == ATTR_MAX_HP:
                value = _decode_varint(raw_data)
                if value is not None and value != max_hp:
                    max_hp = value
                    changed = True
        if changed:
            self._store_entity(
                entity_uuid,
                position,
                facing,
                attr_id=attr_id,
                actor_state=actor_state,
                combat_state=combat_state,
                current_hp=current_hp,
                max_hp=max_hp,
            )

    def _store_entity(
        self,
        entity_uuid,
        position,
        facing,
        entity_type=None,
        attr_id=None,
        actor_state=None,
        combat_state=None,
        current_hp=None,
        max_hp=None,
    ):
        if not entity_uuid:
            return
        entity_uuid = int(entity_uuid)
        previous = self.nearby_entities.get(entity_uuid, {})
        if entity_type is None:
            entity_type = (entity_uuid >> ENTITY_TYPE_SHIFT) & ENTITY_TYPE_MASK
        if attr_id is None:
            attr_id = previous.get("attr_id")
        if actor_state is None:
            actor_state = previous.get("actor_state")
        if combat_state is None:
            combat_state = previous.get("combat_state")
        if current_hp is None:
            current_hp = previous.get("current_hp")
        if max_hp is None:
            max_hp = previous.get("max_hp")
        self.nearby_entities[entity_uuid] = {
            "position": position,
            "facing": facing,
            "entity_type": entity_type,
            "attr_id": attr_id,
            "actor_state": actor_state,
            "combat_state": combat_state,
            "in_combat": bool(combat_state),
            "current_hp": current_hp,
            "max_hp": max_hp,
            "buffs": previous.get("buffs", {}),
            "temp_attributes": previous.get("temp_attributes", {}),
            "is_dead": actor_state == ActorState.DEAD,
            "is_summoned": bool(entity_uuid & (1 << ENTITY_SUMMON_BIT)),
            "is_client_created": bool(entity_uuid & (1 << ENTITY_CLIENT_BIT)),
            "updated_at": time.time(),
        }
        self.metadata_revision += 1

    def _record_player_attributes(self, collection):
        changed = False
        for attr in collection.attrs:
            if not attr.HasField("id") or attr.id not in KNOWN_PLAYER_INTEGER_ATTR_IDS:
                continue
            raw_data = attr.rawData if attr.HasField("rawData") else b""
            value = _decode_varint(raw_data)
            if value is None:
                continue
            # Integer attributes are encoded using protobuf int64 semantics.
            if value >= 1 << 63:
                value -= 1 << 64
            attr_id = int(attr.id)
            value = int(value)
            if self.player_attributes.get(attr_id) != value:
                self.player_attributes[attr_id] = value
                changed = True
        if changed:
            self.monitor_revision += 1

    def _record_skill_cooldowns(self, cooldowns):
        changed = False
        received_at = time.time()
        for cooldown in cooldowns:
            if not cooldown.HasField("skillLevelId"):
                continue
            skill_level_id = int(cooldown.skillLevelId)
            value = {
                "skill_level_id": skill_level_id,
                "skill_id": skill_level_id // 100,
                "begin_time": (
                    int(cooldown.beginTime) if cooldown.HasField("beginTime") else 0
                ),
                "duration": (
                    int(cooldown.duration) if cooldown.HasField("duration") else 0
                ),
                "skill_cd_type": (
                    int(cooldown.skillCdType)
                    if cooldown.HasField("skillCdType") else 0
                ),
                "valid_cd_time": (
                    int(cooldown.validCdTime)
                    if cooldown.HasField("validCdTime") else 0
                ),
                "received_at": received_at,
            }
            self.skill_cooldowns[skill_level_id] = value
            changed = True
        if changed:
            self.monitor_revision += 1

    def _record_fight_resources(self, collection):
        layout = None
        values = None
        for attr in collection.attrs:
            if not attr.HasField("id"):
                continue
            raw = attr.rawData if attr.HasField("rawData") else b""
            if attr.id == ATTR_FIGHT_RESOURCE_IDS:
                layout = _decode_varints(raw)
            elif attr.id == ATTR_FIGHT_RESOURCES:
                values = _decode_varints(raw)
        changed = False
        if layout is not None:
            decimal_layout = [int(value) for value in layout]
            logger.info(
                "fight resource layout stub: source=server, "
                f"decimal={decimal_layout}, "
                f"hexadecimal={[f'0x{value:X}' for value in decimal_layout]}"
            )
        if layout is not None and layout != self.fight_resource_ids:
            # Wire order is significant: resource values are positional.
            self.fight_resource_ids = [int(value) for value in layout]
            self.fight_resources = {
                key: value for key, value in self.fight_resources.items()
                if key in self.fight_resource_ids
            }
            changed = True
        if values is not None and self.fight_resource_ids:
            updated = dict(zip(self.fight_resource_ids, map(int, values)))
            if any(
                self.fight_resources.get(key) != value
                for key, value in updated.items()
            ):
                self.fight_resources.update(updated)
                changed = True
        if changed:
            self.monitor_revision += 1

    def set_fight_resource_layout(self, layout):
        """Install a caller-supplied fallback layout when none was captured."""
        if self.fight_resource_ids:
            return False
        normalized = [int(resource_id) for resource_id in layout]
        if not normalized:
            return False
        self.fight_resource_ids = normalized
        self.fight_resources = {
            key: value for key, value in self.fight_resources.items()
            if key in self.fight_resource_ids
        }
        self.monitor_revision += 1
        return True

    def set_fight_resource_layout(self, layout):
        """Install a caller-supplied fallback layout when none was captured."""
        if self.fight_resource_ids:
            return False
        normalized = [int(resource_id) for resource_id in layout]
        if not normalized:
            return False
        self.fight_resource_ids = normalized
        self.fight_resources = {
            key: value for key, value in self.fight_resources.items()
            if key in self.fight_resource_ids
        }
        self.monitor_revision += 1
        return True

    def _record_temp_attrs(self, entity_uuid, collection):
        entity_uuid = int(entity_uuid)
        current = dict(self.temp_attributes.get(entity_uuid, {}))
        changed = False
        for attr in collection.attrs:
            if not attr.HasField("id"):
                continue
            value = int(attr.value) if attr.HasField("value") else 0
            if current.get(int(attr.id)) != value:
                current[int(attr.id)] = value
                changed = True
        if not changed:
            return
        self.temp_attributes[entity_uuid] = current
        if entity_uuid in self.nearby_entities:
            self.nearby_entities[entity_uuid]["temp_attributes"] = dict(current)
            self.metadata_revision += 1
        self.monitor_revision += 1

    @staticmethod
    def _buff_value(info):
        return {
            "instance_id": int(info.buffUuid),
            "base_id": int(info.baseId) if info.HasField("baseId") else 0,
            "level": int(info.level) if info.HasField("level") else 0,
            "host_uuid": int(info.hostUuid) if info.HasField("hostUuid") else None,
            "source_uuid": int(info.fireUuid) if info.HasField("fireUuid") else None,
            "layer": int(info.layer) if info.HasField("layer") else 0,
            "count": int(info.count) if info.HasField("count") else 0,
            "duration": int(info.duration) if info.HasField("duration") else 0,
            "create_time": int(info.createTime) if info.HasField("createTime") else 0,
        }

    def _replace_buffs(self, fallback_uuid, sync):
        target_uuid = int(sync.uuid) if sync.HasField("uuid") else int(fallback_uuid)
        buffs = {
            int(info.buffUuid): self._buff_value(info)
            for info in sync.buffInfos if info.HasField("buffUuid")
        }
        self._set_entity_buffs(target_uuid, buffs)

    def _apply_buff_effects(self, fallback_uuid, sync):
        sync_uuid = int(sync.uuid) if sync.HasField("uuid") else int(fallback_uuid)
        for effect in sync.buffEffects:
            if not effect.HasField("buffUuid"):
                continue
            target_uuid = int(effect.hostUuid) if effect.HasField("hostUuid") else sync_uuid
            buffs = dict(self.nearby_entities.get(target_uuid, {}).get("buffs", {}))
            instance_id = int(effect.buffUuid)
            for logic in effect.logicEffect:
                if not logic.HasField("rawData"):
                    continue
                effect_type = int(logic.effectType) if logic.HasField("effectType") else 0
                if effect_type == BUFF_EFFECT_ADD:
                    info = self._proto.BuffInfo()
                    info.ParseFromString(logic.rawData)
                    if info.HasField("buffUuid"):
                        buffs[int(info.buffUuid)] = self._buff_value(info)
                elif effect_type == BUFF_EFFECT_CHANGE and instance_id in buffs:
                    change = self._proto.BuffChange()
                    change.ParseFromString(logic.rawData)
                    value = dict(buffs[instance_id])
                    for field_name in ("layer", "duration", "createTime"):
                        if change.HasField(field_name):
                            key = {"createTime": "create_time"}.get(
                                field_name, field_name
                            )
                            value[key] = int(getattr(change, field_name))
                    buffs[instance_id] = value
            if effect.HasField("type") and effect.type == BUFF_EVENT_REMOVE:
                buffs.pop(instance_id, None)
            self._set_entity_buffs(target_uuid, buffs)

    def _set_entity_buffs(self, entity_uuid, buffs):
        entity_uuid = int(entity_uuid)
        if entity_uuid not in self.nearby_entities:
            self._store_entity(entity_uuid, None, None)
        if self.nearby_entities[entity_uuid].get("buffs") == buffs:
            return
        self.nearby_entities[entity_uuid]["buffs"] = buffs
        self.nearby_entities[entity_uuid]["updated_at"] = time.time()
        self.metadata_revision += 1
        self.monitor_revision += 1

    def monitor_state(self):
        local_temp = self.temp_attributes.get(self.local_player_uuid, {})
        return {
            "player_attributes": dict(self.player_attributes),
            "skill_cooldowns": {
                key: dict(value) for key, value in self.skill_cooldowns.items()
            },
            "fight_resource_ids": list(self.fight_resource_ids),
            "fight_resources": dict(self.fight_resources),
            "temp_attributes": dict(local_temp),
        }

    def world_state(self):
        return self.scene_id, self.player_id, self.local_player_uuid, {
            uuid: {**entity, "is_teammate": uuid in self.team_member_uuids}
            for uuid, entity in self.nearby_entities.items()
        }
