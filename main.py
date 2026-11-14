from src.ok_script_runtime import configure_pyappify_runtime, prefer_installed_ok_script

prefer_installed_ok_script()

import ok
from src.config import config
from src.gui.GroupedTasksPage import install_grouped_task_filter

if __name__ == '__main__':
    install_grouped_task_filter()
    config = config
    ok = ok.OK(config)
    configure_pyappify_runtime()
    ok.start()
