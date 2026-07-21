import unittest
from unittest.mock import Mock, patch

import win32api
import win32con

from src.interaction.SRInteraction import SRInteraction
from src.config import config


class SRInteractionTest(unittest.TestCase):
    def test_custom_interaction_is_registered_as_a_class(self):
        interactions = config["windows"]["interaction"]

        self.assertIn(SRInteraction, interactions)
        self.assertNotIn("SRInteraction", interactions)

    def setUp(self):
        self.capture = Mock()
        self.capture.get_abs_cords.return_value = (120, 240)
        self.hwnd_window = Mock()
        self.hwnd_window.hwnd = 100
        self.hwnd_window.top_hwnd = 0
        self.hwnd_window.get_top_window_cords.side_effect = lambda x, y: (x, y)
        self.hwnd_window.hwnds = []
        self.interaction = SRInteraction(self.capture, self.hwnd_window)
        self.interaction._mouse_controller = Mock()
        self.interaction.post = Mock()

    @patch("ok.device.interaction_methods.post_message.win32gui.ClientToScreen")
    @patch("ok.device.interaction_methods.post_message.win32gui.ScreenToClient")
    @patch("ok.device.interaction_methods.post_message.win32gui.IsWindow")
    @patch("src.interaction.SRInteraction.time.sleep")
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


if __name__ == "__main__":
    unittest.main()
