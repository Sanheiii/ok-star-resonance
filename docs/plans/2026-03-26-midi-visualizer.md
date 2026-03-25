# MIDI Piano Roll Visualizer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a full-featured MIDI piano roll visualization popup with playback animation, zoom/scroll, and note detail inspection.

**Architecture:** Custom QWidget with QPainter for rendering, integrated into MidiPlayerTask via a new button. Uses existing qfluentwidgets components for UI consistency.

**Tech Stack:** PySide6, qfluentwidgets, mido (already in dependencies)

---

## Task 1: Create Directory Structure and Data Classes

**Files:**
- Create: `src/gui/__init__.py`
- Create: `src/gui/MidiVisualizerDialog.py`

**Step 1: Create gui package directory**

```bash
mkdir -p src/gui
```

**Step 2: Create __init__.py**

Create `src/gui/__init__.py`:
```python
# GUI components for ok-star-resonance
```

**Step 3: Add data classes to MidiVisualizerDialog.py**

Add to `src/gui/MidiVisualizerDialog.py`:
```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class NoteData:
    """Stores parsed MIDI note information."""
    pitch: int  # MIDI note number (0-127)
    start_time: float  # Start time in seconds
    duration: float  # Duration in seconds
    velocity: int  # Note velocity (0-127)
    track_index: int  # Which track this note belongs to
    is_playable: bool  # Whether this note is in playable range (C3-B5)


@dataclass
class TempoEvent:
    """Stores tempo change information."""
    time: float  # Time in seconds when tempo changes
    bpm: float  # Tempo in beats per minute
```

**Step 4: Commit**

```bash
git add src/gui/__init__.py src/gui/MidiVisualizerDialog.py
git commit -m "feat: add gui package and MIDI visualizer data classes"
```

---

## Task 2: Create MIDI Parser Helper

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add imports for MIDI parsing**

Add to imports in `src/gui/MidiVisualizerDialog.py`:
```python
import mido
from mido import MidiFile, bpm2tempo
from typing import List, Dict, Set, Tuple
```

**Step 2: Add MidiParser class**

