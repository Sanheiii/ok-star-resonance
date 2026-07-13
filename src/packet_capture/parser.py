"""Star Resonance packet framing and local-player transform decoder.

Only protobuf declarations are intentionally external. Put protoc's Python
output in ``src/packet_capture/proto``; see that directory's README.
"""

from __future__ import annotations

import importlib
import logging
import struct
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

WORLD_NTF_SERVICE_ID = 1_664_308_034
MSG_SYNC_CONTAINER_DATA = 0x15
MSG_SYNC_NEAR_DELTA_INFO = 0x2D
MSG_SYNC_TO_ME_DELTA_INFO = 0x2E
ATTR_FACING = 0x32
ATTR_POSITION = 0x34
ENTITY_TYPE_CHAR = 10
MAX_FRAME_SIZE = 10 * 1024 * 1024


def _load_proto_module():
    for name in (
        "src.packet_capture.proto.blueprotobuf_pb2",
        "src.packet_capture.proto.blueprotobuf_package_pb2",
        "src.packet_capture.proto.BlueProtobuf_pb2",
    ):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


def _present(message, *names):
    """Return a present protobuf field across proto2/proto3 generators."""
    if message is None:
        return None
    for name in names:
        if not hasattr(message, name):
            continue
        try:
            return getattr(message, name) if message.HasField(name) else None
        except (ValueError, AttributeError):
            value = getattr(message, name, None)
            return value if value is not None else None
    return None


def _decode_varint(data):
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
        self.position = None
        self.facing = None
        self._proto = _load_proto_module()
        self._warned_proto = False

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
        return (self.position, self.facing) if changed and self.position is not None else None

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
            elif kind == 2 and len(payload) >= 16:
                service_id = int.from_bytes(payload[:8], "big")
                method_id = int.from_bytes(payload[12:16], "big")
                body = payload[16:]
                body = self._decompress(body) if compressed else body
                if service_id == WORLD_NTF_SERVICE_ID and body is not None:
                    changed |= self._decode_notify(method_id, body)
            offset += size
        return changed

    @staticmethod
    def _decompress(data):
        try:
            import zstandard
            return zstandard.ZstdDecompressor().decompress(data)
        except Exception as exc:
            logger.debug("zstd decompression failed: %s", exc)
            return None

    def _decode_notify(self, method_id, body):
        message_name = {
            MSG_SYNC_CONTAINER_DATA: "SyncContainerData",
            MSG_SYNC_TO_ME_DELTA_INFO: "SyncToMeDeltaInfo",
            MSG_SYNC_NEAR_DELTA_INFO: "SyncNearDeltaInfo",
        }.get(method_id)
        message_class = getattr(self._proto, message_name, None) if message_name else None
        if message_class is None:
            return False
        message = message_class()
        try:
            message.ParseFromString(body)
        except Exception as exc:
            logger.debug("failed to decode %s: %s", message_name, exc)
            return False
        if method_id == MSG_SYNC_CONTAINER_DATA:
            data = _present(message, "v_data", "VData")
            char_id = _present(data, "char_id", "CharId")
            if char_id is not None and not isinstance(char_id, int):
                char_id = char_id[0] if len(char_id) == 1 else None
            if char_id:
                self.local_player_uuid = (int(char_id) << 16) | (ENTITY_TYPE_CHAR << 6)
            return False
        if method_id == MSG_SYNC_TO_ME_DELTA_INFO:
            delta_info = _present(message, "delta_info", "DeltaInfo")
            if delta_info is None:
                return False
            uuid = _present(delta_info, "uuid", "Uuid")
            if uuid:
                self.local_player_uuid = int(uuid)
            return self._decode_delta(_present(delta_info, "base_delta", "BaseDelta"), force_local=True)
        changed = False
        deltas = _present(message, "delta_infos", "DeltaInfos") or ()
        for delta in deltas:
            if self.local_player_uuid and _present(delta, "uuid", "Uuid") == self.local_player_uuid:
                changed |= self._decode_delta(delta, force_local=True)
        return changed

    def _decode_delta(self, delta, force_local=False):
        if delta is None:
            return False
        uuid = _present(delta, "uuid", "Uuid")
        if not force_local and (not self.local_player_uuid or uuid != self.local_player_uuid):
            return False
        attrs = _present(delta, "attrs", "Attrs")
        changed = False
        attr_items = _present(attrs, "attrs", "Attrs") or ()
        for attr in attr_items:
            attr_id = _present(attr, "id", "Id")
            raw = _present(attr, "raw_data", "RawData")
            if attr_id == ATTR_POSITION and raw:
                position_class = getattr(self._proto, "Position", None)
                if position_class is not None:
                    position = position_class()
                    try:
                        position.ParseFromString(raw)
                        values = tuple(
                            float(_present(position, axis, axis.upper()) or 0.0)
                            for axis in ("x", "y", "z")
                        )
                        if values != self.position:
                            self.position = values
                            changed = True
                    except Exception as exc:
                        logger.debug("failed to decode position: %s", exc)
            elif attr_id == ATTR_FACING and raw is not None:
                raw_facing = _decode_varint(raw)
                if raw_facing is not None:
                    facing = (raw_facing / 100.0) % 360.0
                    if facing != self.facing:
                        self.facing = facing
                        changed = True
        return changed
