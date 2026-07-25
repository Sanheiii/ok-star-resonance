import unittest
from collections import Counter

from src.packet_capture.adapter_detection import _match_device, _normalize_guid
from src.packet_capture.npcap import NpcapDevice


class AdapterDetectionTest(unittest.TestCase):
    def test_normalize_npcap_device_guid(self):
        self.assertEqual(
            _normalize_guid(r"\Device\NPF_{12345678-abcd-ef00-1234-56789abcdef0}"),
            "12345678-ABCD-EF00-1234-56789ABCDEF0",
        )

    def test_match_device_prefers_ip_with_more_connections(self):
        first = NpcapDevice(r"\Device\NPF_{FIRST}", "First")
        second = NpcapDevice(r"\Device\NPF_{SECOND}", "Second")
        device = _match_device(
            [first, second],
            Counter({"10.0.0.2": 1, "192.168.1.2": 3}),
            {"FIRST": {"10.0.0.2"}, "SECOND": {"192.168.1.2"}},
        )
        self.assertEqual(device, second)

    def test_match_device_returns_none_without_matching_ip(self):
        device = NpcapDevice(r"\Device\NPF_{FIRST}", "First")
        self.assertIsNone(
            _match_device([device], Counter({"10.0.0.2": 1}), {"FIRST": {"10.0.0.3"}})
        )


if __name__ == "__main__":
    unittest.main()
