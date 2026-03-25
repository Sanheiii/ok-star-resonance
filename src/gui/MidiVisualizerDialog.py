import mido
from mido import MidiFile, bpm2tempo
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget, QSizePolicy, QHBoxLayout, QSlider
from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QElapsedTimer, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from qfluentwidgets import (MessageBoxBase, SubtitleLabel, BodyLabel,
                            StrongBodyLabel, ToolButton, FluentIcon,
                            SmoothScrollArea, CaptionLabel, isDarkTheme, themeColor)
from ok import og


@dataclass
class NoteData:
    """Stores parsed MIDI note information."""
    pitch: int  # MIDI note number (0-127)
    start_time: float  # Start time in seconds
    duration: float  # Duration in seconds
    velocity: int  # Note velocity (0-127)
    track_index: int  # Which track this note belongs to
    is_playable: bool  # Whether this note is in playable range (A0-C8)
    is_multi_person: bool = False  # Whether this note is in a section unplayable by single person


@dataclass
class UnplayableSection:
    """Stores information about sections unplayable by single person."""
    start_time: float
    end_time: float
    min_pitch: int
    max_pitch: int


@dataclass
class TempoEvent:
    """Stores tempo change information."""
    time: float  # Time in seconds when tempo changes
    bpm: float  # Tempo in beats per minute


