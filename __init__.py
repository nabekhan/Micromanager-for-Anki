# zip -r Micromanager.ankiaddon * -x "*.DS_Store" -x "*__pycache__*" -x "meta.json" -x ".venv/*" -x ".git/*"
# __init__.py
from aqt import mw

# Notice we now import from .src
from .src.enforcer import lock_addon

# Bind the Anki Add-ons list 'Config' button to your custom UI
# We use __name__ here so Anki knows which add-on this button belongs to
mw.addonManager.setConfigAction(__name__, lock_addon.request_settings)