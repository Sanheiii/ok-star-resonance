# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ok-star-resonance is a Windows automation tool for the game "Star Resonance" (星痕共鸣). It uses image recognition, OCR, and YOLO object detection to automate gameplay tasks like fishing, gathering, and MIDI playback. The tool interacts with the game only through the UI (screen capture and simulated input) - no memory reading or game file modification.

**Core Technologies:**
- **ok-script**: The underlying automation framework providing task orchestration, GUI, OCR, and input simulation
- **OpenVINO/ONNX Runtime**: For YOLO8 object detection (fish splash detection)
- **onnxocr-ppocrv5**: For text recognition in multiple languages (zh, en, jp)
- **PySide6 + qfluentwidgets**: For the GUI

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt --upgrade

# Run release version
python main.py

# Run debug version (enables debug mode with additional logging and screenshot saving)
python main_debug.py
```

**Requirements:** Python 3.12 only. Windows platform.

## Architecture

### Entry Point
- `main.py` / `main_debug.py`: Initialize the `ok.OK` application with config from `src/config.py`

### Configuration (`src/config.py`)
Central configuration file that defines:
- Game window settings (executable names, capture method, resolution requirements)
- OCR settings (language support, OpenVINO toggle)
- Task registration (`onetime_tasks` and `trigger_tasks`)
- GUI settings and template matching parameters

### Global State (`src/globals.py`)
- `Globals` class: Manages the YOLO model singleton loaded via `og.my_app`
- Model switching between OpenVINO and ONNX based on config

### Task System
Two types of tasks registered in config:

**Trigger Tasks** (`trigger_tasks`): Run continuously when enabled, respond to game state changes
- Extend `SRTriggerTask` → `TriggerTask` → `BaseTask`
- Examples: `FishingTask`, `GatherTask`, `AutoSkillTask`

**Onetime Tasks** (`onetime_tasks`): Run once on demand
- Extend `BaseTask` directly
- Examples: `GuildHuntAssistTask`, `MidiPlayerTask`

### Task Class Hierarchy
```
BaseTask (ok-script)
├── TriggerTask (ok-script) - for continuous monitoring
│   └── SRTriggerTask (src/tasks/SRTriggerTask.py)
│       └── FishingTask, GatherTask, AutoSkillTask, etc.
└── BaseTask direct - for onetime execution
    └── GuildHuntAssistTask, MidiPlayerTask
```

### Key Files

| File | Purpose |
|------|---------|
| `src/config.py` | Application configuration, task registration |
| `src/globals.py` | YOLO model singleton management |
| `src/tasks/SRTriggerTask.py` | Base class for trigger tasks with mouse helpers and language utilities |
| `src/OpenVinoYolo8Detect.py` | YOLO8 inference using OpenVINO |
| `src/OnnxYolo8Detect.py` | YOLO8 inference using ONNX Runtime |
| `assets/models/bpsr_splash.onnx` | YOLO model for fish splash detection |
| `assets/result.json` | COCO format annotations for template matching images |
| `configs/` | JSON files storing task configurations (auto-generated) |

### Creating a New Task

1. Create a new file in `src/tasks/` extending `SRTriggerTask` (for trigger tasks) or `BaseTask` (for onetime tasks)
2. Define `name`, `description`, and `default_config` in `__init__`
3. Implement the `run()` method
4. Register in `src/config.py` under `trigger_tasks` or `onetime_tasks`

### Coordinate System
All screen coordinates use normalized values (0.0-1.0) relative to screen dimensions:
- `self.click(0.5, 0.5)` clicks the center of the screen
- `self.box_of_screen(x1, y1, x2, y2)` creates a normalized box

### Multi-language Support
Tasks use `get_game_language()` to detect the configured game client language (zhs, zht, en, jp) and match localized text patterns accordingly. Define regex patterns in `regex_map` for language-specific OCR matching.

## Building

The project uses PyAppify for building Windows executables. The GitHub Actions workflow `.github/workflows/build-application.yml` handles releases on version tags.

## Important Notes

- The game requires 16:9 aspect ratio resolution
- Template matching images are stored in `assets/images/` and annotated in `assets/result.json`
- User configurations are persisted in `configs/*.json`
- MIDI files for the MIDI Player task go in `./midi/` directory