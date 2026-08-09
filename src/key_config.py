from ok import ConfigOption
from qfluentwidgets import FluentIcon


KEY_SETTINGS = ConfigOption(
    name="Key Settings",
    default={
        "Auto Battle": "h",
        "Season Hub": "o",
        "Exit Dungeon": "p",
        "Float": "q",
        "Invert Gliding Controls": False,
        "Phantom Dash": "e",
        "Toggle Walk/Run": "rctrl",
        "Switch Pole": "m",
    },
    icon=FluentIcon.COMMAND_PROMPT,
)
