"""Execute a saved environment update plan after the application exits."""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

from src.environment.update import UpdatePlan


SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF


def wait_for_process_exit(process_id: int) -> None:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, process_id)
    if handle:
        try:
            kernel32.WaitForSingleObject(handle, INFINITE)
        finally:
            kernel32.CloseHandle(handle)


def execute_update(plan: UpdatePlan) -> int:
    log_path = Path(plan.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print("正在更新运行环境，请勿关闭此窗口……", flush=True)

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\nStarting environment update\n")
        log_file.flush()
        process = subprocess.Popen(
            [plan.python_executable, *plan.pip_arguments],
            cwd=plan.working_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if process.stdout is not None:
            for line in process.stdout:
                print(line, end="", flush=True)
                log_file.write(line)
        exit_code = process.wait()
        log_file.write(f"Environment update finished with exit code {exit_code}\n")
    return exit_code


def restart_application(plan: UpdatePlan) -> None:
    environment = os.environ.copy()
    for name, value in plan.restart_environment:
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    subprocess.Popen(
        plan.restart_command,
        cwd=plan.working_directory,
        env=environment,
    )


def wait_for_keypress() -> None:
    import msvcrt

    print("按任意键关闭……", end="", flush=True)
    msvcrt.getwch()


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("更新计划参数无效。")
        wait_for_keypress()
        return 2

    plan_path = Path(argv[0]).resolve()
    try:
        plan = UpdatePlan.load(plan_path)
        for process_id in plan.process_ids:
            wait_for_process_exit(process_id)
        exit_code = execute_update(plan)
    except Exception as exc:
        print(f"\n更新程序发生错误：{exc}")
        wait_for_keypress()
        return 1

    if exit_code != 0:
        print(f"\n更新失败（错误码：{exit_code}）。")
        print(f"详细日志：{plan.log_path}")
        wait_for_keypress()
        return exit_code

    plan_path.unlink(missing_ok=True)
    restart_application(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
