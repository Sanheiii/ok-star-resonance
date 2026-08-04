import unittest
from unittest.mock import patch

import numpy as np

from tasks.DungeonTasks import DungeonTaskBase as dungeon_task_base_module
from tasks.DungeonTasks.DungeonTaskBase import Difficulty, DungeonTaskBase


class _WaitOutOfCombatTask:
    def __init__(self, states):
        self._states = iter(states)
        self._actor_state = 0
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
        state = next(self._states)
        self._in_combat, self._is_dead = state[:2]
        if len(state) > 2:
            self._actor_state = state[2]
        return self._in_combat

    @property
    def actor_state(self):
        return self._actor_state

    @property
    def is_dead(self):
        return self._is_dead

    def handle_death(self):
        self.death_handling_count += 1


class WaitOutOfCombatTest(unittest.TestCase):
    def test_actor_state_two_is_treated_as_in_combat(self):
        task = _WaitOutOfCombatTask([(0, False, 2)] * 20)

        result = DungeonTaskBase.wait_out_of_combat(task)

        self.assertFalse(result)

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


class _WaitInCombatTask:
    def __init__(self, states):
        self._states = iter(states)
        self.capture_checks = 0

    def _require_packet_capture(self):
        self.capture_checks += 1

    def wait_until(self, condition, time_out=0):
        self.time_out = time_out
        for _ in range(3):
            if condition():
                return True
        return None

    @property
    def in_combat(self):
        return next(self._states)


class WaitInCombatTest(unittest.TestCase):
    def test_returns_true_after_entering_combat(self):
        task = _WaitInCombatTask([None, 0, 1])

        result = DungeonTaskBase.wait_in_combat(task, time_out=12)

        self.assertTrue(result)
        self.assertEqual(task.time_out, 12)
        self.assertEqual(task.capture_checks, 4)

    def test_returns_false_when_timeout_expires(self):
        task = _WaitInCombatTask([None, 0, 0])

        result = DungeonTaskBase.wait_in_combat(task, time_out=5)

        self.assertFalse(result)
        self.assertEqual(task.time_out, 5)


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


class AutoCombatDetectionTest(unittest.TestCase):
    @staticmethod
    def _frame_with_skill_ui():
        frame = np.full((720, 1280, 3), (40, 40, 40), dtype=np.uint8)
        DungeonTaskBase._crop_normalized(
            frame,
            DungeonTaskBase._SKILL_UI_ANCHOR_BOX,
        )[:] = DungeonTaskBase._SKILL_UI_DARK_BGR
        return frame

    def test_returns_none_when_skill_ui_is_hidden(self):
        frame = np.full((720, 1280, 3), (210, 160, 40), dtype=np.uint8)

        self.assertIsNone(DungeonTaskBase._detect_auto_combat(frame))

    def test_returns_false_without_outline_in_skill_gaps(self):
        frame = self._frame_with_skill_ui()

        self.assertFalse(DungeonTaskBase._detect_auto_combat(frame))

    def test_returns_true_when_any_skill_gap_has_blue_outline(self):
        frame = self._frame_with_skill_ui()
        DungeonTaskBase._crop_normalized(
            frame,
            DungeonTaskBase._SKILL_GAP_BOXES[3],
        )[:] = (210, 160, 40)

        self.assertTrue(DungeonTaskBase._detect_auto_combat(frame))


class _EnsureAutoCombatTask:
    def __init__(self, states, wait_results=()):
        self.states = iter(states)
        self.wait_results = iter(wait_results)
        self.keys = []

    def send_key(self, key):
        self.keys.append(key)

    def next_frame(self):
        pass

    def is_auto_combat_enabled(self):
        return next(self.states)

    def wait_until(self, condition, time_out=0):
        self.wait_time_out = time_out
        condition_result = condition()
        return next(self.wait_results, condition_result)


