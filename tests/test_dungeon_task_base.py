import unittest

from src.tasks.DungeonTaskBase import Difficulty, DungeonTaskBase


class _EnterTask:
    HAS_NORMAL_DIFFICULTY = True
    frame = object()

    def __init__(self):
        self.clicks = []
        self.errors = []
        self.info = {'entry_count': 0}

    def wait_feature(self, name):
        return name in {
            'dungeon_entrance',
            'dungeon_icon',
            'loading',
            'dungeon_scene_icon',
        }

    def find_one(self, _name):
        return None

    def click(self, *position):
        self.clicks.append(position)

    def log_error(self, message):
        self.errors.append(message)

    def log_info(self, _message):
        pass

    def send_key_down(self, _key):
        pass

    def send_key_up(self, _key):
        pass

    def sleep(self, _seconds):
        pass

    def next_frame(self):
        pass

    def width_of_screen(self, ratio):
        return ratio

    def height_of_screen(self, ratio):
        return ratio

    def scroll(self, *_args):
        pass


class DungeonDifficultyTest(unittest.TestCase):
    def test_default_difficulty_positions_include_normal(self):
        task = _EnterTask()

        self.assertTrue(DungeonTaskBase.enter(task, Difficulty.HARD))

        self.assertIn((0.092, 0.245), task.clicks)

    def test_positions_shift_when_normal_is_unavailable(self):
        task = _EnterTask()
        task.HAS_NORMAL_DIFFICULTY = False

        self.assertTrue(DungeonTaskBase.enter(task, Difficulty.HARD))
        self.assertIn((0.092, 0.154), task.clicks)

        task = _EnterTask()
        task.HAS_NORMAL_DIFFICULTY = False

        self.assertTrue(DungeonTaskBase.enter(task, Difficulty.MASTER1))
        self.assertIn((0.092, 0.245), task.clicks)

    def test_normal_is_rejected_when_unavailable(self):
        task = _EnterTask()
        task.HAS_NORMAL_DIFFICULTY = False

        self.assertFalse(DungeonTaskBase.enter(task, Difficulty.NORMAL))
        self.assertTrue(task.errors)


if __name__ == '__main__':
    unittest.main()
