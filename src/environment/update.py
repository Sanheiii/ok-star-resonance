"""Create and launch a versioned, external environment repair plan."""

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


PLAN_VERSION = 2
PLAN_FILE_NAME = "python_environment_update.json"
LOG_FILE_NAME = "python_environment_update.log"
RESTART_ENVIRONMENT_NAMES = (
    "PYAPPIFY_VERSION",
    "PYAPPIFY_APP_PROFILE",
    "PYAPPIFY_APP_VERSION",
    "PYAPPIFY_APP_JSON_PATH",
    "PYAPPIFY_EXECUTABLE",
)


@dataclass(frozen=True)
class UpdatePlan:
    version: int
    process_ids: tuple[int, ...]
    python_executable: str
    requirements: tuple[str, ...]
    index_url: str | None
    restart_command: tuple[str, ...]
    restart_environment: tuple[tuple[str, str | None], ...]
    working_directory: str
    log_path: str

    @property
    def pip_arguments(self) -> list[str]:
        arguments = ["-m", "pip", "install", "--no-deps"]
        if self.index_url:
            arguments.extend(["--index-url", self.index_url])
        arguments.extend(self.requirements)
        return arguments

    def to_dict(self) -> dict:
        data = asdict(self)
        data["process_ids"] = list(self.process_ids)
        data["requirements"] = list(self.requirements)
        data["restart_command"] = list(self.restart_command)
        data["restart_environment"] = dict(self.restart_environment)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "UpdatePlan":
        if data.get("version") != PLAN_VERSION:
            raise ValueError(
                f"Unsupported update plan version: {data.get('version')}"
            )
        requirements = tuple(str(value) for value in data["requirements"])
        if not requirements:
            raise ValueError("The update plan contains no requirements")
        return cls(
            version=PLAN_VERSION,
            process_ids=tuple(int(value) for value in data["process_ids"]),
            python_executable=str(data["python_executable"]),
            requirements=requirements,
            index_url=str(data["index_url"]) if data.get("index_url") else None,
            restart_command=tuple(str(value) for value in data["restart_command"]),
            restart_environment=tuple(
                (name, data["restart_environment"].get(name))
                for name in RESTART_ENVIRONMENT_NAMES
            ),
            working_directory=str(data["working_directory"]),
            log_path=str(data["log_path"]),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)

    @classmethod
    def load(cls, path: Path) -> "UpdatePlan":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


class EnvironmentUpdateLauncher:
    def __init__(self, working_directory: Path | None = None):
        self.working_directory = (working_directory or Path.cwd()).resolve()

    def launch(self, requirements: tuple[str, ...], index_url: str | None) -> None:
        plan = UpdatePlan(
            version=PLAN_VERSION,
            process_ids=python_process_chain(),
            python_executable=str(find_python_executable(self.working_directory)),
            requirements=requirements,
            index_url=index_url,
            restart_command=build_restart_command(),
            restart_environment=capture_restart_environment(),
            working_directory=str(self.working_directory),
            log_path=str(self.working_directory / "logs" / LOG_FILE_NAME),
        )
        plan_path = self.working_directory / "configs" / PLAN_FILE_NAME
        plan.save(plan_path)

        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE
        )
        subprocess.Popen(
            [
                plan.python_executable,
                "-m",
                "src.environment.updater",
                str(plan_path),
            ],
            cwd=str(self.working_directory),
            close_fds=True,
            creationflags=creation_flags,
        )


def find_python_executable(base_path: Path | None = None) -> Path:
    base_path = (base_path or Path.cwd()).resolve()
    executable = Path(sys.executable).resolve()
    candidates = (
        base_path / "python" / "app_env" / "Scripts" / "python.exe",
        executable.parent / "python" / "app_env" / "Scripts" / "python.exe",
        executable,
    )
    selected = next(
        (candidate for candidate in candidates if candidate.is_file()), executable
    )
    return console_executable(selected)


def build_restart_command() -> tuple[str, ...]:
    executable = gui_executable(Path(sys.executable).resolve())
    argv = list(sys.argv)
    if argv and Path(argv[0]).suffix.lower() in {".py", ".pyw"}:
        return tuple([str(executable), *argv])
    return tuple([str(executable), *argv[1:]])


def gui_executable(executable: Path) -> Path:
    """Use pythonw for Python entrypoints so restarts create only the GUI."""
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.is_file():
            return pythonw
    return executable


def console_executable(executable: Path) -> Path:
    """Use python.exe for the updater so CREATE_NEW_CONSOLE is effective."""
    if executable.name.lower() == "pythonw.exe":
        python = executable.with_name("python.exe")
        if python.is_file():
            return python
    return executable


def capture_restart_environment() -> tuple[tuple[str, str | None], ...]:
    return tuple((name, os.environ.get(name)) for name in RESTART_ENVIRONMENT_NAMES)


def python_process_chain() -> tuple[int, ...]:
    import psutil

    process = psutil.Process()
    process_ids = [process.pid]
    while parent := process.parent():
        try:
            if parent.name().lower() not in {"python.exe", "pythonw.exe"}:
                break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            break
        process_ids.append(parent.pid)
        process = parent
    return tuple(process_ids)
