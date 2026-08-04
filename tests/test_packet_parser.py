import unittest

from src.packet_capture.parser import (
    ActorState,
    ATTR_ACTOR_STATE,
    ATTR_COMBAT_STATE,
    ATTR_CURRENT_HP,
    ATTR_ENTITY_ID,
    ATTR_FACING,
    ATTR_MAX_HP,
    ATTR_POSITION,
    MSG_SYNC_CONTAINER_DATA,
    MSG_SYNC_NEAR_ENTITIES,
    MSG_SYNC_TO_ME_DELTA_INFO,
    MSG_JOIN_TEAM,
    MSG_LEAVE_TEAM,
    MSG_TEAM_DISSOLVE,
    MSG_UPDATE_TEAM_MEMBER_INFO,
    MSG_NEW_MOVE,
    WORLD_CALL_SERVICE_ID,
    GamePacketParser,
)

try:
    import zstandard
except ImportError:
    zstandard = None


class GamePacketParserTest(unittest.TestCase):
    def test_join_team_marks_nearby_player_as_teammate(self):
        parser = GamePacketParser()
        teammate_id = 456
        teammate_uuid = parser._player_uuid(teammate_id)
        parser._store_entity(teammate_uuid, (1.0, 2.0, 3.0), 0.0)
        message = parser._proto.NotifyJoinTeam()
        message.vRequest.memberData.add().charId = teammate_id

        self.assertTrue(
            parser._decode_team_notify(MSG_JOIN_TEAM, message.SerializeToString())
        )
        self.assertTrue(parser.world_state()[3][teammate_uuid]["is_teammate"])

    def test_team_member_update_adds_both_member_sources(self):
        parser = GamePacketParser()
        message = parser._proto.NoticeUpdateTeamMemberInfo()
        message.vRequest.teamMemberSocialDatas.add().charId = 111
        message.vRequest.teamMemberSyncDatas.add().charId = 222

        self.assertTrue(
            parser._decode_team_notify(
                MSG_UPDATE_TEAM_MEMBER_INFO, message.SerializeToString()
            )
        )
        self.assertEqual(
            parser.team_member_uuids,
            {parser._player_uuid(111), parser._player_uuid(222)},
        )

    def test_leave_and_dissolve_remove_team_members(self):
        parser = GamePacketParser()
        parser.local_player_uuid = parser._player_uuid(100)
        parser.team_member_uuids = {
            parser.local_player_uuid,
            parser._player_uuid(200),
        }
        leave = parser._proto.NotifyLeaveTeam()
        leave.vRequest.charId = 200

        self.assertTrue(
            parser._decode_team_notify(MSG_LEAVE_TEAM, leave.SerializeToString())
        )
        self.assertEqual(parser.team_member_uuids, {parser.local_player_uuid})
        self.assertTrue(parser._decode_team_notify(MSG_TEAM_DISSOLVE, b""))
        self.assertEqual(parser.team_member_uuids, set())

    def test_reset_transport_discards_incomplete_streams_but_preserves_state(self):
        parser = GamePacketParser()
        parser.streams[(b"source", 1, b"destination", 2)] = object()
        parser.scene_id = 123
        parser.local_position = (1.0, 2.0, 3.0)
        parser.local_position_revision = 4

        parser.reset_transport()

        self.assertEqual(parser.streams, {})
        self.assertEqual(parser.scene_id, 123)
        self.assertEqual(parser.local_position, (1.0, 2.0, 3.0))
        self.assertEqual(parser.local_position_revision, 4)

    def test_enter_scene_reads_initial_dead_actor_state(self):
        parser = GamePacketParser()
        message = parser._proto.WorldNtf.EnterScene()
        player = message.enterSceneInfo.playerEnt
        player.uuid = 123 << 16
        attr = player.attrs.attrs.add()
        attr.id = ATTR_ACTOR_STATE
        attr.rawData = bytes([ActorState.DEAD])

        self.assertFalse(parser._decode_enter_scene(message))
        self.assertEqual(parser.actor_state, ActorState.DEAD)
        self.assertEqual(parser.actor_state_revision, 1)

    def test_sync_to_me_delta_tracks_revive_actor_state(self):
        parser = GamePacketParser()
        parser.actor_state = ActorState.DEAD
        message = parser._proto.WorldNtf.SyncToMeDeltaInfo()
        message.deltaInfo.uuid = 123 << 16
        attr = message.deltaInfo.baseDelta.attrs.attrs.add()
        attr.id = ATTR_ACTOR_STATE
        attr.rawData = b""

        self.assertFalse(
            parser._decode_notify(
                MSG_SYNC_TO_ME_DELTA_INFO, message.SerializeToString()
            )
        )
        self.assertEqual(parser.actor_state, 0)
        self.assertEqual(parser.actor_state_revision, 1)

    def test_enter_scene_reads_initial_attribute_104(self):
        parser = GamePacketParser()
        message = parser._proto.WorldNtf.EnterScene()
        player = message.enterSceneInfo.playerEnt
        player.uuid = 123 << 16
        attr = player.attrs.attrs.add()
        attr.id = ATTR_COMBAT_STATE
        attr.rawData = b"\x02"

        self.assertFalse(parser._decode_enter_scene(message))
        self.assertEqual(parser.combat_state, 2)
        self.assertEqual(parser.combat_state_revision, 1)

    def test_sync_to_me_delta_updates_attribute_104_including_zero(self):
        parser = GamePacketParser()
        message = parser._proto.WorldNtf.SyncToMeDeltaInfo()
        message.deltaInfo.uuid = 123 << 16
        attr = message.deltaInfo.baseDelta.attrs.attrs.add()
        attr.id = ATTR_COMBAT_STATE
        attr.rawData = b""

        self.assertFalse(
            parser._decode_notify(
                MSG_SYNC_TO_ME_DELTA_INFO, message.SerializeToString()
            )
        )
        self.assertEqual(parser.combat_state, 0)
        self.assertEqual(parser.combat_state_revision, 1)

    def test_sync_to_me_delta_treats_omitted_attribute_104_data_as_zero(self):
        parser = GamePacketParser()
        parser.combat_state = 1
        message = parser._proto.WorldNtf.SyncToMeDeltaInfo()
        message.deltaInfo.uuid = 123 << 16
        attr = message.deltaInfo.baseDelta.attrs.attrs.add()
        attr.id = ATTR_COMBAT_STATE

        self.assertFalse(
            parser._decode_notify(
                MSG_SYNC_TO_ME_DELTA_INFO, message.SerializeToString()
            )
        )
        self.assertEqual(parser.combat_state, 0)
        self.assertEqual(parser.combat_state_revision, 1)

    def test_new_move_notify_updates_local_without_changing_server_position(self):
        parser = GamePacketParser()
        parser.server_position = (1.0, 2.0, 3.0)
        message = parser._proto.NewMove()
        message.info.destPos.x = 11.0
        message.info.destPos.y = 21.0
        message.info.destPos.z = 31.0
        payload = (
            WORLD_CALL_SERVICE_ID.to_bytes(8, "big")
            + (1).to_bytes(4, "big")
            + MSG_NEW_MOVE.to_bytes(4, "big")
            + message.SerializeToString()
        )
        fragment = (len(payload) + 6).to_bytes(4, "big") + (2).to_bytes(2, "big") + payload

        self.assertFalse(parser._process_fragments(fragment))
        self.assertEqual(parser.local_position, (11.0, 21.0, 31.0))
        self.assertEqual(parser.local_position_revision, 1)
        self.assertEqual(parser.server_position, (1.0, 2.0, 3.0))

    def test_new_move_call_updates_local_without_changing_server_position(self):
        parser = GamePacketParser()
        parser.server_position = (1.0, 2.0, 3.0)
        message = parser._proto.NewMove()
        message.info.destPos.x = 10.0
        message.info.destPos.y = 20.0
        message.info.destPos.z = 30.0
        payload = (
            WORLD_CALL_SERVICE_ID.to_bytes(8, "big")
            + (0).to_bytes(4, "big")
            + (7).to_bytes(4, "big")
            + MSG_NEW_MOVE.to_bytes(4, "big")
            + message.SerializeToString()
        )
        fragment = (len(payload) + 6).to_bytes(4, "big") + (1).to_bytes(2, "big") + payload

        self.assertFalse(parser._process_fragments(fragment))
        self.assertEqual(parser.local_position, (10.0, 20.0, 30.0))
        self.assertEqual(parser.local_position_revision, 1)
        self.assertEqual(parser.server_position, (1.0, 2.0, 3.0))

    def test_empty_facing_value_updates_to_zero(self):
        parser = GamePacketParser()
        self.assertIsNotNone(parser._proto)
        parser.facing = 90.0
        attrs = parser._proto.AttrCollection()
        attr = attrs.attrs.add()
        attr.id = ATTR_FACING
        attr.rawData = b""

        self.assertTrue(parser._decode_transform_attrs(attrs))
        self.assertEqual(parser.facing, 0.0)

    def test_scene_container_packet_updates_facing_to_zero(self):
        parser = GamePacketParser()
        self.assertIsNotNone(parser._proto)
        parser.server_position = (1.0, 2.0, 3.0)
        parser.facing = 90.0
        message = parser._proto.WorldNtf.SyncContainerData()
        message.vData.charId = 123
        message.vData.sceneData.mapId = 8
        message.vData.sceneData.pos.x = 4.0
        message.vData.sceneData.pos.y = 5.0
        message.vData.sceneData.pos.z = 6.0
        message.vData.sceneData.pos.dir = 0.0

        self.assertTrue(
            parser._decode_notify(MSG_SYNC_CONTAINER_DATA, message.SerializeToString())
        )
        self.assertEqual(parser.server_position, (4.0, 5.0, 6.0))
        self.assertEqual(parser.facing, 0.0)

    def test_enter_scene_position_updates_facing_to_zero(self):
        parser = GamePacketParser()
        self.assertIsNotNone(parser._proto)
        parser.facing = 90.0
        message = parser._proto.WorldNtf.EnterScene()
        player = message.enterSceneInfo.playerEnt
        player.uuid = 123 << 16
        attr = player.attrs.attrs.add()
        attr.id = ATTR_POSITION
        position = parser._proto.Position(x=4.0, y=5.0, z=6.0, dir=0.0)
        attr.rawData = position.SerializeToString()

        self.assertTrue(parser._decode_enter_scene(message))
        self.assertEqual(parser.server_position, (4.0, 5.0, 6.0))
        self.assertEqual(parser.local_position, (4.0, 5.0, 6.0))
        self.assertEqual(parser.local_position_revision, 1)
        self.assertEqual(parser.facing, 0.0)

    def test_sync_near_entities_removes_disappeared_entities(self):
        parser = GamePacketParser()
        removed_uuid = (123 << 16) | (1 << 6)
        retained_uuid = (456 << 16) | (1 << 6)
        parser._store_entity(removed_uuid, (1.0, 2.0, 3.0), 0.0)
        parser._store_entity(retained_uuid, (4.0, 5.0, 6.0), 0.0)
        revision = parser.metadata_revision

        message = parser._proto.SyncNearEntities()
        disappeared = message.disappear.add()
        disappeared.uuid = removed_uuid
        disappeared.type = parser._proto.EDisappearDead

        self.assertFalse(
            parser._decode_notify(MSG_SYNC_NEAR_ENTITIES, message.SerializeToString())
        )
        self.assertNotIn(removed_uuid, parser.nearby_entities)
        self.assertIn(retained_uuid, parser.nearby_entities)
        self.assertEqual(parser.metadata_revision, revision + 1)

    def test_sync_near_entities_adds_appeared_collection(self):
        parser = GamePacketParser()
        entity_uuid = 789 << 16
        message = parser._proto.SyncNearEntities()
        appeared = message.appear.add()
        appeared.uuid = entity_uuid
        appeared.entType = 16
        position_attr = appeared.attrs.attrs.add()
        position_attr.id = ATTR_POSITION
        position_attr.rawData = parser._proto.Position(
            x=10.0, y=20.0, z=30.0
        ).SerializeToString()
        facing_attr = appeared.attrs.attrs.add()
        facing_attr.id = ATTR_FACING
        facing_attr.rawData = b"\xb0\x04"
        entity_id_attr = appeared.attrs.attrs.add()
        entity_id_attr.id = ATTR_ENTITY_ID
        entity_id_attr.rawData = b"\xac\x02"

        self.assertFalse(
            parser._decode_notify(MSG_SYNC_NEAR_ENTITIES, message.SerializeToString())
        )
        entity = parser.nearby_entities[entity_uuid]
        self.assertEqual(entity["entity_type"], 16)
        self.assertNotIn("entity_type_name", entity)
        self.assertEqual(entity["position"], (10.0, 20.0, 30.0))
        self.assertEqual(entity["facing"], 5.6)
        self.assertEqual(entity["attr_id"], 300)

    def test_entity_delta_updates_attr_id_and_preserves_it_on_movement(self):
        parser = GamePacketParser()
        entity_uuid = (789 << 16) | (16 << 6)
        parser._store_entity(entity_uuid, (1.0, 2.0, 3.0), 4.0)

        attr_delta = parser._proto.AoiSyncDelta(uuid=entity_uuid)
        attr = attr_delta.attrs.attrs.add()
        attr.id = ATTR_ENTITY_ID
        attr.rawData = b"\xac\x02"
        parser._record_entity_delta(attr_delta)
        self.assertEqual(parser.nearby_entities[entity_uuid]["attr_id"], 300)

        movement_delta = parser._proto.AoiSyncDelta(uuid=entity_uuid)
        position_attr = movement_delta.attrs.attrs.add()
        position_attr.id = ATTR_POSITION
        position_attr.rawData = parser._proto.Position(
            x=10.0, y=20.0, z=30.0
        ).SerializeToString()
        parser._record_entity_delta(movement_delta)

        entity = parser.nearby_entities[entity_uuid]
        self.assertEqual(entity["attr_id"], 300)
        self.assertEqual(entity["position"], (10.0, 20.0, 30.0))

    def test_appeared_entity_tracks_health_and_actor_state(self):
        parser = GamePacketParser()
        entity_uuid = (789 << 16) | (16 << 6)
        message = parser._proto.SyncNearEntities()
        appeared = message.appear.add()
        appeared.uuid = entity_uuid
        for attr_id, raw_data in (
            (ATTR_ACTOR_STATE, bytes([ActorState.SKILL])),
            (ATTR_CURRENT_HP, b"\xac\x02"),
            (ATTR_MAX_HP, b"\x90\x03"),
        ):
            attr = appeared.attrs.attrs.add()
            attr.id = attr_id
            attr.rawData = raw_data

        parser._decode_notify(
            MSG_SYNC_NEAR_ENTITIES, message.SerializeToString()
        )

        entity = parser.nearby_entities[entity_uuid]
        self.assertEqual(entity["actor_state"], ActorState.SKILL)
        self.assertEqual(entity["current_hp"], 300)
        self.assertEqual(entity["max_hp"], 400)
        self.assertFalse(entity["is_dead"])

    def test_entity_tracks_combat_state(self):
        parser = GamePacketParser()
        entity_uuid = (789 << 16) | (10 << 6)
        message = parser._proto.SyncNearEntities()
        appeared = message.appear.add()
        appeared.uuid = entity_uuid
        appeared.entType = 10
        combat_state = appeared.attrs.attrs.add()
        combat_state.id = ATTR_COMBAT_STATE
        combat_state.rawData = b"\x01"

        parser._decode_notify(
            MSG_SYNC_NEAR_ENTITIES, message.SerializeToString()
        )
        self.assertTrue(parser.nearby_entities[entity_uuid]["in_combat"])

        delta = parser._proto.AoiSyncDelta(uuid=entity_uuid)
        combat_state = delta.attrs.attrs.add()
        combat_state.id = ATTR_COMBAT_STATE
        combat_state.rawData = b""
        parser._record_entity_delta(delta)
        self.assertFalse(parser.nearby_entities[entity_uuid]["in_combat"])

    def test_entity_delta_marks_dead_and_tracks_zero_health(self):
        parser = GamePacketParser()
        entity_uuid = (789 << 16) | (16 << 6)
        parser._store_entity(
            entity_uuid,
            (1.0, 2.0, 3.0),
            4.0,
            actor_state=ActorState.SKILL,
            current_hp=300,
            max_hp=400,
        )
        delta = parser._proto.AoiSyncDelta(uuid=entity_uuid)
        actor_state = delta.attrs.attrs.add()
        actor_state.id = ATTR_ACTOR_STATE
        actor_state.rawData = bytes([ActorState.DEAD])
        current_hp = delta.attrs.attrs.add()
        current_hp.id = ATTR_CURRENT_HP
        current_hp.rawData = b""

        parser._record_entity_delta(delta)

        entity = parser.nearby_entities[entity_uuid]
        self.assertEqual(entity["actor_state"], ActorState.DEAD)
        self.assertEqual(entity["current_hp"], 0)
        self.assertEqual(entity["max_hp"], 400)
        self.assertTrue(entity["is_dead"])

    @unittest.skipUnless(zstandard is not None, "zstandard is not installed")
    def test_decompresses_zstd_frame_without_content_size(self):
        expected = b"compressed EnterScene payload"
        compressed = zstandard.ZstdCompressor(write_content_size=False).compress(expected)

        self.assertEqual(GamePacketParser._decompress(compressed), expected)


if __name__ == "__main__":
    unittest.main()
