import os
import subprocess
import unittest
from dataclasses import replace
from importlib import metadata
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from src.environment import updater
from src.environment.checker import PythonEnvironmentChecker, load_requirements
from src.environment.update import (
    PLAN_VERSION,
    EnvironmentUpdateLauncher,
    RESTART_ENVIRONMENT_NAMES,
    UpdatePlan,
    capture_restart_environment,
    console_executable,
    gui_executable,
)


class RequirementsText:
    def __init__(self, content):
        self.content = content

    def read_text(self, **_kwargs):
        return self.content


class PythonEnvironmentTest(unittest.TestCase):
    def test_load_requirements_ignores_comments_options_and_false_markers(self):
        path = RequirementsText(
            "# generated file\n--index-url https://example.invalid/simple\n"
            "demo==1.2.3\nignored==1; python_version < '1'\n"
        )

        self.assertEqual(
            ["demo==1.2.3"], [str(item) for item in load_requirements(path)]
        )

    def test_checker_returns_structured_missing_and_outdated_issues(self):
        path = RequirementsText("present==1.0\nwrong>=2\nmissing==3\n")
        versions = {"present": "1.0", "wrong": "1.5"}

        def version_getter(name):
            if name not in versions:
                raise metadata.PackageNotFoundError(name)
            return versions[name]

        report = PythonEnvironmentChecker(path, version_getter).check()

        self.assertFalse(report.is_healthy)
        self.assertEqual(
            ("wrong>=2", "missing==3"), report.requirements_to_install
        )
        self.assertEqual("missing", report.missing[0].requirement.name)
        self.assertEqual("wrong", report.outdated[0].requirement.name)
        self.assertEqual("1.5", report.outdated[0].installed_version)

    def test_update_plan_round_trip_and_pip_arguments(self):
        plan = self._plan()

        restored = UpdatePlan.from_dict(plan.to_dict())

        self.assertEqual(plan, restored)
        self.assertEqual(
            [
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--index-url",
                "https://mirror.example/simple",
                "demo==1",
            ],
            restored.pip_arguments,
        )

    def test_python_restart_uses_pythonw(self):
        python = Path.cwd() / ".venv" / "Scripts" / "python.exe"

        executable = gui_executable(python)

        self.assertEqual("pythonw.exe", executable.name.lower())

    def test_updater_uses_console_python_when_app_runs_with_pythonw(self):
        pythonw = Path.cwd() / ".venv" / "Scripts" / "pythonw.exe"

        executable = console_executable(pythonw)

        self.assertEqual("python.exe", executable.name.lower())

    @patch.dict(
        os.environ,
        {
            "PYAPPIFY_VERSION": "1.0",
            "PYAPPIFY_APP_PROFILE": "China",
            "PYAPPIFY_APP_VERSION": "2.0",
            "PYAPPIFY_APP_JSON_PATH": "app.json",
            "PYAPPIFY_EXECUTABLE": "launcher.exe",
        },
        clear=True,
    )
    def test_capture_restart_environment_includes_all_pyappify_values(self):
        captured = dict(capture_restart_environment())

        self.assertEqual("app.json", captured["PYAPPIFY_APP_JSON_PATH"])
        self.assertEqual("2.0", captured["PYAPPIFY_APP_VERSION"])
        self.assertEqual("launcher.exe", captured["PYAPPIFY_EXECUTABLE"])
        self.assertEqual(set(RESTART_ENVIRONMENT_NAMES), set(captured))

    @patch("src.environment.update.subprocess.Popen")
    @patch("src.environment.update.UpdatePlan.save", autospec=True)
    @patch(
        "src.environment.update.build_restart_command",
        return_value=("python.exe", "main.py"),
    )
    @patch(
        "src.environment.update.find_python_executable",
        return_value=Path("python.exe"),
    )
    @patch(
        "src.environment.update.python_process_chain",
        return_value=(100, 50),
    )
    @patch(
        "src.environment.update.capture_restart_environment",
        return_value=(("PYAPPIFY_VERSION", "1.2.3"),),
    )
    def test_launcher_saves_one_versioned_plan_and_starts_updater(
        self, _environment, _chain, _python, _restart, save, popen
    ):
        launcher = EnvironmentUpdateLauncher(Path.cwd())

        launcher.launch(("demo==1",), "https://mirror.example/simple")

        plan = save.call_args.args[0]
        self.assertEqual(PLAN_VERSION, plan.version)
        self.assertEqual((100, 50), plan.process_ids)
        self.assertEqual(("demo==1",), plan.requirements)
        self.assertEqual((("PYAPPIFY_VERSION", "1.2.3"),), plan.restart_environment)
        popen.assert_called_once()
        self.assertTrue(
            popen.call_args.kwargs["creationflags"] & subprocess.CREATE_NEW_CONSOLE
        )

    @patch("pathlib.Path.unlink")
    @patch("src.environment.updater.restart_application")
    @patch("src.environment.updater.execute_update", return_value=0)
    @patch("src.environment.updater.wait_for_process_exit")
    @patch("src.environment.updater.UpdatePlan.load")
    def test_successful_updater_waits_deletes_plan_and_restarts(
        self, load, wait, _execute, restart, unlink
    ):
        plan = self._plan()
        load.return_value = plan

        result = updater.main(["plan.json"])

        self.assertEqual(0, result)
        self.assertEqual([call(100), call(50)], wait.call_args_list)
        unlink.assert_called_once_with(missing_ok=True)
        restart.assert_called_once_with(plan)

    @patch("src.environment.updater.wait_for_keypress")
    @patch("src.environment.updater.restart_application")
    @patch("src.environment.updater.execute_update", return_value=1)
    @patch("src.environment.updater.wait_for_process_exit")
    @patch("src.environment.updater.UpdatePlan.load")
    def test_failed_updater_waits_for_keypress_without_restarting(
        self, load, _wait, _execute, restart, wait_for_keypress
    ):
        load.return_value = self._plan()

        result = updater.main(["plan.json"])

        self.assertEqual(1, result)
        wait_for_keypress.assert_called_once_with()
        restart.assert_not_called()

    @patch("builtins.print")
    @patch("pathlib.Path.open")
    @patch("pathlib.Path.mkdir")
    @patch("src.environment.updater.subprocess.Popen")
    def test_execute_update_streams_pip_output_to_log(
        self, popen, _mkdir, open_file, _print
    ):
        process = MagicMock()
        process.stdout = ["downloaded\n"]
        process.wait.return_value = 0
        popen.return_value = process
        log_file = MagicMock()
        open_file.return_value.__enter__.return_value = log_file

        result = updater.execute_update(self._plan())

        self.assertEqual(0, result)
        self.assertIn(call("downloaded\n"), log_file.write.call_args_list)

    @patch("src.environment.updater.subprocess.Popen")
    def test_restart_uses_planned_pythonw_command(self, popen):
        plan = self._plan()
        pythonw = Path.cwd() / ".venv" / "Scripts" / "pythonw.exe"
        plan = replace(plan, restart_command=(str(pythonw), "main.py"))

        updater.restart_application(plan)

        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual("pythonw.exe", Path(command[0]).name.lower())
        self.assertEqual(plan.working_directory, options["cwd"])
        self.assertEqual("1.2.3", options["env"]["PYAPPIFY_VERSION"])
        self.assertNotIn("PYAPPIFY_APP_PROFILE", options["env"])
        self.assertEqual({"cwd", "env"}, set(options))

    @staticmethod
    def _plan():
        return UpdatePlan(
            version=PLAN_VERSION,
            process_ids=(100, 50),
            python_executable="python.exe",
            requirements=("demo==1",),
            index_url="https://mirror.example/simple",
            restart_command=("python.exe", "main.py"),
            restart_environment=tuple(
                (
                    name,
                    {
                        "PYAPPIFY_VERSION": "1.2.3",
                        "PYAPPIFY_APP_JSON_PATH": "app.json",
                        "PYAPPIFY_EXECUTABLE": "launcher.exe",
                    }.get(name),
                )
                for name in RESTART_ENVIRONMENT_NAMES
            ),
            working_directory="working",
            log_path="logs/update.log",
        )


if __name__ == "__main__":
    unittest.main()
