import unittest

from src.packet_capture.parser import (
    ATTR_FACING,
    ATTR_POSITION,
    MSG_SYNC_CONTAINER_DATA,
    GamePacketParser,
)

try:
    import zstandard
except ImportError:
    zstandard = None


class GamePacketParserTest(unittest.TestCase):
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
        parser.position = (1.0, 2.0, 3.0)
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
        self.assertEqual(parser.position, (4.0, 5.0, 6.0))
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
        self.assertEqual(parser.position, (4.0, 5.0, 6.0))
        self.assertEqual(parser.facing, 0.0)

    @unittest.skipUnless(zstandard is not None, "zstandard is not installed")
    def test_decompresses_zstd_frame_without_content_size(self):
        expected = b"compressed EnterScene payload"
        compressed = zstandard.ZstdCompressor(write_content_size=False).compress(expected)

        self.assertEqual(GamePacketParser._decompress(compressed), expected)


if __name__ == "__main__":
    unittest.main()
