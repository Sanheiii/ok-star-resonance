# MIDI Piano Roll Visualizer Design

## Overview

Add a full-featured MIDI piano roll visualization popup to `MidiPlayerTask`. Users can view the selected MIDI file with notes displayed on a piano roll grid, complete with playback animation, zoom/scroll, and note detail inspection.

## Architecture

### Component Hierarchy

```
MidiVisualizerDialog (MessageBoxBase)
├── PianoRollWidget (custom QWidget)
│   ├── PianoKeyboard (left side, vertical strip)
│   ├── NoteGrid (main area with time grid and notes)
│   └── Playhead (animated vertical line)
├── Toolbar (QWidget with controls)
│   ├── Play/Pause button (ToolButton)
│   ├── Stop button (ToolButton)
│   ├── Zoom controls (Slider widgets)
│   └── Time display (BodyLabel)
└── InfoPanel (collapsible CardWidget)
    └── Note details (pitch, time, duration, velocity, playable status)
```

### Key Classes

| Class | Responsibility |
|-------|---------------|
| `NoteData` | Dataclass storing parsed note info (pitch, start, duration, velocity, track) |
| `PianoRollWidget` | Custom widget for rendering and interaction (zoom, scroll, click) |
| `PlaybackController` | QTimer-driven animation, emits position updates |
| `MidiVisualizerDialog` | Main dialog, coordinates components, handles MIDI file loading |

### Data Flow

1. User clicks "Visualize" button in task config
2. `MidiVisualizerDialog` loads MIDI file via `mido`
3. Parses notes into `NoteData` objects, calculates playability
4. `PianoRollWidget` renders notes with color coding
5. User interactions update view without reparsing
6. Playback animation updates playhead via timer

## Visual Design

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  ┌──────┬─────────────────────────────────────────────────┐  │
│  │      │  Time Ruler (beats/seconds)                     │  │
│  │      ├─────────────────────────────────────────────────┤  │
│  │      │                                                 │  │
│  │      │    ████     ████████                            │  │
│  │ P    │        ████          ████    ████████           │  │
│  │ i    │  ████████        ████████████      ████████     │  │
│  │ a    │                    Playhead │                  │  │
│  │ n    │                              ▼                  │  │
│  │ o    │            ████     ████████                    │  │
│  │      │       ██████████████       ████                 │  │
│  │ K    │                                                 │  │
│  │ e    │       [unplayable notes shown in red]           │  │
│  │ y    │                                                 │  │
│  │ b    │                                                 │  │
│  │ o    │                                                 │  │
│  │ a    │                                                 │  │
│  │ r    │                                                 │  │
│  │ d    │                                                 │  │
│  └──────┴─────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│  ▶ ⏹  Zoom H: [====●====]  Zoom V: [===●=====]  0:12 / 3:45  │
└──────────────────────────────────────────────────────────────┘
```

### qfluentwidgets Components

| Element | Component |
|---------|-----------|
| Dialog container | `MessageBoxBase` |
| Play/Pause button | `ToolButton` with `FluentIcon.PLAY` / `FluentIcon.PAUSE` |
| Stop button | `ToolButton` with `FluentIcon.STOP` |
| Zoom sliders | `Slider` (horizontal) |
| Time display | `BodyLabel` |
| Scroll area | `SmoothScrollArea` |
| Note info panel | `CardWidget` with `StrongBodyLabel` + `BodyLabel` |
| Title | `SubtitleLabel` |

### Color Scheme

| Element | Color |
|---------|-------|
| Playable notes | Theme primary color (use `themeColor()`) |
| Unplayable notes | Red (#E74C3C) |
| Piano white keys | #F5F5F5 |
| Piano black keys | #2C3E50 |
| Grid lines (beats) | #E0E0E0 |
| Grid lines (measures) | #BDBDBD (thicker) |
| Playhead | #27AE60 |
| Background | #FFFFFF |

### Rendering Details

**Piano Keyboard:**
- Fixed width: ~60px
- Default view: C3-B5 (playable range)
- Scrollable to show full MIDI range
- Octave labels (C3, C4, C5) using `CaptionLabel`

**Note Grid:**
- Horizontal axis: Time (seconds, calculated from tempo map)
- Vertical axis: MIDI note numbers
- Notes: Rounded rectangles via `QPainter`
- Height per note: 12-16px (zoom-adjustable)
- Width: Duration in pixels based on zoom

**Zoom:**
- Horizontal: pixels per second (range: 10-200)
- Vertical: pixels per note (range: 8-24)
- Center preservation during zoom operations

## Error Handling

| Scenario | Handling |
|----------|----------|
| Invalid/corrupted MIDI | Error dialog, close visualizer |
| Empty MIDI (no notes) | Placeholder text "No notes to display" |
| No tempo events | Default to 120 BPM |
| Very long files (>10 min) | Limited initial zoom, allow zoom out |
| Notes outside C0-C8 | Display but start view at C3-B5 |

## Performance

| Concern | Solution |
|---------|----------|
| Many notes (>5000) | Render only visible viewport area |
| Smooth zooming | Debounce zoom redraws (50ms) |
| Playback animation | 30 FPS (33ms timer interval) |
| Memory | Parse once, store as lightweight `NoteData` objects |

## Tempo Handling

1. Parse all tempo changes during load
2. Calculate absolute time using tempo map
3. Display time ruler in seconds (toggleable to beats)
4. Show tempo change markers on time ruler

## Multi-track Display

- Display all selected tracks simultaneously
- Color-code by track (different primary color shades)
- Track names in collapsible legend panel

## Integration

### Button Configuration

Add to `MidiPlayerTask.__init__`:

```python
self.config_type['Visualization'] = {'type': "button", 'buttons': [
    {'icon': FluentIcon.MUSIC, 'text': 'Visualize', 'callback': self.open_visualizer},
]}
```

### Integration Points

| Integration | Source |
|-------------|--------|
| File selection | `self.config.get('MIDI File')` |
| Track selection | `self.config.get('_track_selections')` |
| Playable range | `self.pitch_to_key` |
| Parent window | `og.app.main_window` |

### File Location

`src/gui/MidiVisualizerDialog.py`