class EnsureAutoCombatTest(unittest.TestCase):
    @patch.object(dungeon_task_base_module.time, 'monotonic')
    def test_returns_immediately_when_state_already_matches(self, monotonic):
        monotonic.return_value = 0
        task = _EnsureAutoCombatTask([True])

        result = DungeonTaskBase.ensure_auto_combat(task, True, time_out=10)

        self.assertTrue(result)
        self.assertEqual(task.keys, ['lctrl'])

    @patch.object(dungeon_task_base_module.time, 'monotonic')
    def test_presses_h_and_waits_up_to_two_seconds_for_update(self, monotonic):
        monotonic.side_effect = [0, 1, 1]
        task = _EnsureAutoCombatTask([False, True])

        result = DungeonTaskBase.ensure_auto_combat(task, True, time_out=10)

        self.assertTrue(result)
        self.assertEqual(task.keys, ['lctrl', 'h'])
        self.assertEqual(task.wait_time_out, 2)

    @patch.object(dungeon_task_base_module.time, 'monotonic')
    def test_presses_h_again_when_first_update_does_not_arrive(self, monotonic):
        monotonic.side_effect = [0, 1, 1, 3, 3]
        task = _EnsureAutoCombatTask(
            [False, False, True],
            wait_results=[False],
        )

        result = DungeonTaskBase.ensure_auto_combat(task, True, time_out=10)

        self.assertTrue(result)
        self.assertEqual(task.keys, ['lctrl', 'h', 'h'])

    @patch.object(dungeon_task_base_module.time, 'monotonic')
    def test_retries_h_until_timeout(self, monotonic):
        monotonic.side_effect = [0, 1, 1, 11]
        task = _EnsureAutoCombatTask([False, False], wait_results=[False])

        result = DungeonTaskBase.ensure_auto_combat(task, True, time_out=10)

        self.assertFalse(result)
        self.assertEqual(task.keys, ['lctrl', 'h'])

    def test_rejects_non_boolean_target(self):
        task = _EnsureAutoCombatTask([])

        with self.assertRaises(TypeError):
            DungeonTaskBase.ensure_auto_combat(task, 1)


class _RedeemItemsTask:
    def __init__(self, *, enabled=True, interval=2, item_index=1,
                 pass_count=2, last_redeem=None):
        self.config = {
            'Purchase Items': enabled,
            'Purchase Every N Clears': interval,
            'Purchase Item Index': item_index,
        }
        self.info = {'Pass Count': pass_count}
        self._last_redeem_pass_count = last_redeem
        self.keys = []
        self.clicks = []
        self.errors = []

    def send_key(self, key, **kwargs):
        self.keys.append((key, kwargs))

    def click(self, *position, **kwargs):
        self.clicks.append((position, kwargs))

    def log_error(self, message):
        self.errors.append(message)


class RedeemItemsTest(unittest.TestCase):
    def test_uses_configured_season_hub_key(self):
        task = _RedeemItemsTask()
        task.get_global_config = lambda _option: {
            **task.config,
            'Season Hub': 'u',
        }

        self.assertTrue(DungeonTaskBase.redeem_items(task))
        self.assertEqual(task.keys[0][0], 'u')
        self.assertEqual(task.keys[-1][0], 'u')

    def test_only_triggers_at_the_configured_clear_interval(self):
        task = _RedeemItemsTask(pass_count=1)

        self.assertTrue(DungeonTaskBase.redeem_items(task))
        self.assertFalse(task.keys)

        task.info['Pass Count'] = 2
        self.assertTrue(DungeonTaskBase.redeem_items(task))
        self.assertTrue(task.keys)

    def test_does_not_trigger_again_when_entry_retries(self):
        task = _RedeemItemsTask(pass_count=2)

        self.assertTrue(DungeonTaskBase.redeem_items(task))
        task.keys.clear()
        task.clicks.clear()

        self.assertTrue(DungeonTaskBase.redeem_items(task))
        self.assertFalse(task.keys)
        self.assertFalse(task.clicks)

    def test_out_of_range_item_index_logs_error_and_returns_true(self):
        task = _RedeemItemsTask(item_index=22)

        self.assertTrue(DungeonTaskBase.redeem_items(task))
        self.assertTrue(task.errors)
        self.assertFalse(task.keys)

        task.errors.clear()
        self.assertTrue(DungeonTaskBase.redeem_items(task))
        self.assertFalse(task.errors)


