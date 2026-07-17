import unittest
from unittest.mock import patch

from src.packet_capture.parser import ActorState
from src.tasks import SRTaskBase as sr_task_base_module
from src.tasks.SRTaskBase import SRTaskBase


class _WaitTask:
    def __init__(self, states):
        self._states = iter(states)
        self._in_combat = None
        self.capture_checks = 0

    @property
    def in_combat(self):
        self._in_combat = next(self._states)
        return self._in_combat

    def _require_packet_capture(self):
        self.capture_checks += 1

    def wait_until(self, condition, time_out=0):
        self.time_out = time_out
        for _ in range(10):
            if condition():
                return True
        return None


class WaitOutOfCombatTest(unittest.TestCase):
    def test_waits_through_unknown_and_combat_until_zero(self):
        task = _WaitTask([None, 1, 0])

        result = SRTaskBase.wait_out_of_combat(task, time_out=12)

        self.assertTrue(result)
        self.assertEqual(task.time_out, 12)
        self.assertEqual(task.capture_checks, 4)

    def test_returns_false_when_zero_is_not_seen(self):
        task = _WaitTask([1] * 10)

        self.assertFalse(SRTaskBase.wait_out_of_combat(task, time_out=1))


class CapturedStatePropertyTest(unittest.TestCase):
    def test_exposes_combat_and_actor_states(self):
        class CaptureData:
            @staticmethod
            def get_combat_state():
                return 1

            @staticmethod
            def get_actor_state():
                return ActorState.DEAD

        task = object.__new__(SRTaskBase)
        with patch.object(
                sr_task_base_module.og,
                "packet_capture_data",
                CaptureData(),
                create=True):
            self.assertEqual(task.in_combat, 1)
            self.assertEqual(task.actor_state, ActorState.DEAD)
            self.assertTrue(task.is_dead)


class _PathTask:
    def __init__(self, results):
        self.position = (0, 0)
        self.results = iter(results)
        self.calls = []

    def _begin_movement_session(self):
        pass

    def _end_movement_session(self):
        pass

    def _release_move_keys(self):
        pass

    def sleep(self, _seconds):
        pass

    def move_to_position(self, start, target, **_kwargs):
        self.calls.append((start, target, _kwargs))
        return next(self.results)


