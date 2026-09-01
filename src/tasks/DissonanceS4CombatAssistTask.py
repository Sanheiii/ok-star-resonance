import time
import threading

from src.input.PhysicalKeyboardMonitor import PhysicalKeyboardMonitor
from src.packet_capture.parser import ATTR_CD_ACCELERATE_PCT
from src.tasks.SRTriggerTask import SRTriggerTask


class DissonanceS4CombatAssistTask(SRTriggerTask):
    """Assist the Beat Performer S4 dissonance combat rotation."""

    ACTION_KEY_SETTINGS = {
        "click": ("Basic Attack", "mouse1"),
        "1": ("Amplified Beat", "1"),
        "2": ("Harmonic Anthem", "2"),
        "3": ("Flame Rhapsody", "3"),
        "4": ("Heroic Anthem", "4"),
        "5": ("Center Stage", "5"),
        "r": ("Ultimate Skill", "r"),
    }

    SKILLS = {
        2308: "Harmonic Anthem",
        2309: "Flame Rhapsody",
        2310: "Heroic Anthem",
        2316: "Center Stage",
        2335: "Ascension: Infinite Rhapsody",
    }
    AMPLIFIED_BEAT_FREE_COST_ID = 90203
    FLAME_RHAPSODY_FREE_COST_ID = 90205
    PERFORMANCE_ENERGY_RESOURCE_ID = 23001
    PERFORMANCE_PASSION_RESOURCE_ID = 23011
    FIGHT_RESOURCE_LAYOUT = (
        90001, 90007, 90011, 90017, 90021, 90027,
        23001, 23007, 23011, 23017, 23021, 23027, 23031, 23037,
    )
    HARMONIC_ANTHEM_SKILL_ID = 2308
    FLAME_RHAPSODY_SKILL_ID = 2309
    HEROIC_ANTHEM_SKILL_ID = 2310
    CENTER_STAGE_SKILL_ID = 2316
    INFINITE_RHAPSODY_SKILL_ID = 2335
    HARMONIC_ANTHEM_MAX_CHARGES = 2
    CENTER_STAGE_INTERVAL_MS = 15000
    SKILL_TWO_RESTRICTION_SECONDS = 1.0
    LOOP_INTERVAL = 0.05
    PHYSICAL_INPUT_BLOCK_DELAY = 0.2
    VK_F9 = 0x78

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Dissonance S4 Combat Assist"
        self.description = (
            "Automatically plays whack-a-mole with the Dissonance Critical "
            "Acclaim build. Requires the packet capture tool to be enabled."
        )
        self.default_config.update({
            label: default
            for label, default in self.ACTION_KEY_SETTINGS.values()
        })
        self._skill_two_restricted_until = 0.0
        self._center_stage_was_cooling = None
        self._center_stage_last_success_at = None
        self._physical_input_lock = threading.Lock()
        self._last_physical_input_time = None
        self._physical_keys_down = set()
        self._physical_keyboard_monitor = PhysicalKeyboardMonitor(
            self._on_physical_keyboard_event
        )
        self._keyboard_monitor_start_attempted = False
        self._keyboard_monitor_error_logged = False
        self.trigger_interval = self.LOOP_INTERVAL

    def run(self):
        self._ensure_keyboard_monitor()
        tool = self.packet_capture_tool
        if tool is None or not tool.is_capturing:
            self.info["Capture Status"] = "Waiting for packet capture"
            return

        if not self.fight_resource_layout:
            self.set_fight_resource_layout(self.FIGHT_RESOURCE_LAYOUT)

        self.info["Capture Status"] = "Monitoring"
        now = time.time()
        cooldowns = self.skill_cooldowns
        resources = self.fight_resources
        temp_attributes = self.temp_attributes
        player_attributes = self.player_attributes
        values = self.build_monitor_values(
            cooldowns,
            resources,
            temp_attributes,
            now=now,
            player_attributes=player_attributes,
        )
        for key, value in values.items():
            self.info[key] = value

        center_stage_due = self._is_center_stage_due(
            cooldowns,
            player_attributes,
            now,
        )
        if self._is_keyboard_blocking():
            self.sleep(self.LOOP_INTERVAL)
            return
        action = self.select_action(
            cooldowns,
            resources,
            temp_attributes,
            player_attributes,
            now,
            skill_two_restricted=self._is_skill_two_restricted(),
            center_stage_due=center_stage_due,
        )
        self._perform_action_if_clear(action)

    def on_enabled(self):
        self._reset_runtime_state()
        self._keyboard_monitor_start_attempted = False
        self._ensure_keyboard_monitor()

    def disable(self):
        self._stop_keyboard_monitor()
        super().disable()
        self._reset_runtime_state()

    def on_destroy(self):
        self._stop_keyboard_monitor()
        super().on_destroy()

    def _ensure_keyboard_monitor(self):
        monitor = self._physical_keyboard_monitor
        if monitor.running:
            return True
        if self._keyboard_monitor_start_attempted:
            return False
        self._keyboard_monitor_start_attempted = True
        if monitor.start():
            self._keyboard_monitor_error_logged = False
            self.logger.info("physical keyboard monitor started")
            return True
        if not self._keyboard_monitor_error_logged:
            self.logger.warning(
                f"physical keyboard monitor failed; input blocking disabled: "
                f"{monitor.error}"
            )
            self._keyboard_monitor_error_logged = True
        return False

    def _stop_keyboard_monitor(self):
        monitor = self._physical_keyboard_monitor
        was_running = monitor.running
        monitor.stop()
        if was_running:
            self.logger.info("physical keyboard monitor stopped")

    def _on_physical_keyboard_event(self, event):
        # The monitor already filters injected events. Keep this guard here as
        # well so this state boundary cannot be extended by synthetic input.
        if event.injected or event.vk_code == self.VK_F9:
            return
        now = time.monotonic()
        with self._physical_input_lock:
            self._last_physical_input_time = now
            if event.action == "up":
                self._physical_keys_down.discard(event.vk_code)
            else:
                self._physical_keys_down.add(event.vk_code)

    def _is_keyboard_blocking(self, now=None):
        delay = self.PHYSICAL_INPUT_BLOCK_DELAY
        with self._physical_input_lock:
            last_input = self._last_physical_input_time
            keys_down = bool(self._physical_keys_down)
        if delay <= 0:
            return False
        if keys_down:
            return True
        if last_input is None:
            return False
        if now is None:
            now = time.monotonic()
        return now - last_input < delay

    def _perform_action_if_clear(self, action):
        # Physical input can arrive after the state check in run() while this
        # iteration is selecting an action. Recheck at the action boundary so
        # no newly selected action starts after the player takes over.
        if self._is_keyboard_blocking():
            return False
        self._perform_action(action)
        return True

    def _reset_runtime_state(self):
        self._skill_two_restricted_until = 0.0
        self._center_stage_was_cooling = None
        self._center_stage_last_success_at = None
        with self._physical_input_lock:
            self._last_physical_input_time = None
            self._physical_keys_down.clear()

    def _is_skill_two_restricted(self):
        return time.monotonic() < self._skill_two_restricted_until

    def _is_center_stage_due(self, cooldowns, player_attributes, now):
        cooldown = self._cooldowns_by_skill(cooldowns).get(
            self.CENTER_STAGE_SKILL_ID
        )
        acceleration = int(player_attributes.get(ATTR_CD_ACCELERATE_PCT, 0))
        cooling = (
            cooldown is not None
            and not self.is_skill_ready(cooldown, now, acceleration)
        )
        monotonic_now = time.monotonic()
        if cooling and self._center_stage_was_cooling is not True:
            self._center_stage_last_success_at = monotonic_now
        self._center_stage_was_cooling = cooling
        if cooling:
            return False
        if self._center_stage_last_success_at is None:
            return True
        return (
            monotonic_now - self._center_stage_last_success_at
            > self.CENTER_STAGE_INTERVAL_MS / 1000.0
        )

    def _perform_action(self, action):
        if action is not None:
            label, default = self.ACTION_KEY_SETTINGS[action]
            key = self.config.get(label)
            self.send_key(key)
            if action == "2":
                self._skill_two_restricted_until = (
                    time.monotonic() + self.SKILL_TWO_RESTRICTION_SECONDS
                )

    @classmethod
    def select_action(
        cls,
        cooldowns,
        resources,
        temp_attributes,
        player_attributes,
        now,
        skill_two_restricted=False,
        center_stage_due=None,
    ):
        cooldowns_by_skill = cls._cooldowns_by_skill(cooldowns)
        amplified_beat_free = (
            int(temp_attributes.get(cls.AMPLIFIED_BEAT_FREE_COST_ID, 0)) >= 10000
        )
        performance_passion = int(
            resources.get(cls.PERFORMANCE_PASSION_RESOURCE_ID, 0)
        )
        acceleration = int(player_attributes.get(ATTR_CD_ACCELERATE_PCT, 0))
        flame_rhapsody_free = (
            int(temp_attributes.get(cls.FLAME_RHAPSODY_FREE_COST_ID, 0)) >= 10000
        )
        if skill_two_restricted:
            if amplified_beat_free or performance_passion >= 2:
                return "1"
            if flame_rhapsody_free:
                return "3"
            return None

        center_stage_cooldown = cooldowns_by_skill.get(cls.CENTER_STAGE_SKILL_ID)
        if center_stage_due is None:
            center_stage_due = (
                center_stage_cooldown is not None
                and cls.is_skill_ready(
                    center_stage_cooldown,
                    now,
                    acceleration,
                )
                and cls.cooldown_real_elapsed_ms(
                    center_stage_cooldown,
                    now,
                    acceleration,
                ) > cls.CENTER_STAGE_INTERVAL_MS
            )
        if center_stage_due:
            return "5"
        if amplified_beat_free or performance_passion >= 2:
            return "1"

        if flame_rhapsody_free:
            return "3"

        harmonic_cooldown = cooldowns_by_skill.get(cls.HARMONIC_ANTHEM_SKILL_ID)
        if (
            cls.available_charges(
                harmonic_cooldown,
                now,
                cls.HARMONIC_ANTHEM_MAX_CHARGES,
                acceleration,
            ) >= 2
        ):
            return "2"
        heroic_cooldown = cooldowns_by_skill.get(cls.HEROIC_ANTHEM_SKILL_ID)
        performance_energy = int(
            resources.get(cls.PERFORMANCE_ENERGY_RESOURCE_ID, 0) / 100
        )
        if (
            cls.is_skill_ready(heroic_cooldown, now, acceleration)
            and performance_energy > 15
        ):
            return "4"
        if cls.is_skill_ready(harmonic_cooldown, now, acceleration):
            return "2"
        infinite_rhapsody_cooldown = cooldowns_by_skill.get(
            cls.INFINITE_RHAPSODY_SKILL_ID
        )
        if cls.is_skill_ready(infinite_rhapsody_cooldown, now, acceleration):
            return "r"
        return "click"

    @classmethod
    def build_monitor_values(
        cls, cooldowns, resources, temp_attributes, now, player_attributes=None
    ):
        player_attributes = player_attributes or {}
        values = {}
        cooldowns_by_skill = cls._cooldowns_by_skill(cooldowns)
        cooldown_acceleration = int(
            player_attributes.get(ATTR_CD_ACCELERATE_PCT, 0)
        )
        for skill_id, name in cls.SKILLS.items():
            # syncSkillCDs is a sparse delta. A configured skill with no
            # current entry is not on cooldown, so complete the view as Ready.
            values[name] = cls.format_cooldown(
                cooldowns_by_skill.get(skill_id),
                now,
                missing="Ready",
                cooldown_acceleration=cooldown_acceleration,
            )

        enhancement_value = int(
            temp_attributes.get(cls.AMPLIFIED_BEAT_FREE_COST_ID, 0)
        )
        values["Amplified Beat Free"] = (
            "Yes" if enhancement_value >= 10000 else "No"
        )
        flame_rhapsody_value = int(
            temp_attributes.get(cls.FLAME_RHAPSODY_FREE_COST_ID, 0)
        )
        values["Flame Rhapsody Free"] = (
            "Yes" if flame_rhapsody_value >= 10000 else "No"
        )
        values["Harmonic Anthem Charges"] = cls.available_charges(
            cooldowns_by_skill.get(cls.HARMONIC_ANTHEM_SKILL_ID),
            now,
            cls.HARMONIC_ANTHEM_MAX_CHARGES,
            cooldown_acceleration,
        )
        values["Performance Energy"] = int(
            resources.get(cls.PERFORMANCE_ENERGY_RESOURCE_ID, 0) / 100
        )
        values["Performance Passion"] = int(
            resources.get(cls.PERFORMANCE_PASSION_RESOURCE_ID, 0)
        )
        values["Cooldown Acceleration"] = f"{cooldown_acceleration / 100:.2f}%"
        return values

    @staticmethod
    def _cooldowns_by_skill(cooldowns):
        return {
            int(cooldown.get("skill_id", 0)): cooldown
            for cooldown in cooldowns.values()
        }

    @classmethod
    def is_skill_ready(cls, cooldown, now, cooldown_acceleration=0):
        return cls.remaining_cooldown_ms(
            cooldown, now, cooldown_acceleration
        ) <= 0

    @staticmethod
    def remaining_cooldown_ms(cooldown, now, cooldown_acceleration=0):
        if cooldown is None:
            return 0.0
        duration = int(cooldown.get("duration", 0))
        valid_cd_time = int(cooldown.get("valid_cd_time", 0))
        received_at = float(cooldown.get("received_at", now))
        elapsed_ms = max(0.0, now - received_at) * 1000.0
        speed_multiplier = max(0.0, 1.0 + cooldown_acceleration / 10000.0)
        return max(
            0.0,
            duration - valid_cd_time - elapsed_ms * speed_multiplier,
        )

    @staticmethod
    def cooldown_progress_ms(cooldown, now, cooldown_acceleration=0):
        valid_cd_time = int(cooldown.get("valid_cd_time", 0))
        received_at = float(cooldown.get("received_at", now))
        elapsed_ms = max(0.0, now - received_at) * 1000.0
        speed_multiplier = max(0.0, 1.0 + cooldown_acceleration / 10000.0)
        return max(0.0, valid_cd_time + elapsed_ms * speed_multiplier)

    @classmethod
    def cooldown_real_elapsed_ms(cls, cooldown, now, cooldown_acceleration=0):
        speed_multiplier = max(0.0, 1.0 + cooldown_acceleration / 10000.0)
        if speed_multiplier <= 0:
            return max(0.0, now - float(cooldown.get("received_at", now))) * 1000.0
        return cls.cooldown_progress_ms(
            cooldown,
            now,
            cooldown_acceleration,
        ) / speed_multiplier

    @classmethod
    def format_cooldown(
        cls, cooldown, now, missing="Unknown", cooldown_acceleration=0
    ):
        if cooldown is None:
            return missing
        remaining_ms = cls.remaining_cooldown_ms(
            cooldown, now, cooldown_acceleration
        )
        if remaining_ms <= 0:
            return "Ready"
        return f"{remaining_ms / 1000.0:.1f}s"

    @staticmethod
    def available_charges(
        cooldown, now, max_charges, cooldown_acceleration=0
    ):
        if cooldown is None:
            return max_charges
        duration = int(cooldown.get("duration", 0))
        if duration <= 0:
            return max_charges
        progressed = DissonanceS4CombatAssistTask.cooldown_progress_ms(
            cooldown,
            now,
            cooldown_acceleration,
        )
        return min(max_charges, int(progressed // duration))
