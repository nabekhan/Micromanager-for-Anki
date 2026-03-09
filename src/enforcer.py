# enforcer.py
import time
from aqt import mw
from aqt.qt import *
from aqt import gui_hooks
from aqt.utils import tooltip, showWarning
from aqt.reviewer import Reviewer

from .config import load_config, save_config
from .web import get_hud_css_rules, HUD_HTML_TEMPLATE, HUD_JS
from . import ui


class AnkiLock:
    def __init__(self):
        self.active = False
        self.mode = "cards"
        self.target_val = 0
        self.current_val = 0
        self.initial_minutes = 0
        self.password = ""
        conf = load_config()
        self.lock_type = conf.get("lock_type", "none")
        self.custom_password = conf.get("custom_password", "default")
        if not self.custom_password:
            self.custom_password = "default"

        self._needs_save = False

        self.locked_deck_id = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_tick)

        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.commit_persistence)
        self.save_timer.start(10000)

        self.original_close_event = mw.closeEvent
        mw.closeEvent = self.on_close_attempt

        self.setup_menu()

        gui_hooks.webview_will_set_content.append(self.inject_hud)
        gui_hooks.webview_did_receive_js_message.append(self.on_js_message)
        gui_hooks.reviewer_did_answer_card.append(self.on_answer)
        gui_hooks.state_did_undo.append(self.on_undo)

        gui_hooks.add_cards_did_init.append(self.on_secondary_window)
        gui_hooks.browser_will_show.append(self.on_secondary_window)

        QTimer.singleShot(1000, self.check_persistence)


    def on_secondary_window(self, window):
        if self.active:
            flags = window.windowFlags()
            if not (flags & Qt.WindowType.WindowStaysOnTopHint):
                window.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
                window.show()
                window.raise_()
                window.activateWindow()

    def on_close_attempt(self, event):
        if self.active:
            event.ignore()
            tooltip("Micromanager: Anki is Locked!")
            mw.showMaximized()
            mw.activateWindow()
        else:
            self.original_close_event(event)

    def check_persistence(self):
        conf = load_config()
        if conf.get("is_locked", False):
            self.mode = conf.get("saved_mode", "cards")
            self.target_val = conf.get("saved_target", 10)
            self.current_val = conf.get("saved_current", 0)
            self.password = conf.get("saved_password", "")
            self.lock_type = conf.get("lock_type", "none")
            self.locked_deck_id = conf.get("locked_deck_id", None)
            self.active = True
            mw.form.actionAdd_ons.setEnabled(False)
            self.timer.start(200)
            tooltip("Micromanager: Session Restored (Persistence Active)")
            mw.showMaximized()

    def update_persistence(self):
        self._needs_save = True

    def commit_persistence(self):
        if self._needs_save and self.active:
            save_config({
                "is_locked": True,
                "saved_mode": self.mode,
                "saved_target": self.target_val,
                "saved_current": self.current_val,
                "saved_password": self.password,
                "lock_type": getattr(self, "lock_type", "none"),
                "locked_deck_id": self.locked_deck_id
            })
            self._needs_save = False

    def clear_persistence(self):
        self._needs_save = False
        save_config({"is_locked": False})

    # NEW: The Gatekeeper function. Prevents opening settings if on the home screen.
    def request_settings(self):
        if not self.active and mw.state not in ["overview", "review"]:
            showWarning("Please select and enter a deck first before activating Micromanager.")
            return
        ui.open_settings(self, is_update=self.active)

    def setup_menu(self):
        action = QAction("Micromanager", mw)
        action.setShortcut(QKeySequence("Ctrl+Shift+M"))

        # Route the menu button through the gatekeeper too
        action.triggered.connect(self.request_settings)
        mw.form.menuTools.addAction(action)

    def start_lock(self, dialog, is_update=False):
        if not is_update:
            if self.rb_lock_custom.isChecked():
                temp_pass = self.txt_pass.text().strip()

                # Check for empty password BEFORE overwriting anything
                if not temp_pass:
                    showWarning("Password cannot be empty!")
                    return

                self.lock_type = "custom"
                self.password = temp_pass
                self.custom_password = temp_pass

            elif self.rb_lock_blind.isChecked():
                self.lock_type = "blind"
                self.password = ""
            elif self.rb_lock_random.isChecked():
                self.lock_type = "random"
                import string, random
                chars = string.ascii_letters + string.digits
                self.password = ''.join(random.choices(chars, k=200))
            else:
                self.lock_type = "none"
                self.password = ""

            save_config({
                "lock_type": self.lock_type,
                "custom_password": getattr(self, "custom_password", "")
            })

            self.locked_deck_id = None

        if is_update:
            dialog.accept()
            tooltip("Micromanager: Resuming Session...")
            self.timer.start(200)
            return

        val = self.spin_val.value()

        if self.rb_time.isChecked():
            self.mode = "time"
            self.initial_minutes = val
            self.target_val = val * 60
            self.current_val = self.target_val
        elif self.rb_correct.isChecked():
            self.mode = "correct"
            self.target_val = val
            self.current_val = 0
            self.initial_minutes = 5
        elif getattr(self, 'rb_finish', None) and self.rb_finish.isChecked():
            self.mode = "finish_reviews"
            counts = mw.col.sched.counts()
            # Anki counts are returned as (new, learning, review)
            self.target_val = counts[2] if counts and len(counts) >= 3 else 0

            if self.target_val == 0:
                showWarning("No reviews are currently due in this deck! Lock aborted.")
                return

            self.current_val = 0  # Unused for this mode, but keeps state clean
            self.initial_minutes = 5
        else:
            self.mode = "cards"
            self.target_val = val
            self.current_val = 0
            self.initial_minutes = 5

        self.active = True
        mw.form.actionAdd_ons.setEnabled(False)

        # We now guarantee they are inside a deck, so grab the ID instantly
        self.locked_deck_id = mw.col.decks.get_current_id()

        self.update_persistence()
        self.commit_persistence()

        dialog.accept()
        QApplication.beep()
        self.timer.start(200)

        # Automatically push them into the flashcards if they are on the deck overview screen
        if mw.state == "overview":
            mw.moveToState("review")
        else:
            mw.reset()

        QTimer.singleShot(300, self.update_webview)

    def stop_lock(self, success=False):
        self.active = False
        self.locked_deck_id = None
        self.timer.stop()
        self.clear_persistence()

        # Re-enable the Add-ons menu if locked
        if hasattr(mw.form, 'actionAdd_ons'):
            mw.form.actionAdd_ons.setEnabled(True)

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, (QMainWindow, QDialog)):
                flags = widget.windowFlags()
                if flags & Qt.WindowType.WindowStaysOnTopHint:
                    widget.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
                    if widget.isVisible():
                        widget.show()

        mw.showMaximized()

        # BULLETPROOF HUD REMOVAL
        # Finds any element with the HUD ID and removes it directly from the DOM
        kill_js = """
            var huds = document.querySelectorAll('#force-hud-container');
            huds.forEach(function(hud) { hud.remove(); });
            if (typeof removeForceHud === 'function') removeForceHud();
        """

        if mw.reviewer.web:
            mw.reviewer.web.eval(kill_js)

        # Also clean the main webview just in case Anki transitioned screens too fast
        if mw.web:
            mw.web.eval(kill_js)

        if success:
            QApplication.beep()
            tooltip("Micromanager: Goal Reached! Session Complete.", period=3000)
        else:
            tooltip("Micromanager: Lock Stopped")

    def get_current_display_values(self):
        text_display = "0"
        label_display = "LOCKED"
        pct = 0

        if self.mode == "time":
            mins = int(self.current_val / 60)
            secs = self.current_val % 60
            text_display = f"{mins:02d}:{secs:02d}"
            label_display = "TIMER"
            pct = 100 if self.target_val == 0 else ((self.target_val - self.current_val) / self.target_val) * 100

        elif self.mode == "correct":
            remaining = self.target_val - self.current_val
            text_display = str(max(0, remaining))
            label_display = "CORRECT LEFT"
            pct = 100 if self.target_val == 0 else (self.current_val / self.target_val) * 100

        elif self.mode == "finish_reviews":
            counts = mw.col.sched.counts()
            remaining = counts[2] if counts and len(counts) >= 3 else 0
            text_display = str(remaining)
            label_display = "REVIEWS LEFT"
            pct = 100 if self.target_val == 0 else ((self.target_val - remaining) / self.target_val) * 100

        else:
            remaining = self.target_val - self.current_val
            text_display = str(max(0, remaining))
            label_display = "CARDS LEFT"
            pct = 100 if self.target_val == 0 else (self.current_val / self.target_val) * 100

        return text_display, label_display, max(0, min(100, pct))

    def inject_hud(self, content, context):
        if not isinstance(context, Reviewer) or not self.active: return

        val_txt, lbl_txt, pct = self.get_current_display_values()
        style_block = "<style>" + get_hud_css_rules() + "</style>"
        content.head += style_block

        html_str = HUD_HTML_TEMPLATE.replace("{VAL}", val_txt).replace("{LBL}", lbl_txt).replace("{PCT}", str(pct))
        content.body += html_str

    def on_tick(self):
        if not self.active: return

        # === 1. OS FIGHTING: Anti-Minimize ===
        if mw.isMinimized():
            mw.showMaximized()
            mw.activateWindow()

        # === 2. DECK LOCK LOGIC ===
        if self.locked_deck_id is None and mw.state in ["overview", "review"]:
            self.locked_deck_id = mw.col.decks.get_current_id()
            self.update_persistence()

        if self.locked_deck_id is not None and mw.state in ["overview", "review"]:
            if mw.col.decks.get_current_id() != self.locked_deck_id:
                mw.moveToState("deckBrowser")
                tooltip(f"Micromanager: You are locked to your previous deck until your goal is met! ({self.locked_deck_id})", period=3000)

        # Check if the daily reviews have been completely cleared
        if self.mode == "finish_reviews" and mw.state == "review":
            counts = mw.col.sched.counts()
            remaining_reviews = counts[2] if counts and len(counts) >= 3 else 0
            if remaining_reviews == 0:
                self.stop_lock(success=True)
                return

        # === 3. TIMER LOGIC ===
        if self.mode == "time":
            if not hasattr(self, '_tick_counter'): self._tick_counter = 0
            self._tick_counter += 1
            if self._tick_counter >= 5:
                self._tick_counter = 0
                self.current_val -= 1

                if self.current_val % 60 == 0:
                    self.update_persistence()

                if self.current_val <= 0:
                    self.stop_lock(success=True)
                    return
                self.update_webview()

        # === 4. OS FIGHTING: Window TopMost & Focus Yanking ===
        if not hasattr(self, '_window_tick_counter'): self._window_tick_counter = 0
        self._window_tick_counter += 1

        # Throttled to run every ~3 seconds (15 ticks) to avoid freezing macOS
        if self._window_tick_counter >= 15:
            self._window_tick_counter = 0
            for widget in QApplication.topLevelWidgets():
                if not widget.isVisible():
                    continue
                if isinstance(widget, (QMainWindow, QDialog)):
                    flags = widget.windowFlags()
                    if not (flags & Qt.WindowType.WindowStaysOnTopHint):
                        widget.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
                        widget.show()

        # Instant focus yanking if you click away
        active = QApplication.activeWindow()
        if active is None:
            mw.activateWindow()
            mw.raise_()

    def on_answer(self, reviewer, card, ease):
        if not self.active: return

        if self.mode == "cards":
            self.current_val += 1
            self.update_persistence()
            if self.current_val >= self.target_val:
                self.stop_lock(success=True)
                return
        elif self.mode == "correct":
            if ease > 1:
                self.current_val += 1
                self.update_persistence()
                if self.current_val >= self.target_val:
                    self.stop_lock(success=True)
                    return

        self.update_webview()

    def on_undo(self, *args):
        if not self.active: return
        if self.current_val > 0:
            self.current_val -= 1
        self.update_webview()
        self.update_persistence()

    def update_webview(self):
        if not self.active: return
        if mw.state != "review": return
        if not getattr(mw.reviewer, "card", None): return

        text_display, label_display, pct = self.get_current_display_values()
        safe_html = HUD_HTML_TEMPLATE.replace("{VAL}", text_display).replace("{LBL}", label_display).replace("{PCT}",
                                                                                                             str(pct))
        safe_html = safe_html.replace('\n', ' ').replace("'", "\\'")
        raw_css = get_hud_css_rules().replace('\n', ' ').replace("'", "\\'")

        js_cmd = f"""
        (function(){{
            var hud = document.getElementById('force-hud-container');
            if (!hud) {{
                var s = document.createElement('style');
                s.textContent = '{raw_css}';
                document.head.appendChild(s);
                var d = document.createElement('div');
                d.innerHTML = '{safe_html}';
                document.body.appendChild(d);
                {HUD_JS}
            }}
            if(window.updateForceHud) {{
                window.updateForceHud('{text_display}', '{label_display}', {pct});
            }}
        }})();
        """
        mw.reviewer.web.eval(js_cmd)

    def on_js_message(self, handled, message, context):
        if message == "force_config":
            ui.open_settings(self, is_update=True)
            return (True, None)

        if message == "force_unlock":
            self.timer.stop()

            if self.lock_type == "none":
                reply = QMessageBox.question(
                    mw, 'Unlock',
                    'Are you sure you want to abort your session early?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.stop_lock(success=False)
                else:
                    self.timer.start(200)
            else:
                unlocked = ui.open_unlock_dialog(self.lock_type, self.password)
                if unlocked:
                    self.stop_lock(success=False)
                else:
                    self.timer.start(200)

            return (True, None)

        return handled


lock_addon = AnkiLock()