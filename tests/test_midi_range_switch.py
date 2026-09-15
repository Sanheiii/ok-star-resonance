import ast
from pathlib import Path
import unittest


def load_player_methods():
    # Test the actual task methods without starting Qt, capture or input devices.
    path = Path(__file__).resolve().parents[1] / 'src/tasks/MidiPlayerTask.py'
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    task = next(node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == 'MidiPlayerTask')
    methods = [node for node in task.body if isinstance(node, ast.FunctionDef)
               and node.name in ('switch_state', 'tap_key')]
    namespace = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), namespace)
    return type('PlayerMethods', (), namespace)


PlayerMethods = load_player_methods()


class TestMidiRangeSwitch(unittest.TestCase):
    def test_all_transitions_restore_octave_before_paging(self):
        for page in range(3):
            for octave in (-1, 0, 1):
                for target_page in range(3):
                    for target_octave in (-1, 0, 1):
                        with self.subTest(start=(page, octave), end=(target_page, target_octave)):
                            player = PlayerMethods()
                            player.current_page, player.current_octave = page, octave
                            player.log_debug = lambda message: None
                            game = [page, octave]
                            def tap(key):
                                if key in (',', '.'):
                                    self.assertEqual(game[1], 0)
                                    game[0] += 1 if key == '.' else -1
                                else:
                                    value = 1 if key == 'lshift' else -1
                                    game[1] = 0 if game[1] == value else value
                            player.tap_key = tap
                            player.switch_state(target_page, target_octave)
                            self.assertEqual(game, [target_page, target_octave])
                            self.assertEqual((player.current_page, player.current_octave),
                                             (target_page, target_octave))

    def test_interrupted_switch_key_is_released(self):
        player = PlayerMethods()
        calls = []
        player.send_key_down = lambda key: calls.append(('down', key))
        player.send_key_up = lambda key: calls.append(('up', key))
        def interrupted(seconds):
            raise RuntimeError('task stopped')
        player.sleep = interrupted
        with self.assertRaises(RuntimeError):
            player.tap_key('lctrl')
        self.assertEqual(calls, [('down', 'lctrl'), ('up', 'lctrl')])


if __name__ == '__main__':
    unittest.main()
