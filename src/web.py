# web.py
def get_hud_css_rules():
    # We define our custom variables at the top, and let Anki's .nightMode class swap them!
    return """
    :root {
        --hud-accent: #2980b9;
        --hud-shadow: rgba(0,0,0,0.15);
        --hud-btn-bg: #e0e0e0;
        --hud-btn-fg: #555555;
        --hud-label: #7f8c8d;
    }

    .nightMode {
        --hud-accent: #3498db;
        --hud-shadow: rgba(0,0,0,0.5);
        --hud-btn-bg: #333333;
        --hud-btn-fg: #cccccc;
        --hud-label: #888888;
    }

    #force-hud-container {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 44px !important;
        background: var(--window-bg) !important;
        z-index: 2147483647 !important;
        box-shadow: 0 2px 8px var(--hud-shadow) !important;
        border-bottom: 2px solid var(--border) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        opacity: 0;
        animation: slideInForceTop 0.4s cubic-bezier(0.19, 1, 0.22, 1) forwards !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    #force-hud-progress {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        height: 100% !important;
        background: var(--hud-accent) !important;
        opacity: 0.25 !important;
        z-index: 1 !important;
        transition: width 0.3s ease !important;
    }
    #force-hud-content {
        position: relative !important;
        z-index: 2 !important;
        width: 100% !important;
        height: 100% !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        padding: 0 20px !important;
        box-sizing: border-box !important;
    }
    .hud-section { display: flex !important; flex-direction: row !important; align-items: baseline !important; gap: 8px !important; border: none !important; }
    .hud-val { font-size: 18px !important; font-weight: 800 !important; color: var(--text-fg) !important; line-height: 1 !important; margin: 0 !important; padding: 0 !important; }
    .hud-label { font-size: 11px !important; text-transform: uppercase !important; letter-spacing: 1px !important; color: var(--hud-label) !important; font-weight: 700 !important; border: none !important; }

    .hud-btn { 
        width: 28px !important; 
        height: 28px !important; 
        border-radius: 4px !important; 
        font-size: 16px !important; 
        cursor: pointer !important; 
        display: flex !important; 
        align-items: center !important; 
        justify-content: center !important; 
        transition: transform 0.1s ease !important; 
        border: none !important; 
        margin: 0 !important; 
    }
    .hud-btn:hover { transform: scale(1.05); } 
    .hud-btn:active { transform: scale(0.95); }

    #hud-conf { background: var(--hud-btn-bg) !important; color: var(--hud-btn-fg) !important; } 
    #hud-conf:hover { background: var(--hud-accent) !important; color: white !important; }

    #hud-stop { background: rgba(231, 76, 60, 0.15) !important; color: #e74c3c !important; } 
    #hud-stop:hover { background: #e74c3c !important; color: white !important; }

    @keyframes slideInForceTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    """

HUD_HTML_TEMPLATE = """
<div id="force-hud-container">
    <div id="force-hud-progress" style="width: {PCT}%;"></div>
    <div id="force-hud-content">
        <div class="hud-section" id="sec-display">
            <div class="hud-val" id="val-display">{VAL}</div>
            <div class="hud-label" id="lbl-display">{LBL}</div>
        </div>
        <div style="display:flex; gap:12px; align-items:center;">
            <div id="hud-conf" class="hud-btn" title="Settings" onclick="pycmd('force_config')">≡</div>
            <div id="hud-stop" class="hud-btn" title="Stop" onclick="pycmd('force_unlock')">X</div>
        </div>
    </div>
</div>
"""