Add after data classes in `src/gui/MidiVisualizerDialog.py`:
```python
class MidiParser:
    """Parses MIDI files into NoteData objects."""

    # Playable range for the game (C3=48 to B5=83)
    PLAYABLE_MIN = 48
    PLAYABLE_MAX = 83

    def __init__(self, playable_range: Tuple[int, int] = None):
        self.playable_min = playable_range[0] if playable_range else self.PLAYABLE_MIN
        self.playable_max = playable_range[1] if playable_range else self.PLAYABLE_MAX

    def is_playable(self, pitch: int) -> bool:
        """Check if a note is within playable range."""
        return self.playable_min <= pitch <= self.playable_max

    def parse(self, midi_file: MidiFile, selected_tracks: Set[int] = None) -> Tuple[List[NoteData], List[TempoEvent], float]:
        """
        Parse MIDI file into notes and tempo events.

        Returns:
            Tuple of (notes list, tempo events list, total duration in seconds)
        """
        notes = []
        tempo_events = []

        # Build tempo map
        tempo_map = self._build_tempo_map(midi_file, tempo_events)

        # Parse notes from all tracks
        for track_idx, track in enumerate(midi_file.tracks):
            # Skip unselected tracks if selection is specified
            if selected_tracks is not None and track_idx not in selected_tracks:
                continue

            self._parse_track(track, track_idx, midi_file.ticks_per_beat, tempo_map, notes)

        # Sort notes by start time
        notes.sort(key=lambda n: n.start_time)

        # Calculate total duration
        total_duration = max((n.start_time + n.duration for n in notes), default=0.0)

        return notes, tempo_events, total_duration

    def _build_tempo_map(self, midi_file: MidiFile, tempo_events: List[TempoEvent]) -> List[Tuple[int, int]]:
        """Build a list of (tick, tempo) pairs from all tracks."""
        tempo_map = []
        default_tempo = bpm2tempo(120)  # Default 120 BPM

        for track in midi_file.tracks:
            abs_tick = 0
            for msg in track:
                abs_tick += msg.time
                if msg.type == 'set_tempo':
                    tempo_map.append((abs_tick, msg.tempo))
                    bpm = mido.tempo2bpm(msg.tempo)
                    # Calculate time later, for now store tick
                    tempo_events.append(TempoEvent(time=0.0, bpm=bpm))

        # Sort by tick
        tempo_map.sort(key=lambda x: x[0])

        # If no tempo events, add default
        if not tempo_map:
            tempo_map = [(0, default_tempo)]

        return tempo_map

    def _parse_track(self, track, track_idx: int, ticks_per_beat: int,
                     tempo_map: List[Tuple[int, int]], notes: List[NoteData]):
        """Parse a single track into notes."""
        abs_tick = 0
        active_notes: Dict[int, Tuple[int, float]] = {}  # pitch -> (start_tick, velocity)

        for msg in track:
            abs_tick += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                # Note start
                start_time = self._tick_to_time(abs_tick, ticks_per_beat, tempo_map)
                active_notes[msg.note] = (abs_tick, msg.velocity, start_time)

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                # Note end
                if msg.note in active_notes:
                    start_tick, velocity, start_time = active_notes[msg.note]
                    end_time = self._tick_to_time(abs_tick, ticks_per_beat, tempo_map)
                    duration = end_time - start_time

                    if duration > 0:
                        notes.append(NoteData(
                            pitch=msg.note,
                            start_time=start_time,
                            duration=duration,
                            velocity=velocity,
                            track_index=track_idx,
                            is_playable=self.is_playable(msg.note)
                        ))
                    del active_notes[msg.note]

    def _tick_to_time(self, tick: int, ticks_per_beat: int, tempo_map: List[Tuple[int, int]]) -> float:
        """Convert MIDI tick to time in seconds using tempo map."""
        if not tempo_map:
            return tick / ticks_per_beat  # Fallback, assume 1 beat = 1 second

        time = 0.0
        last_tick = 0
        last_tempo = tempo_map[0][1]

        for map_tick, tempo in tempo_map:
            if map_tick >= tick:
                break
            # Add time from last segment
            time += (map_tick - last_tick) / ticks_per_beat * last_tempo / 1_000_000
            last_tick = map_tick
            last_tempo = tempo

        # Add time for remaining segment
        time += (tick - last_tick) / ticks_per_beat * last_tempo / 1_000_000

        return time
```

**Step 3: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: add MidiParser for converting MIDI to NoteData"
```

---

## Task 3: Create PianoRollWidget with Basic Structure

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add PySide6 imports**

Add to imports:
```python
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
```

**Step 2: Add PianoRollWidget class**

Add after MidiParser class:
```python
class PianoRollWidget(QWidget):
    """Custom widget for rendering piano roll visualization."""

    # Signals
    note_clicked = Signal(object)  # Emits NoteData when a note is clicked
    position_changed = Signal(float)  # Emits current time in seconds

    # Piano roll dimensions
    KEYBOARD_WIDTH = 60
    TIME_RULER_HEIGHT = 24
    NOTE_HEIGHT = 14  # Base height per note row

    # Zoom ranges
    H_ZOOM_MIN = 10  # Min pixels per second
    H_ZOOM_MAX = 200  # Max pixels per second
    V_ZOOM_MIN = 8  # Min pixels per note
    V_ZOOM_MAX = 24  # Max pixels per note

    # Note range to display
    MIN_PITCH = 0  # C0
    MAX_PITCH = 127  # G10

    # Colors
    COLOR_WHITE_KEY = QColor(245, 245, 245)
    COLOR_BLACK_KEY = QColor(44, 62, 80)
    COLOR_GRID_BEAT = QColor(224, 224, 224)
    COLOR_GRID_MEASURE = QColor(189, 189, 189)
    COLOR_PLAYHEAD = QColor(39, 174, 96)
    COLOR_PLAYABLE = None  # Set from theme
    COLOR_UNPLAYABLE = QColor(231, 76, 60)
    COLOR_BACKGROUND = QColor(255, 255, 255)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes: List[NoteData] = []
        self.tempo_events: List[TempoEvent] = []
        self.total_duration = 0.0
        self.selected_tracks: Set[int] = set()

        # Zoom state
        self.h_zoom = 50  # pixels per second
        self.v_zoom = 14  # pixels per note

        # Scroll state
        self.scroll_x = 0  # horizontal scroll offset in pixels
        self.scroll_y = 0  # vertical scroll offset in pixels

        # Playback state
        self.playhead_position = 0.0  # current time in seconds
        self.is_playing = False
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(33)  # ~30 FPS
        self.playback_timer.timeout.connect(self._on_playback_tick)
        self.playback_start_time = 0.0

        # Interaction state
        self.selected_note: Optional[NoteData] = None
        self.setMouseTracking(True)

        # Widget setup
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        # Enable scrollbars via mouse wheel
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def set_notes(self, notes: List[NoteData], tempo_events: List[TempoEvent], duration: float, selected_tracks: Set[int] = None):
        """Set the notes to display."""
        self.notes = notes
        self.tempo_events = tempo_events
        self.total_duration = duration
        self.selected_tracks = selected_tracks or set()
        self._update_scroll_range()
        self.update()

    def set_playable_color(self, color: QColor):
        """Set the color for playable notes."""
        self.COLOR_PLAYABLE = color
