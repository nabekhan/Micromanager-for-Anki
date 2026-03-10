# enforcer.py
from aqt import mw
from aqt.qt import *
from aqt import gui_hooks
from aqt.utils import tooltip
from aqt.reviewer import Reviewer
import string, random
from .config import load_config, save_config
from .web import get_hud_css_rules, HUD_HTML_TEMPLATE
from . import ui


class AnkiLock:
    def __init__(self):
        self.active = False

        # FIX: Load history immediately so settings persist between unlocked sessions
        conf = load_config()
        self.mode = conf.get("saved_mode", "cards")
        self.target_val = conf.get("saved_target", 0)
        self.current_val = 0

        self.initial_minutes = 0
        if self.mode == "time" and self.target_val > 0:
            self.initial_minutes = self.target_val // 60

        self.password = ""
        self.lock_type = conf.get("lock_type", "none")
        self.custom_password = conf.get("custom_password") or "default"

        self._needs_save = False
        self._current_card_is_new = False

        self.locked_deck_id = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_tick)

        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.commit_persistence)
        self.save_timer.start(10000)

        self.original_close_event = mw.closeEvent
        mw.closeEvent = self.on_close_attempt
        self._window_tick_counter = 0
        self._tick_counter = 0

        self.setup_menu()

        gui_hooks.webview_will_set_content.append(self.inject_hud)
        gui_hooks.webview_did_receive_js_message.append(self.on_js_message)
        gui_hooks.reviewer_did_answer_card.append(self.on_answer)
        gui_hooks.state_did_undo.append(self.on_undo)
        gui_hooks.reviewer_did_show_question.append(self.on_question_shown)
        gui_hooks.reviewer_did_show_answer.append(self.update_webview)

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

            # --- FIX: Prevent Percentage Glitch After Syncing ---
            # If the user's due count grew while Anki was closed, update the
            # target size so the math doesn't try to divide by a smaller number.
            try:
                counts = mw.col.sched.counts()
                if self.mode == "finish_reviews":
                    remaining = counts[2] if counts and len(counts) >= 3 else 0
                    if remaining > self.target_val:
                        self.target_val = remaining
                elif self.mode == "finish_deck":
                    remaining = (counts[0] + counts[2]) if counts else 0
                    if remaining > self.target_val:
                        self.target_val = remaining
            except AttributeError:
                pass
                # ---------------------------------------------------

            self.save_timer.start(10000)

            # Restore initial minutes so the settings UI displays correctly
            if self.mode == "time":
                self.initial_minutes = self.target_val // 60

            self.active = True
            mw.form.actionAdd_ons.setEnabled(False)
            mw.form.actionSwitchProfile.setEnabled(False)
            self.timer.start(200)
            tooltip("Micromanager: Session Restored")
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

    def request_settings(self):
        if not self.active and mw.state not in ["overview", "review"]:
            tooltip("Please select a deck before activating Micromanager")
            return
        ui.open_settings(self, is_update=self.active)

    def setup_menu(self):
        action = QAction("Micromanager", mw)
        action.setShortcut(QKeySequence("Ctrl+Shift+M"))

        # Route the menu button through the gatekeeper too
        action.triggered.connect(self.request_settings)
        mw.form.menuTools.addAction(action)

    def start_lock(self, settings):
        # FIX: We now unpack a safe dictionary passed from ui.py
        self.lock_type = settings.get('lock_type', 'none')

        if self.lock_type == "custom":
            self.password = settings.get('password', '')
            self.custom_password = self.password
        elif self.lock_type == "random":
            chars = string.ascii_letters + string.digits
            self.password = ''.join(random.choices(chars, k=200))
        else:
            self.password = ""

        save_config({
            "lock_type": self.lock_type,
            "custom_password": getattr(self, "custom_password", "")
        })

        self.locked_deck_id = None
        self.mode = settings.get('mode', 'cards')
        val = settings.get('val', 5)

        if self.mode == "time":
            self.initial_minutes = val
            self.target_val = val * 60
            self.current_val = self.target_val
        elif self.mode == "correct":
            self.target_val = val
            self.current_val = 0
            self.initial_minutes = 5
        elif self.mode == "new_cards":
            self.target_val = val
            self.current_val = 0
            self.initial_minutes = 5
        elif self.mode == "finish_reviews":
            try:
                counts = mw.col.sched.counts()
                self.target_val = counts[2] if counts and len(counts) >= 3 else 0
            except AttributeError:
                self.target_val = 0
                tooltip("Error: Could not read Anki's scheduler. Goal aborted.")
                return False

            if self.target_val == 0:
                tooltip("No reviews are currently due in this deck! Lock aborted.")
                return False

            self.current_val = 0
            self.initial_minutes = 5
        elif self.mode == "finish_deck":
            try:
                counts = mw.col.sched.counts()
                # FIX: Set the initial goal using only New + Review
                self.target_val = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
            except AttributeError:
                self.target_val = 0
                tooltip("Error: Could not read Anki's scheduler. Goal aborted.")
                return False

            if self.target_val == 0:
                tooltip("No cards are currently due in this deck! Lock aborted.")
                return False

            self.current_val = 0
            self.initial_minutes = 5
        else:
            self.mode = "cards"
            self.target_val = val
            self.current_val = 0
            self.initial_minutes = 5

        self.active = True
        mw.form.actionAdd_ons.setEnabled(False)
        mw.form.actionSwitchProfile.setEnabled(False)
        self.save_timer.start(10000)

        self.locked_deck_id = mw.col.decks.get_current_id()

        self.update_persistence()
        self.commit_persistence()

        QApplication.beep()
        self.timer.start(200)

        # Automatically push them into the flashcards if they are on the deck overview screen
        if mw.state == "overview":
            mw.moveToState("review")
        else:
            mw.reset()

        QTimer.singleShot(300, self.update_webview)
        return True

    def stop_lock(self, success=False):
        self.active = False
        self.locked_deck_id = None
        self.timer.stop()
        self.save_timer.stop()
        self.clear_persistence()

        # Re-enable the Add-ons menu if locked
        if hasattr(mw.form, 'actionAdd_ons'):
            mw.form.actionAdd_ons.setEnabled(True)
            mw.form.actionSwitchProfile.setEnabled(True)

        flags = mw.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            mw.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            if mw.isVisible():
                mw.show()

        mw.show()

        # BULLETPROOF HUD REMOVAL
        # Finds any element with the HUD ID and removes it directly from the DOM
        kill_js = """
            var huds = document.querySelectorAll('#force-hud-container');
            huds.forEach(function(hud) { hud.remove(); });
            if (typeof removeForceHud === 'function') removeForceHud();
        """

        if mw.web:
            mw.web.eval(kill_js)

        if success:
            QApplication.beep()
            tooltip("Micromanager: Session Complete.", period=3000)
        else:
            tooltip("Micromanager: Stopped")

    def get_current_display_values(self):
        text_display = "0"
        label_display = "LOCKED"
        pct = 0.0

        # 1. TIME MODE (Bar shrinks from 100% -> 0%)
        if self.mode == "time":
            mins = int(self.current_val / 60)
            secs = self.current_val % 60
            text_display = f"{mins:02d}:{secs:02d}"
            label_display = "TIMER"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 2. CORRECT ANSWERS (Bar grows from 0% -> 100%)
        elif self.mode == "correct":
            remaining = max(0, self.target_val - self.current_val)
            text_display = str(remaining)
            label_display = "CORRECT LEFT"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 3. TOTAL REVIEWS / CARDS (Bar grows from 0% -> 100%)
        elif self.mode == "cards":
            remaining = max(0, self.target_val - self.current_val)
            text_display = str(remaining)
            label_display = "CARDS LEFT"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 4. NEW CARDS ONLY (Bar grows from 0% -> 100%)
        elif self.mode == "new_cards":
            remaining = max(0, self.target_val - self.current_val)
            text_display = str(remaining)
            label_display = "NEW LEFT"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 5. REVIEWS DUE (Bar grows from 0% -> 100%)
        elif self.mode == "finish_reviews":
            counts = mw.col.sched.counts() if mw.col else None
            remaining = counts[2] if counts and len(counts) >= 3 else 0
            text_display = str(remaining)
            label_display = "REVIEWS LEFT"

            # If Anki dynamically adds reviews to the queue, push the goalpost back
            if remaining > self.target_val:
                self.target_val = remaining

            if self.target_val > 0:
                completed = self.target_val - remaining
                pct = (completed / self.target_val) * 100

        # 6. COMPLETE DECK (Bar grows from 0% -> 100%)
        elif self.mode == "finish_deck":
            counts = mw.col.sched.counts() if mw.col else None
            # FIX: Only count New (counts[0]) and Review (counts[2]). Ignore Learning!
            remaining = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
            text_display = str(remaining)
            label_display = "TOTAL LEFT"

            # If Anki dynamically adds to the queue, push the goalpost
            if remaining > self.target_val:
                self.target_val = remaining

            if self.target_val > 0:
                completed = self.target_val - remaining
                pct = (completed / self.target_val) * 100

        # Guarantee the CSS percentage never exceeds bounds
        return text_display, label_display, max(0.0, min(100.0, pct))

    def inject_hud(self, content, context):
        if not isinstance(context, Reviewer) or not self.active: return

        val_txt, lbl_txt, pct = self.get_current_display_values()
        style_block = "<style>" + get_hud_css_rules() + "</style>"
        content.head += style_block

        html_str = HUD_HTML_TEMPLATE.replace("{VAL}", val_txt).replace("{LBL}", lbl_txt).replace("{PCT}", str(pct))
        content.body += html_str

    def on_tick(self):
        if not self.active: return

        # Check for open dialogs right away
        modal = QApplication.activeModalWidget()

        # === OS FIGHTING: Intelligent Focus & Anti-Minimize ===
        # Get whatever window the user is currently interacting with
        current_active = QApplication.activeWindow()
        modal = QApplication.activeModalWidget()

        # 1. If Anki is minimized, bring the main window back up
        if mw.isMinimized():
            mw.showMaximized()
            if modal:
                modal.raise_()
                modal.activateWindow()
            elif current_active:
                current_active.raise_()
                current_active.activateWindow()
            else:
                mw.activateWindow()

        # 2. Re-assert TopMost status gently (throttled)
        self._window_tick_counter += 1

        if self._window_tick_counter >= 15:
            self._window_tick_counter = 0

            # CRITICAL FIX: DO NOT alter window flags if a modal dialog is open.
            # Altering flags breaks the .exec() event loop of QDialogs.
            if not modal:
                # Only enforce TopMost on the Main Window (mw).
                # Avoid dynamically applying it to random sub-windows/dropdowns.
                if mw.isVisible():
                    flags = mw.windowFlags()
                    if not (flags & Qt.WindowType.WindowStaysOnTopHint):
                        mw.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
                        mw.show()

        # 3. Focus Yanking: If Anki loses focus entirely (user alt-tabs)
        if current_active is None:
            if modal:
                modal.activateWindow()
                modal.raise_()
            else:
                top_widget = QApplication.topLevelAt(QCursor.pos()) or mw
                top_widget.activateWindow()
                top_widget.raise_()

        # === 2. DECK LOCK LOGIC ===
        if self.locked_deck_id is None and mw.state in ["overview", "review"]:
            self.locked_deck_id = mw.col.decks.get_current_id()
            self.update_persistence()

        if self.locked_deck_id is not None and mw.state in ["overview", "review"]:
            if mw.col.decks.get_current_id() != self.locked_deck_id:
                mw.moveToState("deckBrowser")
                tooltip(
                    f"Micromanager: You are locked to your selected deck until your goal is met! (Deck {mw.col.decks.name(self.locked_deck_id)})",
                    period=3000)

        # Check if the daily reviews have been completely cleared
        if self.mode == "finish_reviews" and mw.state == "review":
            counts = mw.col.sched.counts()
            remaining_reviews = counts[2] if counts and len(counts) >= 3 else 0
            if remaining_reviews == 0:
                self.stop_lock(success=True)
                return

            # Check if the entire deck is cleared (Inside both on_tick AND on_question_shown)
        elif self.mode == "finish_deck":
            try:
                counts = mw.col.sched.counts()
                # FIX: Only check if New and Review are zero
                remaining_total = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
                if remaining_total <= 0:
                    self.stop_lock(success=True)
                    return
            except AttributeError:
                pass

        # === 3. TIMER LOGIC ===
        if self.mode == "time":
            self._tick_counter += 1
            if self._tick_counter >= 5:
                self._tick_counter = 0
                self.current_val -= 1

                # Update persistence every single second.
                # The save_timer will automatically batch this to the disk every 10 seconds.
                self.update_persistence()

                if self.current_val <= 0:
                    self.stop_lock(success=True)
                    return
                self.update_webview()

    def on_question_shown(self, card):
        if not self.active: return

        # Track if the current card is new (type 0) for the new_cards goal
        self._current_card_is_new = (card.type == 0)

        # Edge Case: The user suspended/buried a card, which alters due counts
        # without triggering on_answer. We check if they won the "finish_reviews" goal here.
        if self.mode == "finish_reviews":
            try:
                counts = mw.col.sched.counts()
                remaining_reviews = counts[2] if counts and len(counts) >= 3 else 0
                if remaining_reviews <= 0:
                    self.stop_lock(success=True)
                    return
            except AttributeError:
                pass

            # Check if the entire deck is cleared (Inside both on_tick AND on_question_shown)
        elif self.mode == "finish_deck":
            try:
                counts = mw.col.sched.counts()
                # FIX: Only check if New and Review are zero
                remaining_total = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
                if remaining_total <= 0:
                    self.stop_lock(success=True)
                    return
            except AttributeError:
                pass

        # Refresh the HUD on the new card
        self.update_webview()

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
        elif self.mode == "new_cards":
            if getattr(self, "_current_card_is_new", False):
                self.current_val += 1
                self.update_persistence()
                if self.current_val >= self.target_val:
                    self.stop_lock(success=True)
                    return

        self.update_webview()

    def on_undo(self, *args):
        return
        """
        if not self.active: return
        if self.mode == "cards" and self.current_val > 0:
            self.current_val -= 1

        self.update_webview()
        self.update_persistence()
        """

    def update_webview(self, *args, **kwargs):
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

            // If the HUD is missing, rebuild it from scratch
            if (!hud) {{
                var s = document.createElement('style');
                s.textContent = '{raw_css}';
                document.head.appendChild(s);

                var d = document.createElement('div');
                d.innerHTML = '{safe_html}';
                document.body.appendChild(d.firstElementChild);

                // Re-fetch the newly created HUD
                hud = document.getElementById('force-hud-container');
            }}

            // Directly update the DOM to bypass window context resets
            if (hud) {{
                var valEl = document.getElementById('val-display');
                var lblEl = document.getElementById('lbl-display');
                var progEl = document.getElementById('force-hud-progress');

                if (valEl) valEl.innerText = '{text_display}';
                if (lblEl) lblEl.innerText = '{label_display}';
                if (progEl) progEl.style.width = '{pct}%';
            }}
        }})();
        """
        mw.web.eval(js_cmd)

    def on_js_message(self, handled, message, context):
        if message == "force_config":
            ui.open_settings(self, is_update=True)
            return (True, None)

        if message == "force_unlock":
            if self.lock_type == "none":
                # Use our custom UI to bypass the macOS native popup icon bug
                if ui.open_confirm_quit_dialog():
                    self.stop_lock(success=False)
            else:
                unlocked = ui.open_unlock_dialog(self.lock_type, self.password)
                if unlocked:
                    self.stop_lock(success=False)

            return (True, None)

        return handled


lock_addon = AnkiLock()