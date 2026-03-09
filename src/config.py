# src/config.py
import os
import json
from aqt import mw

ADDON_ID = __name__.split('.')[0]
ADDON_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ADDON_DIR, "config.json")

DEFAULT_CONFIG = {
    "is_locked": False,
    "saved_mode": "cards",
    "saved_target": 1,
    "saved_current": 0,
    "saved_password": "",
    "use_password": True,
    "lock_type": "none",
    "custom_password": "default"
}


def ensure_config_exists():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)


def load_config():
    ensure_config_exists()

    config = mw.addonManager.getConfig(ADDON_ID)
    if config is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    return config


def save_config(new_data):
    ensure_config_exists()

    config = load_config()
    config.update(new_data)

    # FORCE DISK WRITE: Bypass Anki's memory buffer to survive hard crashes
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    # Still update Anki's internal state just in case
    mw.addonManager.writeConfig(ADDON_ID, config)
    return config