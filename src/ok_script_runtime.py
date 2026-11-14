"""Load the installed framework when a local development link shadows it."""

import sys
import logging
from importlib import metadata
from pathlib import Path


def prefer_installed_ok_script():
    project_root = Path(__file__).resolve().parent.parent
    if (project_root / "ok").is_symlink():
        installed_root = metadata.distribution("ok-script").locate_file("")
        sys.path.insert(0, str(installed_root))


def configure_pyappify_runtime():
    """Adapt framework logging and Git proxy settings for PyAppify."""
    import pyappify
    from dulwich.client import get_transport_and_path
    from dulwich.config import ConfigFile, StackedConfig
    from pyappify import standalone

    # ok-script assigns its single-argument Logger during OK initialization.
    # PyAppify's standalone updater calls info(message, *args).
    pyappify.logger = logging.getLogger("ok.pyappify")

    original_remote_client = standalone._remote_client

    def remote_client(repo):
        config = repo.get_config_stack()
        try:
            proxy = config.get((b"http",), b"proxy")
        except KeyError:
            return original_remote_client(repo)
        if not proxy or b"://" in proxy:
            return original_remote_client(repo)

        # Git accepts host:port, while Dulwich's urllib3 transport needs a URL.
        override = ConfigFile()
        override.set((b"http",), b"proxy", b"http://" + proxy)
        return get_transport_and_path(
            standalone.remote_url(repo),
            config=StackedConfig([override, *config.backends]),
        )

    standalone._remote_client = remote_client
