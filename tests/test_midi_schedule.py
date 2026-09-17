import unittest
from types import SimpleNamespace

from src.tasks.midi_schedule import plan_midi_events, switch_cost


def in_range(note, page, octave):
    return 21 <= note <= 108 and 48 <= note - (page - 1) * 36 - octave * 12 <= 83


def attack(note):
    return SimpleNamespace(type='note_on', note=note, velocity=100)


class TestMidiSchedule(unittest.TestCase):
    def test_chord_uses_one_range_when_possible(self):
        messages = [attack(n) for n in (64, 69, 71, 45)]
        result = plan_midi_events([(12, msg) for msg in messages], in_range)
        self.assertEqual(len(result), 4)
        self.assertEqual(len({state for _, _, state in result}), 1)
        for _, msg, state in result:
            self.assertTrue(in_range(msg.note, *state))

    def test_wide_chord_groups_notes_without_losing_attacks(self):
        messages = [attack(n) for n in (64, 33, 45)]
        result = plan_midi_events([(11.4375, msg) for msg in messages], in_range)
        self.assertEqual({id(msg) for _, msg, _ in result}, {id(msg) for msg in messages})
        self.assertEqual(len({state for _, _, state in result}), 2)
        for _, msg, state in result:
            self.assertTrue(in_range(msg.note, *state))

    def test_stays_in_current_range(self):
        result = plan_midi_events([(0, attack(60)), (1, attack(64))], in_range)
        self.assertEqual([state for _, _, state in result], [(1, 0), (1, 0)])

    def test_endings_precede_attacks_and_unplayable_is_retained(self):
        off = SimpleNamespace(type='note_on', note=60, velocity=0)
        result = plan_midi_events([(0, attack(60)), (0, off), (1, attack(120))], in_range)
        self.assertIs(result[0][1], off)
        self.assertIsNone(result[-1][2])

    def test_cost_accounts_for_neutralizing_octave(self):
        self.assertEqual(switch_cost((1, -1), (0, 1)), 3)


if __name__ == '__main__':
    unittest.main()

