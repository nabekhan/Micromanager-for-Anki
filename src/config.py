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
        # We also use atomic writing here just to be safe
        temp_path = CONFIG_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        os.replace(temp_path, CONFIG_PATH)


def load_config():
    ensure_config_exists()

    config = mw.addonManager.getConfig(ADDON_ID)
    if config is not None:
        return config

    # Safety Net: If the file got corrupted somehow, don't crash Anki.
    # Fall back to defaults and repair the file.
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        # The file is corrupted. Overwrite it with safe defaults.
        temp_path = CONFIG_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        os.replace(temp_path, CONFIG_PATH)
        return DEFAULT_CONFIG.copy()


def save_config(new_data):
    ensure_config_exists()

    config = load_config()
    config.update(new_data)

    # FORCE DISK WRITE (ATOMIC):
    # Write to a temporary file first, then seamlessly swap it over.
    # This survives hard crashes without corrupting the file.
    temp_path = CONFIG_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    # os.replace is an atomic operation on most operating systems
    os.replace(temp_path, CONFIG_PATH)

    # Still update Anki's internal state just in case
    mw.addonManager.writeConfig(ADDON_ID, config)
    return config