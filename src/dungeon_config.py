from ok import ConfigOption
from qfluentwidgets import FluentIcon


DUNGEON_SETTINGS = ConfigOption(
    name="Dungeon Settings",
    default={
        "Purchase Items": False,
        "Purchase Every N Clears": 8,
        "Purchase Item Index": 1,
        "Purchase Quota-limited Items First": False,
        "Reject Frost Mage Teammates": False,
        "Special Reward Pickup Limit": 5,
    },
    icon=FluentIcon.FLAG,
)