class MidiParser:
    """Parses MIDI files into NoteData objects."""

    # Overall playable range for the game (A0=21 to C8=108)
    OVERALL_MIN = 21  # A0
    OVERALL_MAX = 108  # C8
    # Default display range (C3-B5, middle 3 octaves)
    DEFAULT_MIN = 48  # C3
    DEFAULT_MAX = 83  # B5

    def __init__(self, playable_range: Tuple[int, int] = None):
        # Use overall playable range for determining if a note can be played
        self.playable_min = playable_range[0] if playable_range else self.OVERALL_MIN
        self.playable_max = playable_range[1] if playable_range else self.OVERALL_MAX

    def is_playable(self, pitch: int) -> bool:
        """Check if a note is within overall playable range (A0-C8)."""
        return self.playable_min <= pitch <= self.playable_max

    def parse(self, midi_file: MidiFile, selected_tracks: Set[int] = None) -> Tuple[List[NoteData], List[TempoEvent], float, List['UnplayableSection']]:
        """
        Parse MIDI file into notes and tempo events.

        Returns:
            Tuple of (notes list, tempo events list, total duration in seconds, unplayable sections)
        """
        notes = []
        tempo_events = []

        # Build tempo map
        tempo_map = self._build_tempo_map(midi_file, tempo_events)

        # Parse notes from all tracks
        for track_idx, track in enumerate(midi_file.tracks):
            # Skip unselected tracks if selection is specified and non-empty
            if selected_tracks and track_idx not in selected_tracks:
                continue

            self._parse_track(track, track_idx, midi_file.ticks_per_beat, tempo_map, notes)

        # Sort notes by start time
        notes.sort(key=lambda n: n.start_time)

        # Calculate total duration
        total_duration = max((n.start_time + n.duration for n in notes), default=0.0)

        # Detect multi-person sections
        unplayable_sections = self._detect_multi_person_sections(notes)

        return notes, tempo_events, total_duration, unplayable_sections

    def _detect_multi_person_sections(self, notes: List[NoteData]) -> List['UnplayableSection']:
        """
        Detect sections where notes span across 4+ pages simultaneously.

        A single page with octave modifiers can cover ~5 octaves (60 semitones).
        If notes at the same time span more than this, it's unplayable by single person.
        """
        if not notes:
            return []

        # Build events list: (time, is_start, note)
        events = []
        for note in notes:
            if note.is_playable:  # Only check playable notes
                events.append((note.start_time, True, note))
                events.append((note.start_time + note.duration, False, note))

        events.sort(key=lambda e: (e[0], not e[1]))  # Sort by time, ends before starts

        unplayable_sections = []
        active_notes: List[NoteData] = []
        current_section_start = None

        for time, is_start, note in events:
            if is_start:
                active_notes.append(note)
            else:
                if note in active_notes:
                    active_notes.remove(note)

            if active_notes:
                min_pitch = min(n.pitch for n in active_notes)
                max_pitch = max(n.pitch for n in active_notes)
                pitch_span = max_pitch - min_pitch

                # If span > 48 semitones (4 octaves), requires 4+ page switches
                # This is unplayable by single person
                if pitch_span > 48:
                    if current_section_start is None:
                        current_section_start = time
                    # Mark all active notes as multi-person
                    for n in active_notes:
                        n.is_multi_person = True
                else:
                    if current_section_start is not None:
                        # End of unplayable section
                        unplayable_sections.append(UnplayableSection(
                            start_time=current_section_start,
                            end_time=time,
                            min_pitch=min_pitch,
                            max_pitch=max_pitch
                        ))
                        current_section_start = None
            else:
                if current_section_start is not None:
                    unplayable_sections.append(UnplayableSection(
                        start_time=current_section_start,
                        end_time=time,
                        min_pitch=0,
                        max_pitch=127
                    ))
                    current_section_start = None

        return unplayable_sections

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
        active_notes: Dict[int, Tuple[int, int, float]] = {}  # pitch -> (start_tick, velocity, start_time)

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

    # Playback
    PLAYHEAD_MARGIN = 50  # Pixels from edge to trigger auto-scroll

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
    COLOR_MULTI_PERSON = QColor(255, 165, 0)  # Orange for multi-person notes
    COLOR_UNPLAYABLE_SECTION = QColor(255, 0, 0, 50)  # Light red for unplayable sections
    COLOR_BACKGROUND = QColor(255, 255, 255)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes: List[NoteData] = []
        self.tempo_events: List[TempoEvent] = []
        self.total_duration = 0.0
        self.selected_tracks: Set[int] = set()
        self.unplayable_sections: List[UnplayableSection] = []

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
        self._elapsed_timer = QElapsedTimer()

        # MIDI output for sound playback
        self._midi_out = None
        self._playing_midi_notes: Set[int] = set()  # Currently playing MIDI notes

        # Interaction state
        self.selected_note: Optional[NoteData] = None
        self.setMouseTracking(True)

        # Content size for scroll calculations
        self._content_width = 0
        self._content_height = 0

        # Widget setup
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        # Enable scrollbars via mouse wheel
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def set_notes(self, notes: List[NoteData], tempo_events: List[TempoEvent], duration: float, selected_tracks: Set[int] = None, unplayable_sections: List[UnplayableSection] = None):
        """Set the notes to display."""
        self.notes = notes
        self.tempo_events = tempo_events
        self.total_duration = duration
        self.selected_tracks = selected_tracks or set()
        self.unplayable_sections = unplayable_sections or []
        self._update_scroll_range()
        self._scroll_to_playable_range()
        self.update()

    def _scroll_to_playable_range(self):
        """Scroll the view to show the playable range (C3-B5) centered vertically."""
        # Center on C4 (pitch 60) which is in the middle of playable range
        center_pitch = 60  # C4
        # Calculate scroll position to center this pitch
        target_y = (self.MAX_PITCH - center_pitch) * self.v_zoom
        # Center it in the visible area
        if self.height() > 0:
            self.scroll_y = int(target_y - self.height() / 2 + self.TIME_RULER_HEIGHT)
            self.scroll_y = max(0, self.scroll_y)

        # Scroll horizontally to show the beginning of the piece
        self.scroll_x = 0

    def set_playable_color(self, color: QColor):
        """Set the color for playable notes."""
        self.COLOR_PLAYABLE = color

    def _update_scroll_range(self):
        """Update the scroll range based on content size."""
        content_width = int(self.total_duration * self.h_zoom + self.KEYBOARD_WIDTH)
        content_height = int((self.MAX_PITCH - self.MIN_PITCH + 1) * self.v_zoom + self.TIME_RULER_HEIGHT)
        # Store for scroll calculations
        self._content_width = content_width
        self._content_height = content_height

    def _on_playback_tick(self):
        """Handle playback timer tick with MIDI sound."""
        if not self.is_playing:
            return

        prev_position = self.playhead_position

        # Use actual elapsed time for accurate playback
        elapsed = self._elapsed_timer.elapsed() / 1000.0  # Convert ms to seconds
        self.playhead_position = self.playback_start_time + elapsed

        # Check if playback finished
        if self.playhead_position >= self.total_duration:
            self.playhead_position = self.total_duration
            self.stop_playback()
        else:
            # Play MIDI notes
            self._play_midi_notes(prev_position, self.playhead_position)

        # Auto-scroll to follow playhead
        playhead_x = self._time_to_x(self.playhead_position)
        visible_left = self.KEYBOARD_WIDTH
        visible_right = self.width() - self.PLAYHEAD_MARGIN

        if playhead_x < visible_left or playhead_x > visible_right:
            self.scroll_x = int(self.playhead_position * self.h_zoom - self.width() / 2 + self.KEYBOARD_WIDTH)
            self.scroll_x = max(0, self.scroll_x)

        self.position_changed.emit(self.playhead_position)
        self.update()

    def _play_midi_notes(self, prev_time: float, current_time: float):
        """Send MIDI messages for notes between prev_time and current_time."""
        if not self._midi_out:
            return

        # Find notes that should end (note_off)
        notes_to_end = []
        for note in self.notes:
            note_end = note.start_time + note.duration
            if note_end > prev_time and note_end <= current_time and note.pitch in self._playing_midi_notes:
                notes_to_end.append(note.pitch)

        # Send note_off
        for pitch in notes_to_end:
            self._midi_out.send(mido.Message('note_off', note=pitch, velocity=0))
            self._playing_midi_notes.discard(pitch)

        # Find notes that should start (note_on)
        for note in self.notes:
            if note.start_time > prev_time and note.start_time <= current_time:
                if note.pitch not in self._playing_midi_notes:
                    # Use velocity from note, or default to 80
                    velocity = min(127, max(1, note.velocity if note.velocity > 0 else 80))
                    self._midi_out.send(mido.Message('note_on', note=note.pitch, velocity=velocity))
                    self._playing_midi_notes.add(note.pitch)

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
            # Shift+wheel: horizontal scroll
            delta = event.angleDelta().y()
            self.scroll_x = max(0, self.scroll_x - delta)
            max_scroll = max(0, self._content_width - self.width())
            self.scroll_x = min(self.scroll_x, max_scroll)
            self.update()
        else:
            # Normal wheel: vertical scroll
            delta = event.angleDelta().y()
            self.scroll_y = max(0, self.scroll_y - delta)
            max_scroll = max(0, self._content_height - self.height())
            self.scroll_y = min(self.scroll_y, max_scroll)
            self.update()
        event.accept()

    def mousePressEvent(self, event):
        """Handle mouse press for note selection and seeking."""
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            y = event.position().y()

            # Click on time ruler to seek
            if x > self.KEYBOARD_WIDTH and y <= self.TIME_RULER_HEIGHT:
                click_time = self._x_to_time(x)
                self.seek_to(click_time)
                return

            # Click in note area
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

    def start_playback(self):
        """Start playback animation with MIDI sound."""
        self.is_playing = True
        self.playback_start_time = self.playhead_position
        self._elapsed_timer.start()
        self.playback_timer.start()

        # Initialize MIDI output
        try:
            if self._midi_out is None:
                self._midi_out = mido.open_output(autoreset=True)
        except Exception:
            self._midi_out = None  # MIDI not available

    def stop_playback(self):
        """Stop playback animation and silence all MIDI notes."""
        self.is_playing = False
        self.playback_timer.stop()

        # Stop all MIDI notes
        if self._midi_out:
            for note in list(self._playing_midi_notes):
                self._midi_out.send(mido.Message('note_off', note=note, velocity=0))
            self._playing_midi_notes.clear()

    def cleanup(self):
        """Clean up resources - stop playback and close MIDI port."""
        self.stop_playback()
        if self._midi_out:
            try:
                # Send all notes off to ensure sound stops
                self._midi_out.send(mido.Message('control_change', control=123, value=0))
                self._midi_out.close()
            except Exception:
                pass
            self._midi_out = None

    def toggle_playback(self):
        """Toggle playback on/off."""
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def reset_playhead(self):
        """Reset playhead to start."""
        self.stop_playback()
        self.playhead_position = 0.0
        self.scroll_x = 0  # Reset scroll to show beginning
        self.position_changed.emit(self.playhead_position)  # Notify listeners
        self.update()

    def seek_to(self, time: float):
        """Seek to a specific time position."""
        # Stop all playing notes before seeking
        if self._midi_out and self._playing_midi_notes:
            for note in list(self._playing_midi_notes):
                self._midi_out.send(mido.Message('note_off', note=note, velocity=0))
            self._playing_midi_notes.clear()

        # Set new position
        self.playhead_position = max(0.0, min(time, self.total_duration))

        # If playing, reset the elapsed timer
        if self.is_playing:
            self.playback_start_time = self.playhead_position
            self._elapsed_timer.start()

        self.position_changed.emit(self.playhead_position)
        self.update()

    # --- Piano Keyboard Rendering (Task 4) ---

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
        return (self.MAX_PITCH - pitch) * self.v_zoom - self.scroll_y + self.TIME_RULER_HEIGHT

    def _y_to_pitch(self, y: float) -> int:
        """Convert y coordinate to pitch."""
        pitch = self.MAX_PITCH - int((y - self.TIME_RULER_HEIGHT + self.scroll_y) / self.v_zoom)
        return max(self.MIN_PITCH, min(self.MAX_PITCH, pitch))

    def _draw_keyboard(self, painter: QPainter):
        """Draw the piano keyboard on the left side."""
        keyboard_rect = self.KEYBOARD_WIDTH

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

    # --- Note Grid and Time Ruler Rendering (Task 5) ---

    def _time_to_x(self, time: float) -> float:
        """Convert time in seconds to x coordinate."""
        return time * self.h_zoom - self.scroll_x + self.KEYBOARD_WIDTH

    def _x_to_time(self, x: float) -> float:
        """Convert x coordinate to time in seconds."""
        return (x - self.KEYBOARD_WIDTH + self.scroll_x) / self.h_zoom

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
            elif note.is_multi_person:
                color = self.COLOR_MULTI_PERSON  # Orange for multi-person notes
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

    def _draw_unplayable_sections(self, painter: QPainter):
        """Draw red outlines for sections unplayable by single person."""
        for section in self.unplayable_sections:
            x_start = self._time_to_x(section.start_time)
            x_end = self._time_to_x(section.end_time)
            y_top = self._pitch_to_y(section.max_pitch)
            y_bottom = self._pitch_to_y(section.min_pitch) + self.v_zoom

            # Only draw if visible
            if x_end < self.KEYBOARD_WIDTH or x_start > self.width():
                continue

            # Clip to visible area
            x_start = max(self.KEYBOARD_WIDTH, x_start)
            x_end = min(self.width(), x_end)

            # Draw semi-transparent red background
            painter.fillRect(int(x_start), int(y_top), int(x_end - x_start),
                           int(y_bottom - y_top), self.COLOR_UNPLAYABLE_SECTION)

            # Draw red outline
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(int(x_start), int(y_top), int(x_end - x_start),
                           int(y_bottom - y_top))

    def paintEvent(self, event):
        """Handle paint event."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.COLOR_BACKGROUND)

        # Draw components
        self._draw_grid(painter)
        self._draw_playable_range(painter)
        self._draw_unplayable_sections(painter)
        self._draw_notes(painter)
        self._draw_keyboard(painter)
        self._draw_time_ruler(painter)

        # Draw playhead if playing
        if self.playhead_position > 0 or self.is_playing:
            self._draw_playhead(painter)

    def _draw_playable_range(self, painter: QPainter):
        """Draw the playable range outline (A0 to C8)."""
        # Playable range: A0 (pitch 21) to C8 (pitch 108)
        playable_min = 21  # A0
        playable_max = 108  # C8

        # Calculate y coordinates
        y_min = self._pitch_to_y(playable_max)  # Top (higher pitch)
        y_max = self._pitch_to_y(playable_min) + self.v_zoom  # Bottom (lower pitch)

        # Draw semi-transparent background for playable area
        playable_color = QColor(74, 144, 217, 30)  # Light blue, transparent
        painter.fillRect(self.KEYBOARD_WIDTH, int(y_min),
                        self.width() - self.KEYBOARD_WIDTH, int(y_max - y_min),
                        playable_color)

        # Draw border lines for playable range
        painter.setPen(QPen(QColor(74, 144, 217, 100), 2, Qt.DashLine))
        painter.drawLine(self.KEYBOARD_WIDTH, int(y_min),
                        self.width(), int(y_min))
        painter.drawLine(self.KEYBOARD_WIDTH, int(y_max),
                        self.width(), int(y_max))

        # Draw labels
        painter.setPen(QPen(QColor(100, 100, 100)))
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)
        painter.drawText(self.KEYBOARD_WIDTH + 5, int(y_min + 12), "C8")
        painter.drawText(self.KEYBOARD_WIDTH + 5, int(y_max - 3), "A0")

    def _draw_playhead(self, painter: QPainter):
        """Draw the playhead line."""
        x = self._time_to_x(self.playhead_position)
        if x >= self.KEYBOARD_WIDTH and x <= self.width():
            painter.setPen(QPen(self.COLOR_PLAYHEAD, 2))
            painter.drawLine(int(x), self.TIME_RULER_HEIGHT, int(x), self.height())


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
        self.titleLabel = SubtitleLabel(og.app.tr("MIDI Visualizer"), self)
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
        self.yesButton.setText(og.app.tr("Close"))
        self.yesButton.clicked.connect(self._on_close)
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
        self.stop_btn = ToolButton(FluentIcon.POWER_BUTTON, self)
        self.stop_btn.clicked.connect(self._stop_playback)
        toolbar_layout.addWidget(self.stop_btn)

        toolbar_layout.addSpacing(20)

        # Horizontal zoom label
        toolbar_layout.addWidget(BodyLabel(og.app.tr("Zoom H:")))

        # Horizontal zoom slider
        self.h_zoom_slider = QSlider(Qt.Horizontal, self)
        self.h_zoom_slider.setRange(10, 200)
        self.h_zoom_slider.setValue(50)
        self.h_zoom_slider.setFixedWidth(120)
        self.h_zoom_slider.valueChanged.connect(self._on_h_zoom_changed)
        toolbar_layout.addWidget(self.h_zoom_slider)

        toolbar_layout.addSpacing(10)

        # Vertical zoom label
        toolbar_layout.addWidget(BodyLabel(og.app.tr("Zoom V:")))

        # Vertical zoom slider
        self.v_zoom_slider = QSlider(Qt.Horizontal, self)
        self.v_zoom_slider.setRange(8, 24)
        self.v_zoom_slider.setValue(14)
        self.v_zoom_slider.setFixedWidth(100)
        self.v_zoom_slider.valueChanged.connect(self._on_v_zoom_changed)
        toolbar_layout.addWidget(self.v_zoom_slider)

        toolbar_layout.addStretch()

        # Timeline slider for seeking
        self.timeline_slider = QSlider(Qt.Horizontal, self)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setFixedWidth(200)
        self.timeline_slider.sliderPressed.connect(self._on_timeline_pressed)
        self.timeline_slider.sliderReleased.connect(self._on_timeline_released)
        self.timeline_slider.valueChanged.connect(self._on_timeline_changed)
        self._timeline_dragging = False
        self._timeline_updating = False
        toolbar_layout.addWidget(self.timeline_slider)

        # Time display
        self.time_label = BodyLabel("0:00 / 0:00")
        toolbar_layout.addWidget(self.time_label)

        self.viewLayout.addWidget(toolbar)

    def _setup_info_panel(self):
        """Set up the note info panel."""
        self.info_panel = QWidget()
        info_layout = QHBoxLayout(self.info_panel)
        info_layout.setContentsMargins(0, 4, 0, 4)

        self.info_label = StrongBodyLabel(og.app.tr("Note: "))
        self.info_value = BodyLabel(og.app.tr("Click a note to see details"))
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
            notes, tempo_events, duration, unplayable_sections = parser.parse(midi_file, self.selected_tracks)

            # Set playable color from theme
            color = themeColor()
            self.piano_roll.COLOR_PLAYABLE = color
            self.piano_roll.set_notes(notes, tempo_events, duration, self.selected_tracks, unplayable_sections)

            # Update time display
            self._update_time_display(0, duration)

            # Show warning if there are unplayable sections
            if unplayable_sections:
                self.info_value.setText(og.app.tr("⚠ Contains {} sections unplayable by single person").format(len(unplayable_sections)))

        except Exception as e:
            self.info_value.setText(og.app.tr("Error loading MIDI: {}").format(e))

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
        # Explicitly reset slider and time display
        self._timeline_updating = True
        self.timeline_slider.setValue(0)
        self._timeline_updating = False
        self._update_time_display(0, self.piano_roll.total_duration)

    def _on_h_zoom_changed(self, value):
        """Handle horizontal zoom change."""
        self.piano_roll.set_h_zoom(value)

    def _on_v_zoom_changed(self, value):
        """Handle vertical zoom change."""
        self.piano_roll.set_v_zoom(value)

    def _on_note_clicked(self, note: NoteData):
        """Handle note click."""
        pitch_name = self.piano_roll._pitch_to_name(note.pitch)
        playable = og.app.tr("Playable") if note.is_playable else og.app.tr("Unplayable")
        self.info_value.setText(
            f"{pitch_name} | Time: {note.start_time:.2f}s | Duration: {note.duration:.2f}s | "
            f"Velocity: {note.velocity} | {playable}"
        )

    def _on_position_changed(self, time: float):
        """Handle playhead position change."""
        self._update_time_display(time, self.piano_roll.total_duration)
        # Update timeline slider (if not dragging)
        if not self._timeline_dragging and self.piano_roll.total_duration > 0:
            progress = time / self.piano_roll.total_duration
            new_value = int(progress * 1000)
            # Only update if value actually changed to avoid unnecessary updates
            if self.timeline_slider.value() != new_value:
                self._timeline_updating = True
                self.timeline_slider.setValue(new_value)
                self._timeline_updating = False

    def _on_timeline_pressed(self):
        """Handle timeline slider pressed - pause updates during drag."""
        self._timeline_dragging = True

    def _on_timeline_released(self):
        """Handle timeline slider released - seek to position."""
        self._timeline_dragging = False
        if self.piano_roll.total_duration > 0:
            progress = self.timeline_slider.value() / 1000.0
            seek_time = progress * self.piano_roll.total_duration
            self.piano_roll.seek_to(seek_time)

    def _on_timeline_changed(self, value: int):
        """Handle timeline slider value change during drag."""
        # Ignore if this is an internal update (not user interaction)
        if hasattr(self, '_timeline_updating') and self._timeline_updating:
            return
        if self._timeline_dragging and self.piano_roll.total_duration > 0:
            progress = value / 1000.0
            seek_time = progress * self.piano_roll.total_duration
            self._update_time_display(seek_time, self.piano_roll.total_duration)

    def _update_time_display(self, current: float, total: float):
        """Update the time display label."""
        current_min = int(current // 60)
        current_sec = int(current % 60)
        total_min = int(total // 60)
        total_sec = int(total % 60)
        self.time_label.setText(f"{current_min}:{current_sec:02d} / {total_min}:{total_sec:02d}")

    def _on_close(self):
        """Handle close button click."""
        self.piano_roll.cleanup()

    def closeEvent(self, event):
        """Handle dialog close - clean up resources."""
        self.piano_roll.cleanup()
        super().closeEvent(event)

    def reject(self):
        """Handle dialog rejection (X button) - clean up resources."""
        self.piano_roll.cleanup()
        super().reject()
