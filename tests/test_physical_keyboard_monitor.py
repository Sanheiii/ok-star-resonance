import unittest
from unittest.mock import Mock, patch

from src.input.PhysicalKeyboardMonitor import (
    INPUT_MARKER,
    KeyboardEvent,
    PhysicalKeyboardMonitor,
    is_physical_keyboard_event,
)


class PhysicalKeyboardMonitorTest(unittest.TestCase):
    def test_only_non_injected_flags_are_physical(self):
        self.assertTrue(is_physical_keyboard_event(0x00))
        self.assertFalse(is_physical_keyboard_event(0x10))
        self.assertFalse(is_physical_keyboard_event(0x90))

    def test_extra_info_does_not_override_injected_flag(self):
        pynput_event = KeyboardEvent(0x31, 0, 0x10, 0, 0)
        project_event = KeyboardEvent(0x31, 0, 0x10, 0, INPUT_MARKER)

        self.assertTrue(pynput_event.injected)
        self.assertFalse(pynput_event.project_injected)
        self.assertTrue(project_event.project_injected)

    @patch.object(PhysicalKeyboardMonitor, "_declare_win32_types")
    @patch("src.input.PhysicalKeyboardMonitor.ctypes.WinDLL")
    def test_start_and_stop_are_idempotent(self, win_dll, _declare):
        monitor = PhysicalKeyboardMonitor(Mock())
        monitor._running = True
        monitor._thread = Mock()
        monitor._thread.is_alive.return_value = False

        self.assertTrue(monitor.start())
        self.assertTrue(monitor.start())
        monitor.stop()
        monitor.stop()


if __name__ == "__main__":
    unittest.main()
