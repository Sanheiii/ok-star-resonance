import unittest

from src.packet_capture.parser import GamePacketParser

try:
    import zstandard
except ImportError:
    zstandard = None


class GamePacketParserTest(unittest.TestCase):
    @unittest.skipUnless(zstandard is not None, "zstandard is not installed")
    def test_decompresses_zstd_frame_without_content_size(self):
        expected = b"compressed EnterScene payload"
        compressed = zstandard.ZstdCompressor(write_content_size=False).compress(expected)

        self.assertEqual(GamePacketParser._decompress(compressed), expected)


if __name__ == "__main__":
    unittest.main()
