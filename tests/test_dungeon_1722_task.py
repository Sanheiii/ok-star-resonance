import unittest

from src.tasks.DungeonTasks.DelusionFlowingMoonWildernessTask import DelusionFlowingMoonWildernessTask


class Dungeon1722TaskTest(unittest.TestCase):
    def test_wait_for_entity_position_filters_type_and_uses_ten_seconds(self):
        class Task:
            ENTITY_WAIT_TIMEOUT = 10
            nearby_entities = {
                1: {'attr_id': 5023, 'entity_type': 1, 'position': (1, 2, 3)},
                2: {'attr_id': 5023, 'entity_type': 3, 'position': (4, 5, 6)},
            }

            def wait_until(self, condition, time_out):
                self.time_out = time_out
                return condition()

        task = Task()

        self.assertEqual(
            DelusionFlowingMoonWildernessTask._wait_for_entity_position(task, 5023, 3),
            (4, 5, 6),
        )
        self.assertEqual(task.time_out, 10)

    def test_wait_for_entity_position_returns_none_after_timeout(self):
        class Task:
            ENTITY_WAIT_TIMEOUT = 10
            nearby_entities = {}

            @staticmethod
            def wait_until(_condition, time_out):
                assert time_out == 10
                return False

        self.assertIsNone(
            DelusionFlowingMoonWildernessTask._wait_for_entity_position(Task(), 1955, 1)
        )

    def test_master_route_interacts_with_5020_before_retrying(self):
        class Task:
            COMBAT_ROUNDS = DelusionFlowingMoonWildernessTask.COMBAT_ROUNDS
            BOSS_ENTRANCE_ATTR_ID = DelusionFlowingMoonWildernessTask.BOSS_ENTRANCE_ATTR_ID
            MASTER_INTERACTION_ATTR_ID = DelusionFlowingMoonWildernessTask.MASTER_INTERACTION_ATTR_ID
            ENTITY_WAIT_TIMEOUT = DelusionFlowingMoonWildernessTask.ENTITY_WAIT_TIMEOUT
            _find_nearby_entity_position = staticmethod(
                DelusionFlowingMoonWildernessTask._find_nearby_entity_position
            )
            _find_combat_round = DelusionFlowingMoonWildernessTask._find_combat_round
            _wait_for_entity_position = DelusionFlowingMoonWildernessTask._wait_for_entity_position

            def __init__(self):
                self.entities = {}
                self.info = {}
                self.interactions = []
                self.sleeps = []
                self.events = []

            @property
            def nearby_entities(self):
                return self.entities

            def _use_scene_object(self, attr_id, _state):
                self.events.append('use')
                self.interactions.append(attr_id)
                self.entities = {
                    1: {
                        'attr_id': self.BOSS_ENTRANCE_ATTR_ID,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                }
                return True

            def _find_combat_round(self):
                self.events.append('find')
                return None

            def wait_until(self, condition, time_out):
                self.events.append('wait')
                self.entities = {
                    1: {
                        'attr_id': self.MASTER_INTERACTION_ATTR_ID,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                }
                return condition()

            def sleep(self, seconds):
                self.events.append('sleep')
                self.sleeps.append(seconds)

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._run_master_route(task))
        self.assertEqual(task.interactions, [5020])
        self.assertEqual(task.sleeps, [1, 3])
        self.assertEqual(task.events, ['wait', 'sleep', 'find', 'use', 'sleep'])

    def test_master_route_clears_a_nearby_combat_round_first(self):
        class Task:
            COMBAT_ROUNDS = DelusionFlowingMoonWildernessTask.COMBAT_ROUNDS
            BOSS_ENTRANCE_ATTR_ID = DelusionFlowingMoonWildernessTask.BOSS_ENTRANCE_ATTR_ID
            MASTER_INTERACTION_ATTR_ID = DelusionFlowingMoonWildernessTask.MASTER_INTERACTION_ATTR_ID
            ENTITY_WAIT_TIMEOUT = DelusionFlowingMoonWildernessTask.ENTITY_WAIT_TIMEOUT
            _find_nearby_entity_position = staticmethod(
                DelusionFlowingMoonWildernessTask._find_nearby_entity_position
            )
            _find_combat_round = DelusionFlowingMoonWildernessTask._find_combat_round
            _wait_for_entity_position = DelusionFlowingMoonWildernessTask._wait_for_entity_position

            def __init__(self):
                self.entities = {
                    1: {
                        'attr_id': self.MASTER_INTERACTION_ATTR_ID,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                    2: {
                        'attr_id': 5024,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                }
                self.position = (0, 0, 0)
                self.info = {}
                self.cleared_rounds = []
                self.interactions = []

            @property
            def nearby_entities(self):
                return self.entities

            def move_to_position(self, *_args, **_kwargs):
                return True

            def sleep(self, _seconds):
                pass

            @staticmethod
            def wait_until(condition, time_out):
                return condition()

            def _clear_round(self, scene_object_attr_id, monster_attr_id):
                self.cleared_rounds.append((scene_object_attr_id, monster_attr_id))
                self.entities = {
                    1: {
                        'attr_id': self.BOSS_ENTRANCE_ATTR_ID,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                }
                return True

            def _use_scene_object(self, attr_id, _state):
                self.interactions.append(attr_id)
                return True

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._run_master_route(task))
        self.assertEqual(task.cleared_rounds, [(5024, 1956)])
        self.assertEqual(task.interactions, [])

    def test_master_route_continues_after_special_route(self):
        class Task:
            BOSS_ENTRANCE_ATTR_ID = 5028
            MASTER_INTERACTION_ATTR_ID = 5020
            _find_nearby_entity_position = staticmethod(
                DelusionFlowingMoonWildernessTask._find_nearby_entity_position
            )

            def __init__(self):
                self.entities = {}
                self.wait_calls = 0
                self.special_calls = 0

            @property
            def nearby_entities(self):
                return self.entities

            def _wait_for_entity_position(self, attr_id, entity_type):
                self.wait_calls += 1
                self.entities = {
                    1: {
                        'attr_id': self.BOSS_ENTRANCE_ATTR_ID,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                }
                return None

            def _run_master_special_route(self):
                self.special_calls += 1
                return True

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._run_master_route(task))
        self.assertEqual(task.special_calls, 1)
        self.assertEqual(task.wait_calls, 1)

    def test_master_fallback_enters_npc_waits_and_waits_for_exit(self):
        class Task:
            MASTER_FALLBACK_ENTRY_ATTR_IDS = (5022, 5021)
            MASTER_5022_NPC_ATTR_ID = 140155
            MASTER_5021_NPC_ATTR_ID = 140154
            MASTER_FALLBACK_WAIT_TIME = 60
            BOSS_ENTRANCE_ATTR_ID = 5028
            EXIT_SCENE_OBJECT_ATTR_ID = 5029
            _run_master_5022_route = (
                DelusionFlowingMoonWildernessTask._run_master_5022_route
            )
            _run_master_5021_route = (
                DelusionFlowingMoonWildernessTask._run_master_5021_route
            )

            def __init__(self):
                self.calls = []
                self.info = {}
                self._master_boss_entrance_found = False

            def _wait_for_any_entity_position(self, attr_ids, entity_type):
                self.calls.append(('wait_any', tuple(attr_ids), entity_type))
                return 5022, (1, 2, 3)

            def _use_scene_object(self, attr_id, state):
                self.calls.append(('use_scene_object', attr_id, state))
                return True

            def _use_master_exit(self):
                self.calls.append(('use_scene_object', 5029, '前往出口'))
                return True

            def _wait_for_entity_position(self, attr_id, entity_type):
                self.calls.append(('wait_entity', attr_id, entity_type))
                return (4, 5, 6)

            def _move_to_entity(self, position, state):
                self.calls.append(('move', position, state))
                return True

            def send_key(self, key, **kwargs):
                self.calls.append(('send_key', key, kwargs))

            def sleep(self, seconds):
                self.calls.append(('sleep', seconds))

            def log_error(self, message):
                self.calls.append(('error', message))

        task = Task()

        self.assertTrue(
            DelusionFlowingMoonWildernessTask._run_master_special_route(task)
        )
        self.assertEqual(task.calls, [
            ('wait_any', (5022, 5021), 3),
            ('use_scene_object', 5022, '进入云朵金娜'),
            ('wait_entity', 140155, 2),
            ('move', (4, 5, 6), '前往NPC 140155'),
            ('send_key', 'f', {'after_sleep': 1}),
            ('send_key', 'w', {'down_time': 0.5, 'after_sleep': 1}),
            ('send_key', 'f', {'after_sleep': 1}),
            ('sleep', 60),
            ('use_scene_object', 5029, '前往出口'),
        ])

    def test_master_5021_route_uses_npc_140154_in_separate_branch(self):
        class Task:
            MASTER_5021_NPC_ATTR_ID = 140154
            MASTER_5021_POSITION = (-13.169, -218.602)
            MASTER_5021_LOOP_TIMEOUT = 90
            BOSS_ENTRANCE_ATTR_ID = 5028
            EXIT_SCENE_OBJECT_ATTR_ID = 5029
            _find_master_event_exit = (
                DelusionFlowingMoonWildernessTask._find_master_event_exit
            )

            def __init__(self):
                self.calls = []
                self.info = {}
                self._master_boss_entrance_found = False
                self.position = (0, 0, 0)
                self.entities = {}
                self.is_dead = False

            def _use_scene_object(self, attr_id, state):
                self.calls.append(('use_scene_object', attr_id, state))
                return True

            @property
            def nearby_entities(self):
                return self.entities

            def _wait_for_entity_position(self, attr_id, entity_type):
                self.calls.append(('wait_entity', attr_id, entity_type))
                return (4, 5, 6)

            def _move_to_entity(self, position, state):
                self.calls.append(('move', position, state))
                return True

            def move_to_position(self, start, target, **_kwargs):
                self.calls.append(('move_to_position', start, target))
                return True

            def send_key(self, key, **kwargs):
                self.calls.append(('send_key', key, kwargs))
                if key in ('~', '`'):
                    self.entities = {
                        1: {
                            'attr_id': self.EXIT_SCENE_OBJECT_ATTR_ID,
                            'entity_type': 3,
                            'position': (1, 2, 3),
                        },
                    }

            def sleep(self, seconds):
                self.calls.append(('sleep', seconds))

            def handle_death(self):
                self.calls.append(('handle_death',))

            def log_error(self, message):
                self.calls.append(('error', message))

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._run_master_5021_route(task))
        self.assertEqual(task.calls[:2], [
            ('use_scene_object', 5021, '进入花朵金娜'),
            ('wait_entity', 140154, 2),
        ])
        self.assertEqual(
            [call[1] for call in task.calls if call[0] == 'send_key'],
            ['f', 'w', 'f', 'space', 'q', 'space', '`'],
        )
        self.assertIn(
            ('move_to_position', (0, 0, 0), (-13.169, -218.602)),
            task.calls,
        )

    def test_master_target_gate_finder_includes_green_and_silver_gates(self):
        entities = {
            1: {'attr_id': 5039, 'entity_type': 3, 'position': (1, 2, 3)},
            2: {'attr_id': 5026, 'entity_type': 3, 'position': (4, 5, 6)},
            3: {'attr_id': 5038, 'entity_type': 2, 'position': (7, 8, 9)},
        }

        self.assertEqual(
            DelusionFlowingMoonWildernessTask._find_master_target_gate(entities),
            5039,
        )

    def test_master_exit_prefers_5028_without_interacting_with_5029(self):
        class Task:
            BOSS_ENTRANCE_ATTR_ID = 5028
            EXIT_SCENE_OBJECT_ATTR_ID = 5029
            ENTITY_WAIT_TIMEOUT = 10
            _find_master_event_exit = (
                DelusionFlowingMoonWildernessTask._find_master_event_exit
            )
            _wait_for_master_event_exit = (
                DelusionFlowingMoonWildernessTask._wait_for_master_event_exit
            )

            def __init__(self):
                self.entities = {
                    1: {
                        'attr_id': self.BOSS_ENTRANCE_ATTR_ID,
                        'entity_type': 3,
                        'position': (1, 2, 3),
                    },
                    2: {
                        'attr_id': self.EXIT_SCENE_OBJECT_ATTR_ID,
                        'entity_type': 3,
                        'position': (4, 5, 6),
                    },
                }
                self.calls = []
                self._master_boss_entrance_found = False

            @property
            def nearby_entities(self):
                return self.entities

            def wait_until(self, condition, time_out):
                self.calls.append(('wait_until', time_out))
                return condition()

            def _move_to_entity(self, position, state):
                self.calls.append(('move', position, state))
                return True

            def send_key(self, key, **kwargs):
                self.calls.append(('send_key', key, kwargs))

            def log_error(self, message):
                self.calls.append(('error', message))

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._use_master_exit(task))
        self.assertTrue(task._master_boss_entrance_found)
        self.assertEqual(task.calls, [('wait_until', 10)])

    def test_master_green_route_waits_then_fights_at_configured_position(self):
        class Task:
            MASTER_GREEN_GATES = DelusionFlowingMoonWildernessTask.MASTER_GREEN_GATES

            def __init__(self):
                self.calls = []
                self.info = {}
                self.position = (0, 0, 0)

            def _use_scene_object(self, attr_id, state):
                self.calls.append(('use_scene_object', attr_id, state))
                return True

            def sleep(self, seconds):
                self.calls.append(('sleep', seconds))

            def move_to_position(self, start, target, **kwargs):
                self.calls.append(('move_to_position', start, target, kwargs))
                return True

            @staticmethod
            def get_custom_key(action):
                return action

            def send_key(self, key, **kwargs):
                self.calls.append(('send_key', key, kwargs))

            def wait_in_combat(self):
                self.calls.append(('wait_in_combat',))
                return True

            def wait_out_of_combat(self, time_out):
                self.calls.append(('wait_out_of_combat', time_out))
                return True

        task = Task()

        self.assertTrue(
            DelusionFlowingMoonWildernessTask._run_master_green_route(
                task,
                5039,
                (-256.953, -382.241),
            )
        )
        self.assertIn(('sleep', 3), task.calls)
        self.assertIn(
            ('move_to_position',
             (0, 0, 0),
             (-256.953, -382.241),
             {'enable_sprint': True}),
            task.calls,
        )
        self.assertEqual(
            [call for call in task.calls if call[0] == 'send_key'],
            [
                ('send_key', 'Auto Battle', {}),
                ('send_key', 'Auto Battle', {}),
            ],
        )

    def test_master_5026_route_activates_all_5040_targets_before_combat(self):
        class Task:
            MASTER_5026_NPC_ATTR_ID = 140156
            MASTER_5040_ATTR_ID = 5040
            MASTER_5026_WAIT_TIME = 5
            ENTITY_WAIT_TIMEOUT = 10
            _interact_master_npc = (
                DelusionFlowingMoonWildernessTask._interact_master_npc
            )
            _wait_for_entities = DelusionFlowingMoonWildernessTask._wait_for_entities

            def __init__(self):
                self.entities = {
                    1: {'attr_id': 140156, 'entity_type': 2, 'position': (1, 2, 3)},
                    2: {'attr_id': 5040, 'entity_type': 3, 'position': (10, 0, 10)},
                    3: {'attr_id': 5040, 'entity_type': 3, 'position': (1, 0, 1)},
                }
                self.calls = []
                self.info = {}
                self.position = (0, 0, 0)

            @property
            def nearby_entities(self):
                return self.entities

            def _use_scene_object(self, attr_id, state):
                self.calls.append(('use_scene_object', attr_id, state))
                return True

            def _wait_for_entity_position(self, attr_id, entity_type):
                self.calls.append(('wait_entity', attr_id, entity_type))
                return self.entities[1]['position']

            def _move_to_entity(self, position, state):
                self.calls.append(('move', position, state))
                return True

            def wait_until(self, condition, time_out):
                self.calls.append(('wait_until', time_out))
                return condition()

            def sleep(self, seconds):
                self.calls.append(('sleep', seconds))

            @staticmethod
            def get_custom_key(action):
                return action

            def send_key(self, key, **kwargs):
                self.calls.append(('send_key', key, kwargs))

            def wait_in_combat(self):
                self.calls.append(('wait_in_combat',))
                return True

            def wait_out_of_combat(self, time_out):
                self.calls.append(('wait_out_of_combat', time_out))
                return True

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._run_master_5026_route(task))
        self.assertEqual(
            [call[1] for call in task.calls if call[0] == 'move'],
            [(1, 2, 3), (1, 0, 1), (10, 0, 10)],
        )
        self.assertEqual(
            [call[1] for call in task.calls if call[0] == 'send_key'],
            ['f', 'w', 'f', '`', '`', 'Auto Battle', 'Auto Battle'],
        )
        self.assertEqual(
            [call[1] for call in task.calls if call[0] == 'sleep'],
            [5, 2, 2],
        )

    def test_master_5027_route_stops_when_exit_appears(self):
        class Task:
            MASTER_5027_NPC_ATTR_ID = 140157
            BOSS_ENTRANCE_ATTR_ID = 5028
            EXIT_SCENE_OBJECT_ATTR_ID = 5029
            _interact_master_npc = (
                DelusionFlowingMoonWildernessTask._interact_master_npc
            )
            _find_master_event_exit = (
                DelusionFlowingMoonWildernessTask._find_master_event_exit
            )

            def __init__(self):
                self.entities = {
                    1: {'attr_id': 140157, 'entity_type': 2, 'position': (1, 2, 3)},
                }
                self.calls = []
                self.info = {}
                self._master_boss_entrance_found = False

            @property
            def nearby_entities(self):
                return self.entities

            def _use_scene_object(self, attr_id, state):
                self.calls.append(('use_scene_object', attr_id, state))
                return True

            def _wait_for_entity_position(self, attr_id, entity_type):
                self.calls.append(('wait_entity', attr_id, entity_type))
                return (1, 2, 3)

            def _move_to_entity(self, position, state):
                self.calls.append(('move', position, state))
                return True

            def send_key(self, key, **kwargs):
                self.calls.append(('send_key', key, kwargs))
                if key == '`':
                    self.entities[2] = {
                        'attr_id': self.EXIT_SCENE_OBJECT_ATTR_ID,
                        'entity_type': 3,
                        'position': (4, 5, 6),
                    }

        task = Task()

        self.assertTrue(DelusionFlowingMoonWildernessTask._run_master_5027_route(task))
        self.assertEqual(
            [call[1] for call in task.calls if call[0] == 'send_key'],
            ['f', 'w', 'f', '`'],
        )


if __name__ == '__main__':
    unittest.main()
