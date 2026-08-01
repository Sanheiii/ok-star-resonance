import unittest
from unittest.mock import Mock, patch

from src.packet_capture.windivert import WinDivertCapture


class WinDivertCaptureTest(unittest.TestCase):
    @patch("src.packet_capture.windivert._load_pydivert")
    def test_uses_sniff_mode_and_emits_raw_ip_packet(self, load_pydivert):
        packet = Mock(raw=memoryview(bytearray(b"raw-ip-packet")))
        handle = Mock()
        handle.recv.return_value = packet
        api = load_pydivert.return_value
        api.WinDivert.return_value = handle

        capture = WinDivertCapture()
        received = []

        def receive(raw_packet):
            received.append(raw_packet)
            capture.stop()

        capture.run(receive)

        api.WinDivert.assert_called_once_with(
            WinDivertCapture.FILTER, flags=api.Flag.SNIFF
        )
        self.assertEqual(capture.datalink, 12)
        self.assertEqual(received, [b"raw-ip-packet"])
        self.assertIsInstance(received[0], bytes)
        handle.open.assert_called_once_with()

    @patch("src.packet_capture.windivert._load_pydivert")
    def test_stop_closes_handle_once(self, load_pydivert):
        handle = Mock()
        load_pydivert.return_value.WinDivert.return_value = handle
        capture = WinDivertCapture()

        capture.stop()
        capture.stop()

        handle.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
