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
        self._history = []
        # FIX: Load immediately so settings persist between unlocked sessions
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
            tooltip("Micromanager: Please select a deck before activating Micromanager")
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

        # --- GLOBAL SAFETY CHECK: PREVENT LOCKING ON EMPTY DECKS ---
        try:
            counts = mw.col.sched.counts()
            # sum(counts) totals up New, Learning, and Review cards
            total_due = sum(counts) if counts else 0
        except AttributeError:
            tooltip("Micromanager Error: Could not read Anki's scheduler. Goal aborted.")
            return False

        if total_due == 0:
            tooltip("Micromanager: No cards are currently due in this deck! Lock aborted.")
            return False
        # -----------------------------------------------------------

        if self.mode == "time":
            self.initial_minutes = val
            self.target_val = val * 60
            self.current_val = self.target_val

        elif self.mode == "correct":
            self.target_val = val
            self.current_val = 0
            self.initial_minutes = 5

        elif self.mode == "new_cards":
            available_new = counts[0] if counts and len(counts) >= 1 else 0
            if available_new == 0:
                tooltip("Micromanager: No new cards are currently available in this deck! Lock aborted.")
                return False
            self.target_val = min(val, available_new)
            self.current_val = 0
            self.initial_minutes = 5

        elif self.mode == "finish_reviews":
            self.target_val = counts[2] if counts and len(counts) >= 3 else 0
            if self.target_val == 0:
                tooltip("Micromanager: No reviews are currently due in this deck! Lock aborted.")
                return False
            self.current_val = 0
            self.initial_minutes = 5

        elif self.mode == "finish_deck":
            self.target_val = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
            if self.target_val == 0:
                tooltip("Micromanager: No cards are currently due in this deck! Lock aborted.")
                return False
            self.current_val = 0
            self.initial_minutes = 5

        else:
            self.mode = "cards"
            # Cap the goal to the total available cards
            self.target_val = min(val, total_due)
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
        self._history = []
        QTimer.singleShot(300, self.update_webview)
        return True

    def stop_lock(self, success=False):
        self.active = False
        self.locked_deck_id = None
        self._history = []
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

        # Instead of deleting the HUD, morph it into the unlocked Daily Progress tracker
        if mw.state == "review":
            self.update_webview()
        else:
            kill_js = """
                        var huds = document.querySelectorAll('#force-hud-container');
                        huds.forEach(function(hud) { hud.remove(); });
                        if (typeof removeForceHud === 'function') removeForceHud();
                    """
            if mw.web: mw.web.eval(kill_js)

        if success:
            QApplication.beep()
            tooltip("Micromanager: Session Complete.", period=3000)
        else:
            tooltip("Micromanager: Stopped")

    def get_current_display_values(self):
        text_display = "0"
        label_display = "LOCKED"
        pct = 0.0
        bar_color = "#ff3b30"  # Default to Red for all locked modes

        if not self.active:
            # UNLOCKED MODE: Standard Anki Daily Progress
            try:
                counts = mw.col.sched.counts()

                if counts and len(counts) >= 3:
                    new_cards, lrn_cards, rev_cards = counts[0], counts[1], counts[2]

                    # Track the workload entirely ignoring learning cards
                    total_remaining_today = new_cards + rev_cards

                    if rev_cards > 0:
                        remaining = rev_cards
                        label_display = "REVIEWS LEFT"
                        bar_color = "#007aff"  # Blue
                    elif new_cards > 0:
                        remaining = new_cards
                        label_display = "NEW CARDS LEFT"
                        bar_color = "#34c759"  # Green
                    else:
                        remaining = 0
                        label_display = "DONE"
                        bar_color = "#34c759"  # Green when finished
                else:
                    # Fallback if Anki returns weird queue data
                    remaining = sum(counts) if counts else 0
                    total_remaining_today = remaining
                    label_display = "CARDS LEFT"
                    bar_color = "#007aff"

                done = len(mw.col.find_cards("deck:current rated:1"))
                total = done + total_remaining_today

                pct = (done / total * 100) if total > 0 else 100.0
                text_display = str(remaining)

                return text_display, label_display, max(0.0, min(100.0, pct)), bar_color
            except Exception:
                return "0", "CARDS LEFT", 100.0, "#007aff"

        # 1. TIME MODE
        if self.mode == "time":
            mins = int(self.current_val / 60)
            secs = self.current_val % 60
            text_display = f"{mins:02d}:{secs:02d}"
            label_display = "TIMER"
            if self.target_val > 0:
                elapsed = self.target_val - self.current_val
                pct = (elapsed / self.target_val) * 100

        # 2. CORRECT ANSWERS
        elif self.mode == "correct":
            remaining = max(0, self.target_val - self.current_val)
            text_display = str(remaining)
            label_display = "CORRECT LEFT"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 3. TOTAL REVIEWS / CARDS
        elif self.mode == "cards":
            remaining = max(0, self.target_val - self.current_val)
            text_display = str(remaining)
            label_display = "CARDS LEFT"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 4. NEW CARDS ONLY
        elif self.mode == "new_cards":
            remaining = max(0, self.target_val - self.current_val)
            text_display = str(remaining)
            label_display = "NEW LEFT"
            if self.target_val > 0:
                pct = (self.current_val / self.target_val) * 100

        # 5. REVIEWS DUE
        elif self.mode == "finish_reviews":
            counts = mw.col.sched.counts() if mw.col else None
            remaining = counts[2] if counts and len(counts) >= 3 else 0
            text_display = str(remaining)
            label_display = "REVIEWS LEFT"
            if remaining > self.target_val: self.target_val = remaining
            if self.target_val > 0:
                completed = self.target_val - remaining
                pct = (completed / self.target_val) * 100

        # 6. COMPLETE DECK
        elif self.mode == "finish_deck":
            counts = mw.col.sched.counts() if mw.col else None
            remaining = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
            text_display = str(remaining)
            label_display = "TOTAL LEFT"
            if remaining > self.target_val: self.target_val = remaining
            if self.target_val > 0:
                completed = self.target_val - remaining
                pct = (completed / self.target_val) * 100

        return text_display, label_display, max(0.0, min(100.0, pct)), bar_color

    def inject_hud(self, content, context):
        if not isinstance(context, Reviewer): return

        val_txt, lbl_txt, pct, color = self.get_current_display_values()
        style_block = "<style>" + get_hud_css_rules() + "</style>"
        content.head += style_block

        html_str = HUD_HTML_TEMPLATE.replace("{VAL}", val_txt).replace("{LBL}", lbl_txt).replace("{PCT}",
                                                                                                 str(pct)).replace(
            "{COLOR}", color)
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

        # === DECK COMPLETION CHECKS ===
        if mw.state in ["overview", "review"]:
            try:
                counts = mw.col.sched.counts()

                # 1. Global Failsafe: If the deck is completely empty (no New, Learning, or Review), unlock.
                total_due = sum(counts) if counts else 0
                if total_due == 0:
                    self.stop_lock(success=True)
                    return

                # 2. Specific Mode Checks (if the deck isn't totally empty, but their specific goal is met)
                if self.mode == "finish_reviews":
                    remaining_reviews = counts[2] if len(counts) >= 3 else 0
                    if remaining_reviews == 0:
                        self.stop_lock(success=True)
                        return

                elif self.mode == "finish_deck":
                    # Only check if New and Review are zero
                    remaining_total = (counts[0] + counts[2]) if len(counts) >= 3 else 0
                    if remaining_total <= 0:
                        self.stop_lock(success=True)
                        return

                elif self.mode == "new_cards":
                    remaining_new = counts[0] if len(counts) >= 1 else 0
                    if remaining_new == 0:
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
        if not self.active:
            self.update_webview()
            return

        self._current_card_is_new = (card.type == 0)

        if self.mode == "finish_reviews":
            try:
                counts = mw.col.sched.counts()
                remaining_reviews = counts[2] if counts and len(counts) >= 3 else 0
                if remaining_reviews <= 0:
                    self.stop_lock(success=True)
                    return
            except AttributeError:
                pass
        elif self.mode == "finish_deck":
            try:
                counts = mw.col.sched.counts()
                remaining_total = (counts[0] + counts[2]) if counts and len(counts) >= 3 else 0
                if remaining_total <= 0:
                    self.stop_lock(success=True)
                    return
            except AttributeError:
                pass

        self.update_webview()

    def on_answer(self, reviewer, card, ease):
        if not self.active:
            self.update_webview()
            return

        counted = False
        if self.mode == "cards":
            counted = True
        elif self.mode == "correct" and ease > 1:
            counted = True
        elif self.mode == "new_cards" and getattr(self, "_current_card_is_new", False):
            counted = True

        if not hasattr(self, "_history"): self._history = []
        self._history.append(counted)

        if counted:
            self.current_val += 1
            self.update_persistence()
            if self.current_val >= self.target_val:
                self.stop_lock(success=True)
                return

        self.update_webview()

    def on_undo(self, *args):
        if not self.active:
            self.update_webview()
            return

        if self.mode in ["finish_reviews", "finish_deck"]:
            self.update_webview()
            return

        # Check if the undo actually involved a flashcard review.
        # Anki passes an 'OpChanges' object as the first argument.
        is_review_undo = True
        if args and hasattr(args[0], "review"):
            is_review_undo = args[0].review

        if self.mode in ["cards", "correct", "new_cards"]:
            # Only steal the point back if they ACTUALLY undid a review
            if is_review_undo and hasattr(self, "_history") and len(self._history) > 0:
                last_action_counted = self._history.pop()
                if last_action_counted and self.current_val > 0:
                    self.current_val -= 1
                    self.update_persistence()

            self.update_webview()

    def update_webview(self, *args, **kwargs):
        if mw.state != "review": return
        if not getattr(mw.reviewer, "card", None): return

        text_display, label_display, pct, color = self.get_current_display_values()
        stop_display = "flex" if self.active else "none"

        safe_html = HUD_HTML_TEMPLATE.replace("{VAL}", text_display).replace("{LBL}", label_display).replace("{PCT}",
                                                                                                             str(pct)).replace(
            "{COLOR}", color)
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
                        document.body.appendChild(d.firstElementChild);
                        hud = document.getElementById('force-hud-container');
                    }}
                    if (hud) {{
                        var valEl = document.getElementById('val-display');
                        var lblEl = document.getElementById('lbl-display');
                        var progEl = document.getElementById('force-hud-progress');

                        if (valEl) valEl.innerText = '{text_display}';
                        if (lblEl) lblEl.innerText = '{label_display}';
                        if (progEl) {{
                            progEl.style.width = '{pct}%';
                            progEl.style.setProperty('background-color', '{color}', 'important');
                        }}
                    }}
                }})();
                """
        mw.web.eval(js_cmd)

    def on_js_message(self, handled, message, context):
        if message == "force_config":
            ui.open_settings(self, is_update=self.active)
            return (True, None)

        return handled


lock_addon = AnkiLock()