import unittest
from unittest.mock import Mock, patch

import win32api
import win32con

from src.interaction.HybridInteraction import HybridInteraction
from src.config import config


class HybridInteractionTest(unittest.TestCase):
    def test_custom_interaction_is_registered_as_a_class(self):
        interactions = config["windows"]["interaction"]

        self.assertIn(HybridInteraction, interactions)
        self.assertNotIn("HybridInteraction", interactions)

    def setUp(self):
        self.capture = Mock()
        self.capture.get_abs_cords.return_value = (120, 240)
        self.hwnd_window = Mock()
        self.hwnd_window.hwnd = 100
        self.hwnd_window.top_hwnd = 0
        self.hwnd_window.get_top_window_cords.side_effect = lambda x, y: (x, y)
        self.hwnd_window.hwnds = []
        self.interaction = HybridInteraction(self.capture, self.hwnd_window)
        self.interaction._mouse_controller = Mock()
        self.interaction.post = Mock()

    @patch("ok.device.interaction_methods.post_message.win32gui.ClientToScreen")
    @patch("ok.device.interaction_methods.post_message.win32gui.ScreenToClient")
    @patch("ok.device.interaction_methods.post_message.win32gui.IsWindow")
    @patch("src.interaction.HybridInteraction.time.sleep")
    def test_click_moves_with_pynput_and_posts_button_messages(
        self, sleep, is_window, screen_to_client, client_to_screen
    ):
        is_window.return_value = True
        client_to_screen.return_value = (120, 240)
        screen_to_client.return_value = (20, 40)

        self.interaction.click(20, 40)

        self.assertEqual(self.interaction.mouse_controller.position, (120, 240))
        position = win32api.MAKELONG(20, 40)
        self.interaction.post.assert_any_call(
            win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, position
        )
        self.interaction.post.assert_any_call(win32con.WM_LBUTTONUP, 0, position)

    def test_keyboard_uses_post_message_backend(self):
        with patch.object(self.interaction, "try_activate"):
            self.interaction.send_key_down("a")

        message, virtual_key, _ = self.interaction.post.call_args.args
        self.assertEqual(message, win32con.WM_KEYDOWN)
        self.assertEqual(virtual_key, ord("A"))

    def test_left_shift_uses_left_virtual_key_and_left_scan_code(self):
        with patch.object(self.interaction, "try_activate"):
            self.interaction.send_key_down("lshift")

        message, virtual_key, lparam = self.interaction.post.call_args.args
        self.assertEqual(message, win32con.WM_KEYDOWN)
        self.assertEqual(virtual_key, win32con.VK_LSHIFT)
        self.assertEqual((lparam >> 16) & 0xFF, 0x2A)
        self.assertFalse(lparam & (1 << 24))

    def test_right_shift_uses_right_virtual_key_and_right_scan_code(self):
        self.interaction.send_key_up("rshift")

        message, virtual_key, lparam = self.interaction.post.call_args.args
        self.assertEqual(message, win32con.WM_KEYUP)
        self.assertEqual(virtual_key, win32con.VK_RSHIFT)
        self.assertEqual((lparam >> 16) & 0xFF, 0x36)
        self.assertFalse(lparam & (1 << 24))
        self.assertTrue(lparam & (1 << 30))
        self.assertTrue(lparam & (1 << 31))

    def test_right_ctrl_uses_generic_virtual_key_and_extended_flag(self):
        self.interaction.send_key_up("rctrl")

        message, virtual_key, lparam = self.interaction.post.call_args.args
        self.assertEqual(message, win32con.WM_KEYUP)
        self.assertEqual(virtual_key, win32con.VK_CONTROL)
        self.assertEqual((lparam >> 16) & 0xFF, 0x1D)
        self.assertTrue(lparam & (1 << 24))
        self.assertTrue(lparam & (1 << 30))
        self.assertTrue(lparam & (1 << 31))

    def test_left_alt_uses_generic_virtual_key_without_extended_flag(self):
        with patch.object(self.interaction, "try_activate"):
            self.interaction.send_key_down("lalt")

        message, virtual_key, lparam = self.interaction.post.call_args.args
        self.assertEqual(message, win32con.WM_KEYDOWN)
        self.assertEqual(virtual_key, win32con.VK_MENU)
        self.assertEqual((lparam >> 16) & 0xFF, 0x38)
        self.assertFalse(lparam & (1 << 24))

    def test_right_alt_uses_generic_virtual_key_and_extended_flag(self):
        self.interaction.send_key_up("ralt")

        message, virtual_key, lparam = self.interaction.post.call_args.args
        self.assertEqual(message, win32con.WM_KEYUP)
        self.assertEqual(virtual_key, win32con.VK_MENU)
        self.assertEqual((lparam >> 16) & 0xFF, 0x38)
        self.assertTrue(lparam & (1 << 24))
        self.assertTrue(lparam & (1 << 30))
        self.assertTrue(lparam & (1 << 31))


if __name__ == "__main__":
    unittest.main()
