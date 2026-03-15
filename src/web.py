# web.py
def get_hud_css_rules():
    return """
    :root {
        /* Inherit directly from Anki's native theme */
        --hud-bg: var(--window-bg);
        --hud-border: var(--border);
        --hud-text: var(--text-fg);

        /* Add-on specific accent variables */
        --hud-accent: #007aff;
        --hud-label: #666666;
        --hud-btn-bg: rgba(0, 0, 0, 0.05); /* Transparent overlays instead of solid colors */
        --hud-btn-hover: rgba(0, 0, 0, 0.1);
    }

    .nightMode {
        --hud-accent: #0a84ff;
        --hud-label: #999999;
        --hud-btn-bg: rgba(255, 255, 255, 0.1); /* Transparent overlays for dark mode */
        --hud-btn-hover: rgba(255, 255, 255, 0.15);
    }

    #force-hud-container {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 48px !important;
        background: var(--hud-bg) !important;
        z-index: 2147483647 !important;
        border-top: 1px solid var(--hud-border) !important;
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
        opacity: 0.15 !important;
        z-index: 1 !important;
        transition: width 0.3s ease-out !important;
        border-top-right-radius: 4px !important;
        border-bottom-right-radius: 4px !important;
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

    .hud-section { 
        display: flex !important; 
        flex-direction: row !important; 
        align-items: baseline !important; 
        gap: 8px !important; 
    }

    .hud-val { 
        font-size: 18px !important; 
        font-weight: 800 !important; 
        color: var(--hud-text) !important; 
        font-variant-numeric: tabular-nums !important; 
    }

    .hud-label { 
        font-size: 11px !important; 
        text-transform: uppercase !important; 
        letter-spacing: 1.2px !important; 
        color: var(--hud-label) !important; 
        font-weight: 700 !important; 
    }

    .hud-btn { 
        width: 32px !important; 
        height: 32px !important; 
        border-radius: 6px !important; 
        font-size: 16px !important; 
        cursor: pointer !important; 
        display: flex !important; 
        align-items: center !important; 
        justify-content: center !important; 
        transition: all 0.15s ease !important; 
        border: none !important; 
        background: var(--hud-btn-bg) !important; 
        color: var(--hud-text) !important; 
    }

    .hud-btn:hover { 
        background: var(--hud-btn-hover) !important; 
    } 
    .hud-btn:active { transform: scale(0.95); }

    @keyframes slideInForceTop { 
        from { opacity: 0; transform: translateY(10px); } 
        to { opacity: 1; transform: translateY(0); } 
    }
    """


HUD_HTML_TEMPLATE = """
<div id="force-hud-container">
    <div id="force-hud-progress" style="width: {PCT}%;"></div>
    <div id="force-hud-content">
        <div class="hud-section" id="sec-display">
            <div class="hud-val" id="val-display">{VAL}</div>
            <div class="hud-label" id="lbl-display">{LBL}</div>
        </div>
        <div style="display:flex; gap:10px; align-items:center;">
            <div id="hud-conf" class="hud-btn" title="Settings" onclick="pycmd('force_config')">&#9881;</div>
            <div id="hud-stop" class="hud-btn" title="Stop" onclick="pycmd('force_unlock')">&times;</div>
        </div>
    </div>
</div>
"""