class _RecoverTask:
    scene_id = 8

    def __init__(self):
        self.info = {}
        self._frames = iter([None, object()])
        self.current_frame = None
        self.find_calls = []
        self.color_percentage_calls = []
        self.warnings = []
        self.sleep_calls = []

    def screenshot(self, _name):
        raise AssertionError('The initial-state scene must not be screenshotted')

    def get_game_language(self):
        return 'en'

    def get_task_by_class(self, _task_class):
        return object()

    def next_frame(self):
        self.current_frame = next(self._frames)
        return self.current_frame

    def find_one(self, feature_name, **_kwargs):
        if self.current_frame is None:
            raise AssertionError('Feature detection must not run without a frame')
        self.find_calls.append(feature_name)
        return False

    def get_box_by_name(self, feature_name):
        return f'{feature_name}_box'

    def calculate_color_percentage(self, color, box):
        if self.current_frame is None:
            raise AssertionError('Color detection must not run without a frame')
        self.color_percentage_calls.append((color, box))
        return 0.8

    def log_warning(self, message):
        self.warnings.append(message)

    def sleep(self, seconds):
        self.sleep_calls.append(seconds)


class ReturnToInitialStateTest(unittest.TestCase):
    def test_retries_capture_before_running_feature_detection(self):
        task = _RecoverTask()

        DungeonTaskBase.return_to_initial_state(task)

        self.assertEqual(task.find_calls, [])
        self.assertEqual(task.color_percentage_calls, [(
            {'r': (255, 255), 'g': (255, 255), 'b': (255, 255)},
            'menu_icon_box',
        )])
        self.assertEqual(task.sleep_calls, [1])
        self.assertEqual(len(task.warnings), 1)


class _PickupSpecialRewardTask:
    def __init__(self, entities, move_result=True):
        self.nearby_entities = entities
        self.position = (1, 2, 3)
        self.info = {'Special Reward Count': 0}
        self.move_result = move_result
        self.moves = []
        self.keys = []
        self.errors = []

    def move_to_position(self, current, target, **kwargs):
        self.moves.append((current, target, kwargs))
        return self.move_result

    def send_key(self, key):
        self.keys.append(key)

    def log_error(self, message):
        self.errors.append(message)


class PickupSpecialRewardTest(unittest.TestCase):
    def test_moves_to_reward_and_presses_f(self):
        task = _PickupSpecialRewardTask({
            1: {'attr_id': 9999, 'position': (4, 5, 6)},
            2: {'attr_id': 1207, 'position': (7, 8, 9)},
        })

        self.assertTrue(DungeonTaskBase.pickup_special_reward(task, 1207))
        self.assertEqual(task.moves, [(
            (1, 2, 3),
            (7, 8, 9),
            {'target_tolerance': 1.5, 'enable_sprint': True},
        )])
        self.assertEqual(task.keys, ['f'])
        self.assertEqual(task.info['Special Reward Count'], 1)

    def test_returns_false_when_reward_is_missing(self):
        task = _PickupSpecialRewardTask({
            1: {'attr_id': 1207, 'position': None},
        })

        self.assertFalse(DungeonTaskBase.pickup_special_reward(task, 1207))
        self.assertFalse(task.moves)
        self.assertFalse(task.keys)
        self.assertEqual(task.info['Special Reward Count'], 0)

    def test_returns_false_without_pressing_f_when_movement_fails(self):
        task = _PickupSpecialRewardTask({
            1: {'attr_id': 1207, 'position': (7, 8, 9)},
        }, move_result=False)

        self.assertFalse(DungeonTaskBase.pickup_special_reward(task, 1207))
        self.assertFalse(task.keys)
        self.assertEqual(task.info['Special Reward Count'], 0)

    def test_returns_false_when_an_unexpected_error_occurs(self):
        task = _PickupSpecialRewardTask({
            1: {'attr_id': 1207, 'position': (7, 8, 9)},
        })

        def fail_to_send(_key):
            raise RuntimeError('input failed')

        task.send_key = fail_to_send

        self.assertFalse(DungeonTaskBase.pickup_special_reward(task, 1207))
        self.assertTrue(task.errors)
        self.assertEqual(task.info['Special Reward Count'], 0)


if __name__ == '__main__':
    unittest.main()