class MovementReturnValueTest(unittest.TestCase):
    def test_path_returns_current_and_later_nodes_after_death(self):
        task = _PathTask([True, False])
        nodes = [(1, 1), (2, 2), (3, 3)]

        remaining = SRTaskBase.move_to_positions(task, nodes)

        self.assertEqual(remaining, [(2, 2), (3, 3)])

    def test_completed_path_returns_none(self):
        task = _PathTask([True, True])

        self.assertIsNone(SRTaskBase.move_to_positions(task, [(1, 1), (2, 2)]))

    def test_path_forwards_maximum_deviation_to_each_segment(self):
        task = _PathTask([True, True])

        SRTaskBase.move_to_positions(
            task,
            [(1, 1), (2, 2)],
            max_path_deviation=4,
        )

        self.assertEqual(
            [call[2]['max_path_deviation'] for call in task.calls],
            [4, 4],
        )

    def test_direct_move_releases_keys_before_returning_on_death(self):
        class DirectTask:
            _xz = staticmethod(SRTaskBase._xz)
            _MOVE_RESULT_DEATH = SRTaskBase._MOVE_RESULT_DEATH
            position = (0, 0)
            is_dead = True
            camera_direction = 0
            release_count = 0

            def _release_move_keys(self):
                self.release_count += 1

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                pass

            def detect_camera_direction(self):
                pass

        task = DirectTask()

        result = SRTaskBase._move_direct(task, (0, 0), tolerance=1)

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_DEATH)
        self.assertEqual(task.release_count, 2)

    @patch.object(
        sr_task_base_module.time,
        'monotonic',
        side_effect=[0, SRTaskBase._MOVE_STALL_TIMEOUT],
    )
    def test_direct_move_fails_after_stall_timeout_without_progress(self, _monotonic):
        class StalledTask:
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _MOVE_STALL_TIMEOUT = SRTaskBase._MOVE_STALL_TIMEOUT
            _MOVE_RESULT_TIMEOUT = SRTaskBase._MOVE_RESULT_TIMEOUT
            position = (0, 0)
            is_dead = False
            camera_direction = 0
            _camera_direction_detected = True
            release_count = 0
            info = {}

            def _release_move_keys(self):
                self.release_count += 1

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                pass

            def detect_camera_direction(self):
                pass

            def rotate_camera(self, _degrees):
                pass

        task = StalledTask()

        result = SRTaskBase._move_direct(task, (0, 10), tolerance=1)

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_TIMEOUT)
        self.assertEqual(task.release_count, 2)

    def test_direct_move_does_not_press_direction_keys_in_blocked_actor_states(self):
        for blocked_state in (
                ActorState.FALL,
                ActorState.TELEPORT,
                ActorState.FALL_TELEPORT):
            with self.subTest(actor_state=blocked_state):
                class BlockedTask:
                    _xz = staticmethod(SRTaskBase._xz)
                    _angle_delta = staticmethod(SRTaskBase._angle_delta)
                    _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
                    _MOVE_KEYS = SRTaskBase._MOVE_KEYS
                    _MOVE_DURATION = SRTaskBase._MOVE_DURATION
                    _MOVE_STALL_TIMEOUT = SRTaskBase._MOVE_STALL_TIMEOUT
                    _MOVE_BLOCKED_ACTOR_STATES = SRTaskBase._MOVE_BLOCKED_ACTOR_STATES
                    _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
                    camera_direction = 0
                    _camera_direction_detected = True
                    info = {}

                    def __init__(self):
                        self.frame_count = 0
                        self.pressed_keys = []

                    @property
                    def position(self):
                        return (0, 10) if self.frame_count >= 3 else (0, 0)

                    @property
                    def actor_state(self):
                        return blocked_state if self.frame_count == 2 else ActorState.DEFAULT

                    @property
                    def is_dead(self):
                        return False

                    def _release_move_keys(self):
                        pass

                    def _require_packet_capture(self):
                        pass

                    def next_frame(self):
                        self.frame_count += 1

                    def detect_camera_direction(self):
                        pass

                    def rotate_camera(self, _degrees):
                        pass

                    def send_key_down(self, key):
                        self.pressed_keys.append(key)

                    def sleep(self, _seconds):
                        pass

                task = BlockedTask()

                result = SRTaskBase._move_direct(task, (0, 10), tolerance=1)

                self.assertEqual(result, SRTaskBase._MOVE_RESULT_SUCCESS)
                self.assertEqual(task.pressed_keys, [])

    def test_move_to_position_returns_false_on_timeout(self):
        class TimeoutTask:
            _xz = staticmethod(SRTaskBase._xz)
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            _MOVE_RESULT_DEATH = SRTaskBase._MOVE_RESULT_DEATH
            _MOVE_RESULT_TIMEOUT = SRTaskBase._MOVE_RESULT_TIMEOUT
            position = (0, 0)
            death_handled = False

            def _begin_movement_session(self):
                pass

            def _end_movement_session(self):
                pass

            def _require_packet_capture(self):
                pass

            def _move_direct(self, *_args, **_kwargs):
                return self._MOVE_RESULT_TIMEOUT

            def handle_death(self):
                self.death_handled = True
                return True

        task = TimeoutTask()

        result = SRTaskBase.move_to_position(task, (0, 0), (0, 10))

        self.assertFalse(result)
        self.assertFalse(task.death_handled)

    def test_move_to_position_returns_false_after_exceeding_path_deviation(self):
        class DeviatedTask:
            _xz = staticmethod(SRTaskBase._xz)
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            _MOVE_RESULT_DEATH = SRTaskBase._MOVE_RESULT_DEATH
            _MOVE_RESULT_TIMEOUT = SRTaskBase._MOVE_RESULT_TIMEOUT
            _MOVE_RESULT_PATH_DEVIATION = SRTaskBase._MOVE_RESULT_PATH_DEVIATION
            position = (0, 0)

            def __init__(self):
                self.calls = []
                self.death_handled = False

            def _begin_movement_session(self):
                pass

            def _end_movement_session(self):
                pass

            def _require_packet_capture(self):
                pass

            def _move_direct(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                if kwargs.get('max_path_deviation') is not None:
                    return self._MOVE_RESULT_PATH_DEVIATION
                return self._MOVE_RESULT_SUCCESS

            def handle_death(self):
                self.death_handled = True
                return True

        task = DeviatedTask()

        result = SRTaskBase.move_to_position(
            task,
            (0, 0),
            (0, 10),
            max_path_deviation=3,
        )

        self.assertFalse(result)
        self.assertEqual(task.calls[-1][1]['max_path_deviation'], 3)
        self.assertFalse(task.death_handled)

    def test_direct_move_fails_when_too_far_from_planned_path(self):
        class DeviatedTask:
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _closest_point_on_segment = staticmethod(SRTaskBase._closest_point_on_segment)
            _MOVE_RESULT_PATH_DEVIATION = SRTaskBase._MOVE_RESULT_PATH_DEVIATION
            position = (4, 0, 5)
            is_dead = False
            camera_direction = 0
            _camera_direction_detected = True
            info = {}

            def __init__(self):
                self.release_count = 0

            def _release_move_keys(self):
                self.release_count += 1

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                pass

            def detect_camera_direction(self):
                pass

            def rotate_camera(self, _degrees):
                pass

        task = DeviatedTask()

        result = SRTaskBase._move_direct(
            task,
            (0, 0, 10),
            tolerance=1,
            line_start=(0, 0, 0),
            max_path_deviation=3,
        )

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_PATH_DEVIATION)
        self.assertEqual(task.release_count, 2)


