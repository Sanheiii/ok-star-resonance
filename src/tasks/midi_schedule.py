from itertools import groupby


def switch_cost(current, target):
    page, octave = current
    target_page, target_octave = target
    if page == target_page:
        return int(octave != target_octave)
    return abs(page - target_page) + int(octave != 0) + int(target_octave != 0)


def plan_midi_events(events, is_in_range):
    """Group simultaneous attacks by range; retain note identities and timestamps."""
    current = (1, 0)
    states = [(page, octave) for page in range(3) for octave in (-1, 0, 1)]
    planned = []
    for timestamp, group in groupby(events, key=lambda event: event[0]):
        messages = [msg for _, msg in group]
        attacks = []
        for msg in messages:
            if msg.type == 'note_on' and msg.velocity > 0:
                attacks.append(msg)
            else:
                # Release ending notes before new attacks at the same timestamp.
                planned.append((timestamp, msg, None))
        while attacks:
            playable = {state: [msg for msg in attacks if is_in_range(msg.note, *state)]
                        for state in states}
            target = max(states, key=lambda state: (
                len(playable[state]), -switch_cost(current, state)))
            selected = playable[target]
            if not selected:
                planned.extend((timestamp, msg, None) for msg in attacks)
                break
            for msg in selected:
                planned.append((timestamp, msg, target))
            selected_ids = {id(msg) for msg in selected}
            attacks = [msg for msg in attacks if id(msg) not in selected_ids]
            current = target
    return planned