```

**Step 3: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: add PianoRollWidget class structure"
```

---

## Task 4: Implement Piano Keyboard Rendering

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add helper methods for piano keyboard**

Add to PianoRollWidget class:
```python
    def _is_black_key(self, pitch: int) -> bool:
        """Check if a pitch is a black key."""
        note_in_octave = pitch % 12
        return note_in_octave in {1, 3, 6, 8, 10}  # C#, D#, F#, G#, A#

    def _pitch_to_name(self, pitch: int) -> str:
        """Convert MIDI pitch to note name."""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (pitch // 12) - 1
        return f"{note_names[pitch % 12]}{octave}"

    def _pitch_to_y(self, pitch: int) -> float:
        """Convert pitch to y coordinate (top of the note row)."""
        # Higher pitches are at top, so invert
        pitch_range = self.MAX_PITCH - self.MIN_PITCH + 1
        return (self.MAX_PITCH - pitch) * self.v_zoom - self.scroll_y + self.TIME_RULER_HEIGHT

    def _y_to_pitch(self, y: float) -> int:
        """Convert y coordinate to pitch."""
        pitch_range = self.MAX_PITCH - self.MIN_PITCH + 1
        pitch = self.MAX_PITCH - int((y - self.TIME_RULER_HEIGHT + self.scroll_y) / self.v_zoom)
        return max(self.MIN_PITCH, min(self.MAX_PITCH, pitch))
```

**Step 2: Add keyboard rendering method**

```python
    def _draw_keyboard(self, painter: QPainter):
        """Draw the piano keyboard on the left side."""
        keyboard_rect = self.KEYBOARD_WIDTH
        visible_top = self.scroll_y
        visible_bottom = self.scroll_y + self.height() - self.TIME_RULER_HEIGHT

        # Draw white keys first
        for pitch in range(self.MIN_PITCH, self.MAX_PITCH + 1):
            y = self._pitch_to_y(pitch)
            if y < self.TIME_RULER_HEIGHT or y > self.height():
                continue

            if not self._is_black_key(pitch):
                rect_y = y
                painter.setPen(QPen(self.COLOR_GRID_BEAT, 1))
                painter.setBrush(QBrush(self.COLOR_WHITE_KEY))
                painter.drawRect(0, int(rect_y), keyboard_rect, int(self.v_zoom))

        # Draw black keys on top
        for pitch in range(self.MIN_PITCH, self.MAX_PITCH + 1):
            y = self._pitch_to_y(pitch)
            if y < self.TIME_RULER_HEIGHT or y > self.height():
                continue

            if self._is_black_key(pitch):
                rect_y = y
                painter.setPen(QPen(self.COLOR_BLACK_KEY, 1))
                painter.setBrush(QBrush(self.COLOR_BLACK_KEY))
                # Black keys are smaller
                painter.drawRect(0, int(rect_y), int(keyboard_rect * 0.6), int(self.v_zoom))

        # Draw octave labels
        painter.setPen(QPen(QColor(100, 100, 100)))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        for pitch in range(self.MIN_PITCH, self.MAX_PITCH + 1):
            if pitch % 12 == 0:  # C notes
                y = self._pitch_to_y(pitch)
                if self.TIME_RULER_HEIGHT <= y <= self.height():
                    painter.drawText(5, int(y + self.v_zoom - 2), self._pitch_to_name(pitch))
```

