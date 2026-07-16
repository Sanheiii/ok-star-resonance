import unittest

from src.packet_capture.parser import (
    ACTOR_STATE_DEAD,
    ATTR_ACTOR_STATE,
    ATTR_COMBAT_STATE,
    ATTR_FACING,
    ATTR_POSITION,
    MSG_SYNC_CONTAINER_DATA,
    MSG_SYNC_NEAR_ENTITIES,
    MSG_SYNC_TO_ME_DELTA_INFO,
    MSG_NEW_MOVE,
    WORLD_CALL_SERVICE_ID,
    GamePacketParser,
)

try:
    import zstandard
except ImportError:
    zstandard = None


class GamePacketParserTest(unittest.TestCase):
    def test_enter_scene_reads_initial_dead_actor_state(self):
        parser = GamePacketParser()
        message = parser._proto.WorldNtf.EnterScene()
        player = message.enterSceneInfo.playerEnt
        player.uuid = 123 << 16
        attr = player.attrs.attrs.add()
        attr.id = ATTR_ACTOR_STATE
        attr.rawData = bytes([ACTOR_STATE_DEAD])

        self.assertFalse(parser._decode_enter_scene(message))
        self.assertEqual(parser.actor_state, ACTOR_STATE_DEAD)
        self.assertTrue(parser.is_dead)
        self.assertEqual(parser.death_state_revision, 1)

    def test_sync_to_me_delta_tracks_revive_actor_state(self):
        parser = GamePacketParser()
        parser.actor_state = ACTOR_STATE_DEAD
        parser.is_dead = True
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
        self.assertFalse(parser.is_dead)
        self.assertEqual(parser.death_state_revision, 1)

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

        self.assertFalse(
            parser._decode_notify(MSG_SYNC_NEAR_ENTITIES, message.SerializeToString())
        )
        entity = parser.nearby_entities[entity_uuid]
        self.assertEqual(entity["entity_type"], 16)
        self.assertEqual(entity["entity_type_name"], "Collection")
        self.assertEqual(entity["position"], (10.0, 20.0, 30.0))
        self.assertEqual(entity["facing"], 5.6)

    @unittest.skipUnless(zstandard is not None, "zstandard is not installed")
    def test_decompresses_zstd_frame_without_content_size(self):
        expected = b"compressed EnterScene payload"
        compressed = zstandard.ZstdCompressor(write_content_size=False).compress(expected)

        self.assertEqual(GamePacketParser._decompress(compressed), expected)


if __name__ == "__main__":
    unittest.main()
