from ok import ConfigOption


PUSHDEER_SETTINGS = ConfigOption(
    name="PushDeer Settings",
    description="Configure PushDeer notifications for supported tasks",
    default={
        "Enable PushDeer": False,
        "PushDeer Server": "",
        "PushDeer ApiKey": "",
    },
    config_description={
        "PushDeer Server": "Put your server url here if not using official server",
        "PushDeer ApiKey": "Get from your PushDeer app",
    },
    icon="bell",
)
