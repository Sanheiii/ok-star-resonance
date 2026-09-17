import unittest

from src.tasks.midi_key_state import MidiKeyState


class TestMidiKeyState(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.state = MidiKeyState(
            lambda key: self.events.append(('down', key)),
            lambda key: self.events.append(('up', key)),
            lambda seconds: self.events.append(('wait', seconds)),
            min_hold=0,
        )

    def test_beethoven_a4_a3_collision(self):
        self.state.note_on(0, 69, 'h')  # A4 at 12.0000 s
        self.state.note_on(0, 57, 'h')  # A3 at 12.1875 s
        self.assertEqual(self.events, [
            ('down', 'h'), ('up', 'h'), ('wait', 0.033), ('down', 'h'),
        ])
        self.state.note_off(0, 69)
        self.assertEqual(len(self.events), 4)
        self.state.note_off(0, 57)
        self.assertEqual(self.events[-1], ('up', 'h'))
        self.assertFalse(self.state.owners)

    def test_old_off_after_new_note_ends(self):
        self.state.note_on(0, 69, 'h')
        self.state.note_on(0, 57, 'h')
        self.state.note_off(0, 57)
        self.state.note_on(0, 45, 'h')
        count = len(self.events)
        self.state.note_off(0, 69)
        self.assertEqual(len(self.events), count)
        self.state.note_off(0, 45)
        self.assertEqual(self.events[-1], ('up', 'h'))

    def test_overlapping_same_pitch_uses_fifo_instances(self):
        self.state.note_on(0, 60, 'a')
        self.state.note_on(0, 60, 'a')
        count = len(self.events)
        self.state.note_off(0, 60)
        self.assertEqual(len(self.events), count)
        self.state.note_off(0, 60)
        self.assertEqual(self.events[-1], ('up', 'a'))

    def test_channels_do_not_release_each_others_notes(self):
        self.state.note_on(0, 60, 'a')
        self.state.note_on(1, 60, 'q')
        self.state.note_off(0, 60)
        self.assertEqual(set(self.state.owners), {'q'})

    def test_pause_retains_old_note_identity(self):
        self.state.note_on(0, 60, 'a')
        self.state.release_all()
        self.state.note_on(0, 60, 'a')
        count = len(self.events)
        self.state.note_off(0, 60)
        self.assertEqual(len(self.events), count)
        self.state.note_off(0, 60)
        self.assertFalse(self.state.owners)

    def test_interrupted_retrigger_leaves_no_key_down(self):
        self.state.note_on(0, 69, 'h')
        def interrupt(seconds):
            raise RuntimeError('stopped')
        self.state.sleep = interrupt
        with self.assertRaises(RuntimeError):
            self.state.note_on(0, 57, 'h')
        self.state.release_all()
        self.assertFalse(self.state.owners)
        self.assertEqual(self.events[-1], ('up', 'h'))

    def test_cleanup_attempts_every_key_after_failure(self):
        self.state.note_on(0, 60, 'a')
        self.state.note_on(0, 64, 'd')
        def release(key):
            self.events.append(('up', key))
            if key == 'a':
                raise RuntimeError('release failed')
        self.state.key_up = release
        with self.assertRaises(RuntimeError):
            self.state.release_all()
        self.assertEqual(self.events[-2:], [('up', 'a'), ('up', 'd')])

    def test_overdue_note_off_preserves_minimum_hold(self):
        now = [0.0]
        def wait(seconds):
            now[0] += seconds
        state = MidiKeyState(lambda key: None, lambda key: None, wait,
                             clock=lambda: now[0])
        state.note_on(0, 45, 'n')
        state.note_off(0, 45)
        self.assertAlmostEqual(now[0], 0.04)
        state.note_on(0, 45, 'n')
        now[0] += 0.2
        state.note_off(0, 45)
        self.assertAlmostEqual(now[0], 0.24)

    def test_stop_does_not_wait_for_minimum_hold(self):
        state = MidiKeyState(lambda key: None, lambda key: None,
                             lambda seconds: self.fail('cleanup must not wait'),
                             clock=lambda: 0)
        state.note_on(0, 45, 'n')
        state.release_all()
        self.assertFalse(state.owners)


if __name__ == '__main__':
    unittest.main()
