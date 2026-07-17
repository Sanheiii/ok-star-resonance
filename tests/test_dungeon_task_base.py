import unittest
from unittest.mock import patch

from tasks.DungeonTasks import DungeonTaskBase as dungeon_task_base_module
from tasks.DungeonTasks.DungeonTaskBase import Difficulty, DungeonTaskBase


class _WaitOutOfCombatTask:
    def __init__(self, states):
        self._states = iter(states)
        self.capture_checks = 0
        self.death_handling_count = 0

    def _require_packet_capture(self):
        self.capture_checks += 1

    def wait_until(self, condition, time_out=0):
        self.time_out = time_out
        for _ in range(20):
            if condition():
                return True
        return None

    @property
    def in_combat(self):
        self._in_combat, self._is_dead = next(self._states)
        return self._in_combat

    @property
    def is_dead(self):
        return self._is_dead

    def handle_death(self):
        self.death_handling_count += 1


class WaitOutOfCombatTest(unittest.TestCase):
    @patch.object(dungeon_task_base_module.time, 'monotonic')
    def test_requires_five_continuous_seconds_without_combat_or_death(self, monotonic):
        task = _WaitOutOfCombatTask([(0, False)] * 3)
        monotonic.side_effect = [10, 14.9, 15]

        result = DungeonTaskBase.wait_out_of_combat(task, time_out=12)

        self.assertTrue(result)
        self.assertEqual(task.time_out, 12)

    @patch.object(dungeon_task_base_module.time, 'monotonic')
    def test_combat_or_death_restarts_the_five_second_timer(self, monotonic):
        task = _WaitOutOfCombatTask([
            (0, False),
            (0, False),
            (1, False),
            (0, False),
            (0, True),
            (0, False),
            (0, False),
        ])
        monotonic.side_effect = [0, 4.9, 10, 20, 25]

        result = DungeonTaskBase.wait_out_of_combat(task)

        self.assertTrue(result)
        self.assertEqual(task.death_handling_count, 1)


class _EnterTask:
    has_normal_difficulty = True
    frame = object()

    def __init__(self):
        self.clicks = []
        self.errors = []
        self.info = {
            'Entry Count': 0,
            'Pass Count': 0,
            'Pass Rate': '0.00%',
        }

    _update_pass_rate = DungeonTaskBase._update_pass_rate

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
        task.has_normal_difficulty = False

        self.assertTrue(DungeonTaskBase.enter(task, Difficulty.HARD))
        self.assertIn((0.092, 0.154), task.clicks)

        task = _EnterTask()
        task.has_normal_difficulty = False

        self.assertTrue(DungeonTaskBase.enter(task, Difficulty.MASTER1))
        self.assertIn((0.092, 0.245), task.clicks)

    def test_normal_is_rejected_when_unavailable(self):
        task = _EnterTask()
        task.has_normal_difficulty = False

        self.assertFalse(DungeonTaskBase.enter(task, Difficulty.NORMAL))
        self.assertTrue(task.errors)


class PassRateTest(unittest.TestCase):
    def test_uses_entry_count_minus_one_as_denominator(self):
        task = object.__new__(DungeonTaskBase)
        task.info = {'Entry Count': 4, 'Pass Count': 3}

        DungeonTaskBase._update_pass_rate(task)

        self.assertEqual(task.info['Pass Rate'], '100.00%')

    def test_handles_zero_denominator(self):
        task = object.__new__(DungeonTaskBase)
        task.info = {'Entry Count': 1, 'Pass Count': 0}

        DungeonTaskBase._update_pass_rate(task)

        self.assertEqual(task.info['Pass Rate'], '0.00%')


if __name__ == '__main__':
    unittest.main()
