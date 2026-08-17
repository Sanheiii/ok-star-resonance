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


class HandleDeathTest(unittest.TestCase):
    @patch.object(sr_task_base_module.time, 'monotonic', side_effect=[0, 45])
    def test_returns_without_reviving_after_default_timeout(self, _monotonic):
        class DeadTask:
            is_dead = True

            def __init__(self):
                self.release_count = 0

            def _release_move_keys(self):
                self.release_count += 1

            def next_frame(self):
                raise AssertionError('timeout should stop death handling')

        task = DeadTask()

        result = SRTaskBase.handle_death(task)

        self.assertIsNone(result)
        self.assertEqual(task.release_count, 1)


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


class CameraDirectionProtectionTest(unittest.TestCase):
    @staticmethod
    def _task(direction=0, detected=True):
        task = object.__new__(SRTaskBase)
        task.frame = object()
        task.camera_direction = direction
        task._camera_direction_detected = detected
        task._camera_direction_protected_until = 0.0
        task._camera_direction_rotation_protected_until = 0.0
        return task

    def test_active_rotation_wins_over_stale_minimap_frame(self):
        task = self._task()

        with patch.object(
                sr_task_base_module.SRTaskBase,
                '_move_mouse_relative'), patch.object(
                    sr_task_base_module.time,
                    'monotonic',
                    side_effect=(10.0, 10.1)), patch.object(
                        sr_task_base_module.MinimapSectorAngleDetector,
                        'detect',
                        return_value=(0, 1, {})):
            SRTaskBase.rotate_camera(task, 90)
            SRTaskBase.detect_camera_direction(task)

        self.assertEqual(task.camera_direction, 90)
        self.assertTrue(task._camera_direction_detected)

    def test_large_detection_jump_is_rejected_and_close_detection_refreshes(self):
        task = self._task(direction=100)
        task._camera_direction_protected_until = 10.3

        with patch.object(
                sr_task_base_module.time,
                'monotonic',
                side_effect=(10.1, 10.2)), patch.object(
                    sr_task_base_module.MinimapSectorAngleDetector,
                    'detect',
                    side_effect=((130, 1, {}), (110, 1, {}))):
            SRTaskBase.detect_camera_direction(task)
            SRTaskBase.detect_camera_direction(task)

        self.assertEqual(task.camera_direction, 110)
        self.assertEqual(task._camera_direction_protected_until, 10.5)


class _PathTask:
    def __init__(self, results):
        self.position = (0, 0)
        self.results = iter(results)
        self.calls = []
        self.sleeps = []

    def _begin_movement_session(self):
        pass

    def _end_movement_session(self):
        pass

    def _release_move_keys(self):
        pass

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def move_to_position(self, start, target, **_kwargs):
        self.calls.append((start, target, _kwargs))
        return next(self.results)