**Step 3: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: implement piano keyboard rendering"
```

---

## Task 5: Implement Note Grid and Time Ruler Rendering

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add time conversion helpers**

Add to PianoRollWidget class:
```python
    def _time_to_x(self, time: float) -> float:
        """Convert time in seconds to x coordinate."""
        return time * self.h_zoom - self.scroll_x + self.KEYBOARD_WIDTH

    def _x_to_time(self, x: float) -> float:
        """Convert x coordinate to time in seconds."""
        return (x - self.KEYBOARD_WIDTH + self.scroll_x) / self.h_zoom
```

**Step 2: Add grid and time ruler rendering**

```python
    def _draw_grid(self, painter: QPainter):
        """Draw the time grid."""
        # Calculate visible time range
        start_time = self._x_to_time(self.KEYBOARD_WIDTH)
        end_time = self._x_to_time(self.width())

        # Assume 4/4 time, 120 BPM default
        beat_duration = 0.5  # seconds per beat at 120 BPM
        measure_duration = beat_duration * 4

        # Draw measure lines (thicker)
        measure = 0
        time = 0
        while time < end_time:
            x = self._time_to_x(time)
            if x >= self.KEYBOARD_WIDTH:
                painter.setPen(QPen(self.COLOR_GRID_MEASURE, 2))
                painter.drawLine(int(x), self.TIME_RULER_HEIGHT, int(x), self.height())
            time += measure_duration
            measure += 1

        # Draw beat lines (thinner)
        beat = 0
        time = 0
        while time < end_time:
            if beat % 4 != 0:  # Skip measure lines
                x = self._time_to_x(time)
                if x >= self.KEYBOARD_WIDTH:
                    painter.setPen(QPen(self.COLOR_GRID_BEAT, 1))
                    painter.drawLine(int(x), self.TIME_RULER_HEIGHT, int(x), self.height())
            time += beat_duration
            beat += 1

    def _draw_time_ruler(self, painter: QPainter):
        """Draw the time ruler at the top."""
        # Background
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.setBrush(QBrush(QColor(240, 240, 240)))
        painter.drawRect(self.KEYBOARD_WIDTH, 0, self.width() - self.KEYBOARD_WIDTH, self.TIME_RULER_HEIGHT)

        # Time markers
        painter.setPen(QPen(QColor(80, 80, 80)))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)

        start_time = max(0, self._x_to_time(self.KEYBOARD_WIDTH))
        end_time = self._x_to_time(self.width())

        # Show time every second
        second = int(start_time)
        while second <= end_time:
            x = self._time_to_x(float(second))
            if x >= self.KEYBOARD_WIDTH:
                minutes = second // 60
                secs = second % 60
                painter.drawText(int(x - 15), 16, f"{minutes}:{secs:02d}")
                # Tick mark
                painter.drawLine(int(x), self.TIME_RULER_HEIGHT - 4, int(x), self.TIME_RULER_HEIGHT)
            second += 1
