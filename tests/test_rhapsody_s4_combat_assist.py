import unittest
import threading
from unittest.mock import patch

from src.packet_capture.parser import ATTR_CD_ACCELERATE_PCT
from src.tasks.DissonanceS4CombatAssistTask import (
    DissonanceS4CombatAssistTask,
)


class DissonanceS4CombatAssistTaskTest(unittest.TestCase):
    @staticmethod
    def make_keyboard_task():
        task = object.__new__(DissonanceS4CombatAssistTask)
        task._physical_input_lock = threading.Lock()
        task._last_physical_input_time = None
        task._physical_keys_down = set()
        task.logger = unittest.mock.Mock()
        return task

    def test_physical_input_blocks_until_delay_expires(self):
        task = self.make_keyboard_task()
        event = unittest.mock.Mock(
            vk_code=0x31, action="down", injected=False
        )
        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=10.0,
        ):
            task._on_physical_keyboard_event(event)

        self.assertTrue(task._is_keyboard_blocking(now=10.19))
        self.assertTrue(task._is_keyboard_blocking(now=100.0))

        event.action = "up"
        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=100.0,
        ):
            task._on_physical_keyboard_event(event)
        self.assertTrue(task._is_keyboard_blocking(now=100.19))
        self.assertFalse(task._is_keyboard_blocking(now=100.201))

    def test_all_physical_keys_must_be_released_before_delay_starts(self):
        task = self.make_keyboard_task()

        for vk_code in (0x41, 0x53):
            task._on_physical_keyboard_event(
                unittest.mock.Mock(
                    vk_code=vk_code, action="down", injected=False
                )
            )
        task._on_physical_keyboard_event(
            unittest.mock.Mock(
                vk_code=0x53, action="up", injected=False
            )
        )

        self.assertTrue(task._is_keyboard_blocking(now=1000.0))
        self.assertEqual(task._physical_keys_down, {0x41})

    def test_f9_does_not_update_physical_input_time(self):
        task = self.make_keyboard_task()
        task._on_physical_keyboard_event(
            unittest.mock.Mock(
                vk_code=task.VK_F9, action="down", injected=False
            )
        )
        self.assertIsNone(task._last_physical_input_time)

    def test_injected_input_does_not_update_physical_input_time(self):
        task = self.make_keyboard_task()
        task._on_physical_keyboard_event(
            unittest.mock.Mock(vk_code=0x31, action="down", injected=True)
        )
        self.assertIsNone(task._last_physical_input_time)

    def test_monitor_failure_disables_blocking_without_raising(self):
        task = self.make_keyboard_task()
        task._physical_keyboard_monitor = unittest.mock.Mock(
            running=False,
            error=RuntimeError("hook failed"),
        )
        task._physical_keyboard_monitor.start.return_value = False
        task._keyboard_monitor_error_logged = False
        task._keyboard_monitor_start_attempted = False

        self.assertFalse(task._ensure_keyboard_monitor())
        self.assertFalse(task._ensure_keyboard_monitor())
        task.logger.warning.assert_called_once()
        task._physical_keyboard_monitor.start.assert_called_once()

    def test_action_boundary_sees_physical_input_during_selection(self):
        task = self.make_keyboard_task()
        task._last_physical_input_time = 10.0
        task._perform_action = unittest.mock.Mock()

        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=10.1,
        ):
            self.assertFalse(task._perform_action_if_clear("2"))

        task._perform_action.assert_not_called()

    def test_build_monitor_values_tracks_requested_resources(self):
        now = 100.0
        cooldowns = {
            230801: {
                "skill_id": 2308,
                "duration": 10000,
                "valid_cd_time": 2000,
                "received_at": 99.0,
            },
            231001: {
                "skill_id": 2310,
                "duration": 5000,
                "valid_cd_time": 5000,
                "received_at": 100.0,
            },
        }

        values = DissonanceS4CombatAssistTask.build_monitor_values(
            cooldowns,
            {23001: 6500, 23011: 4},
            {90203: 10000, 90205: 10000},
            now,
            player_attributes={ATTR_CD_ACCELERATE_PCT: 1234},
        )

        self.assertEqual(values["Harmonic Anthem"], "6.9s")
        self.assertEqual(values["Heroic Anthem"], "Ready")
        self.assertEqual(values["Amplified Beat Free"], "Yes")
        self.assertEqual(values["Flame Rhapsody Free"], "Yes")
        self.assertEqual(values["Harmonic Anthem Charges"], 0)
        self.assertEqual(values["Performance Energy"], 65)
        self.assertEqual(values["Performance Passion"], 4)
        self.assertEqual(values["Cooldown Acceleration"], "12.34%")
        self.assertEqual(values["Flame Rhapsody"], "Ready")

    def test_attack_count_enhancement_does_not_mark_amplified_beat_free(self):
        values = DissonanceS4CombatAssistTask.build_monitor_values(
            {},
            {},
            {90176: 2},
            now=100.0,
        )

        self.assertEqual(values["Amplified Beat Free"], "No")
        self.assertEqual(values["Flame Rhapsody Free"], "No")
        self.assertTrue(
            all(
                values[name] == "Ready"
                for name in DissonanceS4CombatAssistTask.SKILLS.values()
            )
        )

    def test_normal_amplified_beat_value_is_not_free(self):
        values = DissonanceS4CombatAssistTask.build_monitor_values(
            {}, {}, {90203: 3000}, now=100.0
        )

        self.assertEqual(values["Amplified Beat Free"], "No")

    def test_flame_rhapsody_requires_full_free_cost_value(self):
        normal = DissonanceS4CombatAssistTask.build_monitor_values(
            {}, {}, {90205: 3000}, now=100.0
        )
        free = DissonanceS4CombatAssistTask.build_monitor_values(
            {}, {}, {90205: 10000}, now=100.0
        )

        self.assertEqual(normal["Flame Rhapsody Free"], "No")
        self.assertEqual(free["Flame Rhapsody Free"], "Yes")

    def test_harmonic_anthem_charge_count_uses_recharge_progress(self):
        cooldown = {
            "duration": 10000,
            "valid_cd_time": 9000,
            "received_at": 99.0,
        }

        self.assertEqual(
            DissonanceS4CombatAssistTask.available_charges(
                cooldown, now=100.0, max_charges=2
            ),
            1,
        )
        self.assertEqual(
            DissonanceS4CombatAssistTask.available_charges(
                cooldown, now=110.0, max_charges=2
            ),
            2,
        )

    def test_format_cooldown_never_returns_negative_time(self):
        self.assertEqual(
            DissonanceS4CombatAssistTask.format_cooldown(
                {
                    "duration": 1000,
                    "valid_cd_time": 900,
                    "received_at": 1.0,
                },
                2.0,
            ),
            "Ready",
        )

    def test_cooldown_acceleration_doubles_elapsed_progress_at_100_percent(self):
        cooldown = {
            "duration": 10000,
            "valid_cd_time": 0,
            "received_at": 99.0,
        }

        self.assertEqual(
            DissonanceS4CombatAssistTask.format_cooldown(
                cooldown,
                now=100.0,
                cooldown_acceleration=10000,
            ),
            "8.0s",
        )

    def test_center_stage_interval_uses_real_time_not_accelerated_progress(self):
        task = DissonanceS4CombatAssistTask
        cooldowns = {
            231601: {
                "skill_id": 2316,
                "duration": 10000,
                "valid_cd_time": 0,
                "received_at": 100.0,
            },
        }
        attributes = {ATTR_CD_ACCELERATE_PCT: 10000}

        self.assertEqual(
            task.select_action(
                cooldowns,
                {23011: 2},
                {},
                attributes,
                110.0,
            ),
            "1",
        )
        self.assertEqual(
            task.select_action(
                cooldowns,
                {23011: 2},
                {},
                attributes,
                115.01,
            ),
            "5",
        )

    def test_center_stage_interval_starts_when_server_confirms_cooldown(self):
        task = object.__new__(DissonanceS4CombatAssistTask)
        task._center_stage_was_cooling = None
        task._center_stage_last_success_at = None
        cooling = {
            231601: {
                "skill_id": 2316,
                "duration": 10000,
                "valid_cd_time": 0,
                "received_at": 100.0,
            },
        }

        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=20.0,
        ):
            self.assertFalse(task._is_center_stage_due(cooling, {}, 100.0))
        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=34.99,
        ):
            self.assertFalse(task._is_center_stage_due({}, {}, 115.0))
        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=35.01,
        ):
            self.assertTrue(task._is_center_stage_due({}, {}, 115.01))

    def test_action_priority(self):
        task = DissonanceS4CombatAssistTask
        cooling_down = {
            230801: {
                "skill_id": 2308,
                "duration": 10000,
                "valid_cd_time": 0,
                "received_at": 100.0,
            },
            231001: {
                "skill_id": 2310,
                "duration": 10000,
                "valid_cd_time": 0,
                "received_at": 100.0,
            },
        }

        self.assertEqual(
            task.select_action(cooling_down, {23011: 2}, {}, {}, 100.0),
            "1",
        )
        center_stage_overdue = dict(cooling_down)
        center_stage_overdue[231601] = {
            "skill_id": 2316,
            "duration": 15000,
            "valid_cd_time": 15001,
            "received_at": 100.0,
        }
        self.assertEqual(
            task.select_action(
                center_stage_overdue,
                {23011: 2},
                {},
                {},
                100.0,
            ),
            "5",
        )
        center_stage_cooling_down = dict(cooling_down)
        center_stage_cooling_down[231601] = {
            "skill_id": 2316,
            "duration": 30000,
            "valid_cd_time": 15001,
            "received_at": 100.0,
        }
        self.assertEqual(
            task.select_action(
                center_stage_cooling_down,
                {23011: 2},
                {},
                {},
                100.0,
            ),
            "1",
        )
        self.assertEqual(task.select_action({}, {}, {}, {}, 100.0), "2")
        self.assertEqual(
            task.select_action(cooling_down, {}, {90205: 10000}, {}, 100.0),
            "3",
        )
        heroic_ready = dict(cooling_down)
        heroic_ready[231001] = dict(heroic_ready[231001], valid_cd_time=10000)
        self.assertEqual(
            task.select_action(heroic_ready, {23001: 1600}, {}, {}, 100.0),
            "4",
        )
        self.assertEqual(
            task.select_action(cooling_down, {}, {}, {}, 100.0),
            "r",
        )

    def test_pressing_skill_two_starts_one_second_restriction(self):
        task = object.__new__(DissonanceS4CombatAssistTask)
        task._skill_two_restricted_until = 0.0
        task.send_key = lambda key: None

        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=10.0,
        ):
            task._perform_action("2")
        self.assertEqual(task._skill_two_restricted_until, 11.0)
        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=10.99,
        ):
            self.assertTrue(task._is_skill_two_restricted())
        with patch(
            "src.tasks.DissonanceS4CombatAssistTask.time.monotonic",
            return_value=11.0,
        ):
            self.assertFalse(task._is_skill_two_restricted())

    def test_skill_two_restriction_allows_only_one_then_three(self):
        task = DissonanceS4CombatAssistTask

        self.assertEqual(
            task.select_action(
                {},
                {task.PERFORMANCE_PASSION_RESOURCE_ID: 2},
                {},
                {},
                100.0,
                skill_two_restricted=True,
                center_stage_due=True,
            ),
            "1",
        )
        self.assertEqual(
            task.select_action(
                {},
                {},
                {task.FLAME_RHAPSODY_FREE_COST_ID: 10000},
                {},
                100.0,
                skill_two_restricted=True,
                center_stage_due=True,
            ),
            "3",
        )
        self.assertEqual(
            task.select_action(
                {},
                {},
                {},
                {},
                100.0,
                skill_two_restricted=True,
                center_stage_due=True,
            ),
            None,
        )

if __name__ == "__main__":
    unittest.main()