class MovementReturnValueTest(unittest.TestCase):
    def test_mouse_key_alias_passes_hotkey_validation(self):
        task = object.__new__(SRTaskBase)

        self.assertEqual(task.validate_key("mouse2"), "mouse2")
        self.assertEqual(task.validate_key("mouse_x1"), "mouse_x1")
        self.assertEqual(task.validate_key("a"), "a")

    def test_path_returns_current_and_later_nodes_after_death(self):
        task = _PathTask([True, False])
        nodes = [(1, 1), (2, 2), (3, 3)]

        remaining = SRTaskBase.move_to_positions(task, nodes)

        self.assertEqual(remaining, [(2, 2), (3, 3)])

    def test_completed_path_returns_none(self):
        task = _PathTask([True, True])

        self.assertIsNone(SRTaskBase.move_to_positions(task, [(1, 1), (2, 2)]))

        self.assertEqual(
            [call[2]['keep_move_keys'] for call in task.calls],
            [False, True],
        )
        self.assertEqual(task.sleeps, [])

    def test_holding_move_keys_only_changes_the_different_keys(self):
        task = object.__new__(SRTaskBase)
        task._held_move_keys = ('w',)
        task.events = []
        task.send_key_down = lambda key: task.events.append(('down', key))
        task.send_key_up = lambda key: task.events.append(('up', key))

        SRTaskBase._hold_move_keys(task, ('w', 'd'))
        SRTaskBase._hold_move_keys(task, ('w',))

        self.assertEqual(task.events, [('down', 'd'), ('up', 'd')])

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

    def test_path_forwards_sprint_and_camera_options_to_each_segment(self):
        task = _PathTask([True, True])

        SRTaskBase.move_to_positions(
            task,
            [(1, 1), (2, 2)],
            enable_sprint=True,
            rotate_camera=False,
            camera_offset=90,
        )

        self.assertEqual(
            [call[2]['enable_sprint'] for call in task.calls],
            [True, True],
        )
        self.assertEqual(
            [call[2]['rotate_camera'] for call in task.calls],
            [False, False],
        )
        self.assertEqual(
            [call[2]['camera_offset'] for call in task.calls],
            [90, 90],
        )

    def test_movement_options_default_to_sprint_off_and_camera_rotation_on(self):
        task = _PathTask([True])

        SRTaskBase.move_to_positions(task, [(1, 1)])

        self.assertFalse(task.calls[0][2]['enable_sprint'])
        self.assertTrue(task.calls[0][2]['rotate_camera'])
        self.assertEqual(task.calls[0][2]['camera_offset'], 0)

    def test_clockwise_camera_offset_uses_left_strafe_to_move_forward(self):
        class DirectTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _MOVE_KEYS = SRTaskBase._MOVE_KEYS
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            camera_direction = 0
            _camera_direction_detected = True
            actor_state = ActorState.DEFAULT
            is_dead = False
            info = {}

            def __init__(self):
                self.frame_count = 0
                self.rotations = []
                self.pressed_keys = []

            @property
            def position(self):
                return (0, 10) if self.frame_count >= 3 else (0, 0)

            def _release_move_keys(self):
                pass

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                self.frame_count += 1

            def detect_camera_direction(self):
                pass

            def rotate_camera(self, degrees):
                self.rotations.append(degrees)
                self.camera_direction = (self.camera_direction + degrees) % 360

            def send_key_down(self, key):
                self.pressed_keys.append(key)

            def sleep(self, _seconds):
                pass

        task = DirectTask()

        result = SRTaskBase._move_direct(
            task,
            (0, 10),
            tolerance=1,
            camera_offset=90,
        )

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_SUCCESS)
        self.assertEqual(task.rotations, [90])
        self.assertEqual(task.pressed_keys, ['a'])

    def test_direct_move_can_disable_camera_rotation(self):
        class DirectTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            is_dead = False
            camera_direction = 0
            _camera_direction_detected = True
            info = {}

            def __init__(self):
                self.frame_count = 0
                self.rotations = []

            @property
            def position(self):
                return (10, 0) if self.frame_count >= 2 else (0, 0)

            def _release_move_keys(self):
                pass

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                self.frame_count += 1

            def detect_camera_direction(self):
                pass

            def rotate_camera(self, degrees):
                self.rotations.append(degrees)

        task = DirectTask()

        result = SRTaskBase._move_direct(
            task,
            (10, 0),
            tolerance=1,
            rotate_camera=False,
        )

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_SUCCESS)
        self.assertEqual(task.rotations, [])

    def test_direct_move_waits_after_initial_camera_rotation(self):
        class DirectTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            is_dead = False
            camera_direction = 0
            _camera_direction_detected = True
            info = {}

            def __init__(self):
                self.frame_count = 0
                self.events = []

            @property
            def position(self):
                return (10, 0) if self.frame_count >= 2 else (0, 0)

            def _release_move_keys(self):
                pass

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                self.frame_count += 1

            def detect_camera_direction(self):
                pass

            def rotate_camera(self, degrees):
                self.events.append(('rotate', degrees))

            def sleep(self, seconds):
                self.events.append(('sleep', seconds))

        task = DirectTask()

        result = SRTaskBase._move_direct(task, (10, 0), tolerance=1)

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_SUCCESS)
        self.assertEqual(task.events, [('rotate', 90), ('sleep', 0.1)])

    def test_enabled_sprint_waits_for_full_initial_cooldown(self):
        class SprintTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _MOVE_KEYS = SRTaskBase._MOVE_KEYS
            _MOVE_DURATION = SRTaskBase._MOVE_DURATION
            _MOVE_STALL_TIMEOUT = SRTaskBase._MOVE_STALL_TIMEOUT
            _MOVE_BLOCKED_ACTOR_STATES = SRTaskBase._MOVE_BLOCKED_ACTOR_STATES
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            _CAMERA_CORRECTION_THRESHOLD = SRTaskBase._CAMERA_CORRECTION_THRESHOLD
            _SPRINT_COOLDOWN = SRTaskBase._SPRINT_COOLDOWN
            _SPRINT_MIN_DISTANCE = SRTaskBase._SPRINT_MIN_DISTANCE
            camera_direction = 0
            _camera_direction_detected = True
            actor_state = ActorState.DEFAULT
            is_dead = False
            info = {}

            def __init__(self):
                self.frame_count = 0
                self.sent_keys = []

            @property
            def position(self):
                return (0, 6) if self.frame_count >= 4 else (0, 0)

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

            def send_key_down(self, _key):
                pass

            def send_key(self, key, _duration=None):
                self.sent_keys.append(key)

            def get_custom_key(self, action):
                assert action == "Rush"
                return "mouse2"

            def _sprint_prompt_visible(self):
                return True

            def sleep(self, _seconds):
                pass

        task = SprintTask()

        with patch.object(
                sr_task_base_module.time,
                'monotonic',
                side_effect=(100, 100, 100.99, 101),
        ):
            result = SRTaskBase._move_direct(
                task,
                (0, 6),
                tolerance=0.5,
                enable_sprint=True,
            )

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_SUCCESS)
        self.assertEqual(task.sent_keys, ["mouse2"])

    def test_sprint_is_skipped_at_five_metres(self):
        class SprintTask:
            _MOVE_KEYS = SRTaskBase._MOVE_KEYS
            _SPRINT_COOLDOWN = SRTaskBase._SPRINT_COOLDOWN
            _SPRINT_MIN_DISTANCE = SRTaskBase._SPRINT_MIN_DISTANCE

            def __init__(self):
                self.sent_keys = []

            def _sprint_prompt_visible(self):
                return True

            def send_key(self, key, duration):
                self.sent_keys.append((key, duration))

        task = SprintTask()

        last_sprint_at = SRTaskBase._try_sprint(
            task,
            enable_sprint=True,
            camera_aligned=True,
            keys=("w",),
            now=101,
            last_sprint_at=100,
            remaining_distance=5,
        )

        self.assertEqual(last_sprint_at, 100)
        self.assertEqual(task.sent_keys, [])

    def test_sprint_uses_configured_rush_key_for_clockwise_camera_offset(self):
        class SprintTask:
            _MOVE_KEYS = SRTaskBase._MOVE_KEYS
            _SPRINT_COOLDOWN = SRTaskBase._SPRINT_COOLDOWN
            _SPRINT_MIN_DISTANCE = SRTaskBase._SPRINT_MIN_DISTANCE

            def __init__(self):
                self.sent_keys = []

            def _sprint_prompt_visible(self):
                return True

            def send_key(self, key, duration=None):
                self.sent_keys.append((key, duration))

            def get_custom_key(self, action):
                return "mouse2"

        task = SprintTask()

        last_sprint_at = SRTaskBase._try_sprint(
            task,
            enable_sprint=True,
            camera_aligned=True,
            keys=("a",),
            now=101,
            last_sprint_at=100,
            remaining_distance=20,
            camera_offset=90,
        )

        self.assertEqual(last_sprint_at, 101)
        self.assertEqual(
            task.sent_keys,
            [("mouse2", None)],
        )

    def test_direct_move_releases_keys_before_returning_on_death(self):
        class DirectTask(SRTaskBase):
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

    def test_move_to_position_stops_when_scene_changes(self):
        class SceneChangeTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            _MOVE_RESULT_DEATH = SRTaskBase._MOVE_RESULT_DEATH
            _MOVE_RESULT_SCENE_CHANGED = SRTaskBase._MOVE_RESULT_SCENE_CHANGED
            position = (0, 0)
            is_dead = False

            def __init__(self):
                self._movement_session_depth = 0
                self._movement_scene_id = None
                self._held_move_keys = ('w',)
                self.current_scene_id = 100
                self.released_keys = []

            @property
            def scene_id(self):
                return self.current_scene_id

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                self.current_scene_id = 200

            def send_key_up(self, key):
                self.released_keys.append(key)

        task = SceneChangeTask()

        result = SRTaskBase.move_to_position(task, (0, 0), (0, 10))

        self.assertFalse(result)
        self.assertEqual(task.released_keys, ['w'])

    def test_move_to_position_returns_false_when_loading_is_detected(self):
        class LoadingTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _MOVE_RESULT_SUCCESS = SRTaskBase._MOVE_RESULT_SUCCESS
            _MOVE_RESULT_DEATH = SRTaskBase._MOVE_RESULT_DEATH
            _MOVE_RESULT_LOADING = SRTaskBase._MOVE_RESULT_LOADING
            position = (0, 0)
            is_dead = False
            frame = object()

            def __init__(self):
                self.release_count = 0

            def _begin_movement_session(self):
                pass

            def _end_movement_session(self):
                pass

            def _release_move_keys(self):
                self.release_count += 1

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                pass

            def find_one(self, feature):
                return feature == 'loading'

            def handle_death(self):
                raise AssertionError('loading must not be handled as death')

        task = LoadingTask()

        result = SRTaskBase.move_to_position(task, (0, 0), (0, 10))

        self.assertFalse(result)
        self.assertEqual(task.release_count, 2)

    @patch.object(
        sr_task_base_module.time,
        'monotonic',
        side_effect=[
            0,
            SRTaskBase._MOVE_STALL_TIMEOUT,
            SRTaskBase._MOVE_STALL_TIMEOUT
            + SRTaskBase._MOVE_STALL_JUMP_EXTENSION,
        ],
    )
    def test_direct_move_jumps_once_and_extends_stall_timeout(self, _monotonic):
        class StalledTask(SRTaskBase):
            _xz = staticmethod(SRTaskBase._xz)
            _angle_delta = staticmethod(SRTaskBase._angle_delta)
            _segment_reaches_target = staticmethod(SRTaskBase._segment_reaches_target)
            _MOVE_STALL_TIMEOUT = SRTaskBase._MOVE_STALL_TIMEOUT
            _MOVE_STALL_JUMP_EXTENSION = SRTaskBase._MOVE_STALL_JUMP_EXTENSION
            _MOVE_RESULT_TIMEOUT = SRTaskBase._MOVE_RESULT_TIMEOUT
            position = (0, 0)
            is_dead = False
            camera_direction = 0
            _camera_direction_detected = True
            release_count = 0
            sent_keys = []
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

            def send_key(self, key):
                self.sent_keys.append(key)

        task = StalledTask()

        result = SRTaskBase._move_direct(task, (0, 10), tolerance=1)

        self.assertEqual(result, SRTaskBase._MOVE_RESULT_TIMEOUT)
        self.assertEqual(task.sent_keys, ['space'])
        self.assertEqual(task.release_count, 3)

    def test_direct_move_does_not_press_direction_keys_in_blocked_actor_states(self):
        for blocked_state in (
                ActorState.FALL,
                ActorState.TELEPORT,
                ActorState.FALL_TELEPORT):
            with self.subTest(actor_state=blocked_state):
                class BlockedTask(SRTaskBase):
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
        class DeviatedTask(SRTaskBase):
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
        class DeviatedTask(SRTaskBase):
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