class _LookAtTask:
    _xz = staticmethod(SRTaskBase._xz)
    _angle_delta = staticmethod(SRTaskBase._angle_delta)

    def __init__(self, camera_direction=0, position=(0, 0), detected=True):
        self.camera_direction = camera_direction
        self.position = position
        self._camera_direction_detected = detected
        self.rotations = []
        self.capture_checks = 0
        self.frame_count = 0

    def _require_packet_capture(self):
        self.capture_checks += 1

    def next_frame(self):
        self.frame_count += 1

    def detect_camera_direction(self):
        return self.camera_direction

    def rotate_camera(self, degrees):
        self.rotations.append(degrees)


class LookAtTest(unittest.TestCase):
    def test_looks_at_absolute_angle_using_shortest_turn(self):
        task = _LookAtTask(camera_direction=350)

        result = SRTaskBase.look_at(task, 10)

        self.assertTrue(result)
        self.assertEqual(task.rotations, [20])
        self.assertEqual(task.capture_checks, 0)

    def test_looks_at_world_position(self):
        task = _LookAtTask(camera_direction=0, position=(10, 5, 20))

        result = SRTaskBase.look_at(task, (20, 99, 20))

        self.assertTrue(result)
        self.assertEqual(task.rotations, [90])
        self.assertEqual(task.capture_checks, 1)

    def test_does_not_rotate_when_direction_detection_fails(self):
        task = _LookAtTask(camera_direction=123, detected=False)

        result = SRTaskBase.look_at(task, 90)

        self.assertFalse(result)
        self.assertEqual(task.rotations, [])

    def test_same_position_needs_no_camera_detection(self):
        task = _LookAtTask(position=(10, 20))

        result = SRTaskBase.look_at(task, (10, 20))

        self.assertTrue(result)
        self.assertEqual(task.frame_count, 0)
        self.assertEqual(task.rotations, [])


if __name__ == "__main__":
    unittest.main()