```

**Step 3: Add note rendering**

```python
    def _draw_notes(self, painter: QPainter):
        """Draw all notes."""
        # Get visible area
        visible_left = self._x_to_time(self.KEYBOARD_WIDTH)
        visible_right = self._x_to_time(self.width())
        visible_top = self._y_to_pitch(self.TIME_RULER_HEIGHT)
        visible_bottom = self._y_to_pitch(self.height())

        for note in self.notes:
            # Skip notes outside visible area
            if note.start_time + note.duration < visible_left:
                continue
            if note.start_time > visible_right:
                continue
            if note.pitch > visible_top or note.pitch < visible_bottom:
                continue

            x = self._time_to_x(note.start_time)
            y = self._pitch_to_y(note.pitch)
            width = note.duration * self.h_zoom
            height = self.v_zoom - 2  # Small gap between rows

            # Choose color based on playability and selection
            if note == self.selected_note:
                color = QColor(255, 200, 0)  # Yellow for selected
            elif note.is_playable:
                color = self.COLOR_PLAYABLE or QColor(74, 144, 217)
            else:
                color = self.COLOR_UNPLAYABLE

            # Track coloring - slightly different shades
            if self.selected_tracks and note.track_index in self.selected_tracks:
                color = color.lighter(110)

            # Draw rounded rectangle
            painter.setPen(QPen(color.darker(120), 1))
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(int(x), int(y + 1), int(width), int(height), 3, 3)
```

**Step 4: Implement paintEvent**

```python
    def paintEvent(self, event):
        """Handle paint event."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.COLOR_BACKGROUND)

        # Draw components
        self._draw_grid(painter)
        self._draw_notes(painter)
        self._draw_keyboard(painter)
        self._draw_time_ruler(painter)

        # Draw playhead if playing
        if self.playhead_position > 0 or self.is_playing:
            self._draw_playhead(painter)

    def _draw_playhead(self, painter: QPainter):
        """Draw the playhead line."""
        x = self._time_to_x(self.playhead_position)
        if x >= self.KEYBOARD_WIDTH and x <= self.width():
            painter.setPen(QPen(self.COLOR_PLAYHEAD, 2))
            painter.drawLine(int(x), self.TIME_RULER_HEIGHT, int(x), self.height())
```

**Step 5: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: implement note grid, time ruler, and note rendering"
```

---

## Task 6: Implement Zoom and Scroll

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add scroll range update method**

Add to PianoRollWidget class:
```python
    def _update_scroll_range(self):
        """Update the scroll range based on content size."""
        content_width = int(self.total_duration * self.h_zoom + self.KEYBOARD_WIDTH)
        content_height = int((self.MAX_PITCH - self.MIN_PITCH + 1) * self.v_zoom + self.TIME_RULER_HEIGHT)
        # Store for scroll calculations
        self._content_width = content_width
        self._content_height = content_height

    def set_h_zoom(self, value: int):
        """Set horizontal zoom (pixels per second)."""
        old_h_zoom = self.h_zoom
        self.h_zoom = max(self.H_ZOOM_MIN, min(self.H_ZOOM_MAX, value))

        # Adjust scroll to keep center
        if old_h_zoom > 0:
            center_time = self._x_to_time(self.width() / 2)
            self.scroll_x = int(center_time * self.h_zoom - self.width() / 2 + self.KEYBOARD_WIDTH)

        self._update_scroll_range()
        self.update()

    def set_v_zoom(self, value: int):
        """Set vertical zoom (pixels per note)."""
        old_v_zoom = self.v_zoom
        self.v_zoom = max(self.V_ZOOM_MIN, min(self.V_ZOOM_MAX, value))

        # Adjust scroll to keep center
        if old_v_zoom > 0:
            center_pitch = self._y_to_pitch(self.height() / 2)
            self.scroll_y = int((self.MAX_PITCH - center_pitch) * self.v_zoom - self.height() / 2 + self.TIME_RULER_HEIGHT)

        self._update_scroll_range()
        self.update()
```

**Step 2: Add mouse wheel handling**

```python
    def wheelEvent(self, event):
        """Handle mouse wheel for scrolling and zooming."""
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            # Ctrl+wheel: horizontal zoom
            delta = event.angleDelta().y()
            if delta > 0:
                self.set_h_zoom(int(self.h_zoom * 1.1))
            else:
                self.set_h_zoom(int(self.h_zoom / 1.1))
        elif modifiers & Qt.ShiftModifier:
            # Shift+wheel: vertical zoom
            delta = event.angleDelta().y()
            if delta > 0:
                self.set_v_zoom(int(self.v_zoom * 1.1))
            else:
                self.set_v_zoom(int(self.v_zoom / 1.1))
        else:
            # Normal wheel: vertical scroll
            delta = event.angleDelta().y()
            self.scroll_y = max(0, self.scroll_y - delta)
            max_scroll = max(0, self._content_height - self.height())
            self.scroll_y = min(self.scroll_y, max_scroll)
            self.update()
```

**Step 3: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: implement zoom and scroll functionality"
```

---

## Task 7: Implement Note Click Selection

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add mouse press handling**

Add to PianoRollWidget class:
```python
    def mousePressEvent(self, event):
        """Handle mouse press for note selection."""
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            y = event.position().y()

            # Check if click is in the note area
            if x > self.KEYBOARD_WIDTH and y > self.TIME_RULER_HEIGHT:
                # Find clicked note
                click_time = self._x_to_time(x)
                click_pitch = self._y_to_pitch(y)

                # Search for note at this position
                found_note = None
                for note in reversed(self.notes):  # Check top notes first
                    if (note.pitch == click_pitch and
                        note.start_time <= click_time <= note.start_time + note.duration):
                        found_note = note
                        break

                self.selected_note = found_note
                if found_note:
                    self.note_clicked.emit(found_note)
                self.update()
```

**Step 2: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: implement note click selection"
```

---

## Task 8: Implement Playback Animation

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add playback control methods**

Add to PianoRollWidget class:
```python
    def start_playback(self):
        """Start playback animation."""
        self.is_playing = True
        self.playback_start_time = self.playhead_position
        self._playback_real_start = 0.0  # Will track real time
        self.playback_timer.start()

    def stop_playback(self):
        """Stop playback animation."""
        self.is_playing = False
        self.playback_timer.stop()

    def toggle_playback(self):
        """Toggle playback on/off."""
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def reset_playhead(self):
        """Reset playhead to start."""
        self.playhead_position = 0.0
        self.update()

    def _on_playback_tick(self):
        """Handle playback timer tick."""
        if not self.is_playing:
            return

        # Advance playhead (30 FPS, real-time)
        self.playhead_position += 0.033  # 33ms per frame

        # Check if playback finished
        if self.playhead_position >= self.total_duration:
            self.playhead_position = self.total_duration
            self.stop_playback()

        # Auto-scroll to follow playhead
        playhead_x = self._time_to_x(self.playhead_position)
        visible_left = self.KEYBOARD_WIDTH
        visible_right = self.width() - 50

        if playhead_x < visible_left or playhead_x > visible_right:
            self.scroll_x = int(self.playhead_position * self.h_zoom - self.width() / 2 + self.KEYBOARD_WIDTH)
            self.scroll_x = max(0, self.scroll_x)

        self.position_changed.emit(self.playhead_position)
        self.update()
```

**Step 2: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: implement playback animation with auto-scroll"
```

---

## Task 9: Create MidiVisualizerDialog Main Dialog

**Files:**
- Modify: `src/gui/MidiVisualizerDialog.py`

**Step 1: Add qfluentwidgets imports**

Add to imports:
```python
from qfluentwidgets import (MessageBoxBase, SubtitleLabel, BodyLabel,
                            StrongBodyLabel, ToolButton, Slider, FluentIcon,
                            SmoothScrollArea, CaptionLabel, isDarkTheme, themeColor)
```

**Step 2: Add MidiVisualizerDialog class**

```python
class MidiVisualizerDialog(MessageBoxBase):
    """Main dialog for MIDI visualization."""

    def __init__(self, midi_path: str, playable_range: tuple = None,
                 selected_tracks: set = None, parent=None):
        super().__init__(parent)
        self.midi_path = midi_path
        self.playable_range = playable_range
        self.selected_tracks = selected_tracks or set()

        self._setup_ui()
        self._load_midi()

    def _setup_ui(self):
        """Set up the dialog UI."""
        # Title
        self.titleLabel = SubtitleLabel(self.tr("MIDI Visualizer"), self)
        self.viewLayout.addWidget(self.titleLabel)

        # Piano roll widget
        self.piano_roll = PianoRollWidget(self)
        self.piano_roll.setMinimumHeight(400)

        # Scroll area for piano roll
        scroll = SmoothScrollArea(self)
        scroll.setWidget(self.piano_roll)
        scroll.setWidgetResizable(True)
        self.viewLayout.addWidget(scroll)

        # Toolbar
        self._setup_toolbar()

        # Info panel
        self._setup_info_panel()

        # Dialog buttons
        self.yesButton.setText(self.tr("Close"))
        self.cancelButton.hide()

        # Set dialog size
        self.widget.setMinimumSize(800, 600)

    def _setup_toolbar(self):
        """Set up the playback toolbar."""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 8, 0, 8)

        # Play/Pause button
        self.play_btn = ToolButton(FluentIcon.PLAY, self)
        self.play_btn.setCheckable(True)
        self.play_btn.clicked.connect(self._toggle_playback)
        toolbar_layout.addWidget(self.play_btn)

        # Stop button
        self.stop_btn = ToolButton(FluentIcon.STOP, self)
        self.stop_btn.clicked.connect(self._stop_playback)
        toolbar_layout.addWidget(self.stop_btn)

        toolbar_layout.addSpacing(20)

        # Horizontal zoom label
        toolbar_layout.addWidget(BodyLabel(self.tr("Zoom H:")))

        # Horizontal zoom slider
        self.h_zoom_slider = Slider(Qt.Horizontal, self)
        self.h_zoom_slider.setRange(10, 200)
        self.h_zoom_slider.setValue(50)
        self.h_zoom_slider.setFixedWidth(120)
        self.h_zoom_slider.valueChanged.connect(self._on_h_zoom_changed)
        toolbar_layout.addWidget(self.h_zoom_slider)

        toolbar_layout.addSpacing(10)

        # Vertical zoom label
        toolbar_layout.addWidget(BodyLabel(self.tr("Zoom V:")))

        # Vertical zoom slider
        self.v_zoom_slider = Slider(Qt.Horizontal, self)
        self.v_zoom_slider.setRange(8, 24)
        self.v_zoom_slider.setValue(14)
        self.v_zoom_slider.setFixedWidth(100)
        self.v_zoom_slider.valueChanged.connect(self._on_v_zoom_changed)
        toolbar_layout.addWidget(self.v_zoom_slider)

        toolbar_layout.addStretch()

        # Time display
        self.time_label = BodyLabel("0:00 / 0:00")
        toolbar_layout.addWidget(self.time_label)

        self.viewLayout.addWidget(toolbar)

    def _setup_info_panel(self):
        """Set up the note info panel."""
        self.info_panel = QWidget()
        info_layout = QHBoxLayout(self.info_panel)
        info_layout.setContentsMargins(0, 4, 0, 4)

        self.info_label = StrongBodyLabel(self.tr("Note: "))
        self.info_value = BodyLabel(self.tr("Click a note to see details"))
        info_layout.addWidget(self.info_label)
        info_layout.addWidget(self.info_value)
        info_layout.addStretch()

        self.viewLayout.addWidget(self.info_panel)

        # Connect note click signal
        self.piano_roll.note_clicked.connect(self._on_note_clicked)
        self.piano_roll.position_changed.connect(self._on_position_changed)

    def _load_midi(self):
        """Load and parse the MIDI file."""
        try:
            midi_file = mido.MidiFile(self.midi_path)
            parser = MidiParser(self.playable_range)
            notes, tempo_events, duration = parser.parse(midi_file, self.selected_tracks)

            # Set playable color from theme
            color = themeColor()
            self.piano_roll.COLOR_PLAYABLE = color
            self.piano_roll.set_notes(notes, tempo_events, duration, self.selected_tracks)

            # Update time display
            self._update_time_display(0, duration)

        except Exception as e:
            self.info_value.setText(self.tr(f"Error loading MIDI: {e}"))

    def _toggle_playback(self):
        """Toggle playback."""
        self.piano_roll.toggle_playback()
        if self.piano_roll.is_playing:
            self.play_btn.setIcon(FluentIcon.PAUSE)
        else:
            self.play_btn.setIcon(FluentIcon.PLAY)

    def _stop_playback(self):
        """Stop playback and reset."""
        self.piano_roll.stop_playback()
        self.piano_roll.reset_playhead()
        self.play_btn.setIcon(FluentIcon.PLAY)
        self.play_btn.setChecked(False)

    def _on_h_zoom_changed(self, value):
        """Handle horizontal zoom change."""
        self.piano_roll.set_h_zoom(value)

    def _on_v_zoom_changed(self, value):
        """Handle vertical zoom change."""
        self.piano_roll.set_v_zoom(value)

    def _on_note_clicked(self, note: NoteData):
        """Handle note click."""
        pitch_name = self.piano_roll._pitch_to_name(note.pitch)
        playable = self.tr("Playable") if note.is_playable else self.tr("Unplayable")
        self.info_value.setText(
            f"{pitch_name} | Time: {note.start_time:.2f}s | Duration: {note.duration:.2f}s | "
            f"Velocity: {note.velocity} | {playable}"
        )

    def _on_position_changed(self, time: float):
        """Handle playhead position change."""
        self._update_time_display(time, self.piano_roll.total_duration)

    def _update_time_display(self, current: float, total: float):
        """Update the time display label."""
        current_min = int(current // 60)
        current_sec = int(current % 60)
        total_min = int(total // 60)
        total_sec = int(total % 60)
        self.time_label.setText(f"{current_min}:{current_sec:02d} / {total_min}:{total_sec:02d}")
```

**Step 3: Add QHBoxLayout import**

Add to imports:
```python
from PySide6.QtWidgets import QWidget, QSizePolicy, QHBoxLayout
```

**Step 4: Commit**

```bash
git add src/gui/MidiVisualizerDialog.py
git commit -m "feat: implement MidiVisualizerDialog with toolbar and info panel"
```

---

## Task 10: Integrate with MidiPlayerTask

**Files:**
- Modify: `src/tasks/MidiPlayerTask.py`

**Step 1: Add import**

Add at top of `src/tasks/MidiPlayerTask.py`:
```python
from src.gui.MidiVisualizerDialog import MidiVisualizerDialog
```

**Step 2: Add visualize button in __init__**

Find the line with `self.config_type['MIDI Folder']` and add after it:
```python
        self.config_type['Visualization'] = {'type': "button", 'buttons': [
            {'icon': FluentIcon.MUSIC, 'text': 'Visualize', 'callback': self.open_visualizer},
        ]}
```

**Step 3: Add open_visualizer method**

Add method to MidiPlayerTask class (after `open_track_selector` method):
```python
    def open_visualizer(self):
        """Open the MIDI visualizer dialog."""
        midi_file_name = self.config.get('MIDI File')
        if not midi_file_name or midi_file_name == 'No MIDI files found.':
            if hasattr(self, 'log_error'):
                self.log_error("请先选择一个有效的 MIDI 文件。")
            return

        file_path = os.path.join(self.midi_dir, midi_file_name)
        if not os.path.exists(file_path):
            return

        # Get selected tracks
        selections = self.config.get('_track_selections', {})
        selected_tracks = set(selections.get(midi_file_name, []))

        # Get playable range from pitch_to_key
        playable_min = min(self.pitch_to_key.keys())
        playable_max = max(self.pitch_to_key.keys())

        # Open visualizer dialog
        dialog = MidiVisualizerDialog(
            midi_path=file_path,
            playable_range=(playable_min, playable_max),
            selected_tracks=selected_tracks,
            parent=og.app.main_window
        )
        dialog.exec()
```

**Step 4: Commit**

```bash
git add src/tasks/MidiPlayerTask.py
git commit -m "feat: integrate MIDI visualizer with MidiPlayerTask"
```

---

## Task 11: Final Testing and Polish

**Files:**
- None (testing only)

**Step 1: Run the application**

```bash
python main_debug.py
```

**Step 2: Manual test checklist**

1. Open MIDI Player task in onetime tasks
2. Select a MIDI file
3. Click "Visualize" button
4. Verify piano roll displays correctly
5. Test zoom sliders
6. Test mouse wheel zoom (Ctrl+wheel, Shift+wheel)
7. Test scroll with mouse wheel
8. Click on notes to see details
9. Test play/pause button
10. Test stop button
11. Verify playhead animation
12. Check playable/unplayable note colors
13. Close dialog

**Step 3: Fix any issues found during testing**

If issues found, fix and commit with descriptive message.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete MIDI piano roll visualizer"
```

---

## Summary

This implementation adds:
- `NoteData` and `TempoEvent` dataclasses for MIDI data representation
- `MidiParser` class for converting MIDI files to visualizable data
- `PianoRollWidget` custom widget with full rendering and interaction
- `MidiVisualizerDialog` main dialog with toolbar and info panel
- Integration with `MidiPlayerTask` via "Visualize" button

Features:
- Piano roll grid with keyboard visualization
- Note rendering with playable/unplayable color coding
- Horizontal and vertical zoom
- Mouse wheel scroll and zoom
- Click-to-select notes with detail display
- Playback animation with auto-scrolling playhead
- Time ruler display