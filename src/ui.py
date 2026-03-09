# ui.py
import random
import string
from aqt import mw
from aqt.qt import *
from aqt.theme import theme_manager
from aqt.utils import tooltip


class EventBlocker(QObject):
    """Utility class to intercept keys (like Enter or Paste) before QDialog acts on them."""

    def __init__(self, block_enter=False, block_paste=False, enter_callback=None, parent=None):
        super().__init__(parent)
        self.block_enter = block_enter
        self.block_paste = block_paste
        self.enter_callback = enter_callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if self.block_enter and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.enter_callback:
                    self.enter_callback()
                return True
            if self.block_paste and event.matches(QKeySequence.StandardKey.Paste):
                return True
        return False


def open_settings(addon, is_update=False):
    """Builds and displays the main, streamlined configuration window."""
    if is_update:
        addon.timer.stop()

    mw.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
    mw.showMaximized()

    d = QDialog(mw)
    d.setWindowTitle("Micromanager")
    d.setMinimumWidth(400)

    is_night = theme_manager.night_mode
    if is_night:
        dlg_bg, dlg_fg, box_bg, input_bg = "#2b2b2b", "white", "#3a3a3a", "#4a4a4a"
    else:
        dlg_bg, dlg_fg, box_bg, input_bg = "#ececec", "black", "#ffffff", "#ffffff"

    d.setStyleSheet(f"""
        QDialog {{ background-color: {dlg_bg}; color: {dlg_fg}; }}
        #sectionBox {{ background-color: {box_bg}; border-radius: 8px; }}
        QLabel, QRadioButton, QCheckBox {{ color: {dlg_fg}; font-size: 13px; }}
        QLineEdit, QTextEdit {{ padding: 5px; font-size: 13px; color: {dlg_fg}; background-color: {input_bg}; border: 1px solid #ccc; border-radius: 4px; }}
        .desc-label {{ color: #888; font-size: 11px; font-style: italic; }}
    """)

    layout = QVBoxLayout()
    layout.setSpacing(15)
    layout.setContentsMargins(20, 20, 20, 20)

    # --- Section 1: Goal Type ---
    sec_goal = QWidget()
    sec_goal.setObjectName("sectionBox")
    lay_goal = QVBoxLayout()
    lay_goal.setContentsMargins(15, 15, 15, 15)
    lay_goal.setSpacing(10)

    addon.rb_cards = QRadioButton("Total Reviews")
    addon.rb_correct = QRadioButton("Correct Answers")
    addon.rb_time = QRadioButton("Time (Minutes)")
    addon.rb_finish = QRadioButton("Reviews Due")

    if addon.mode == "time":
        addon.rb_time.setChecked(True)
    elif addon.mode == "correct":
        addon.rb_correct.setChecked(True)
    elif addon.mode == "finish_reviews":
        addon.rb_finish.setChecked(True)
    else:
        addon.rb_cards.setChecked(True)

    addon.spin_val = QSpinBox()
    addon.spin_val.setMinimumWidth(80)

    lbl_suffix = QLabel("cards")
    lbl_suffix.setStyleSheet("font-weight: bold; font-size: 13px; margin-left: 5px;")

    h_spin = QHBoxLayout()
    h_spin.addWidget(addon.spin_val)
    h_spin.addWidget(lbl_suffix)
    h_spin.addStretch()

    def update_ui_limits():
        is_finish = addon.rb_finish.isChecked()
        # Elements will completely collapse when hidden
        addon.spin_val.setVisible(not is_finish)
        lbl_suffix.setVisible(not is_finish)

        if addon.rb_time.isChecked():
            addon.spin_val.setRange(1, 480)
            lbl_suffix.setText("minutes")
        elif addon.rb_correct.isChecked():
            addon.spin_val.setRange(1, 5000)
            lbl_suffix.setText("cards")
        else:
            addon.spin_val.setRange(1, 5000)
            lbl_suffix.setText("cards")

    addon.rb_cards.toggled.connect(update_ui_limits)
    addon.rb_correct.toggled.connect(update_ui_limits)
    addon.rb_time.toggled.connect(update_ui_limits)
    addon.rb_finish.toggled.connect(update_ui_limits)
    update_ui_limits()

    if is_update:
        if addon.mode == "time":
            addon.spin_val.setValue(addon.initial_minutes)
        else:
            addon.spin_val.setValue(addon.target_val)
        addon.rb_cards.setEnabled(False)
        addon.rb_correct.setEnabled(False)
        addon.rb_time.setEnabled(False)
        addon.rb_finish.setEnabled(False)
        addon.spin_val.setEnabled(False)

    lay_goal.addWidget(addon.rb_cards)
    lay_goal.addWidget(addon.rb_correct)
    lay_goal.addWidget(addon.rb_time)
    lay_goal.addWidget(addon.rb_finish)
    lay_goal.addLayout(h_spin)
    sec_goal.setLayout(lay_goal)
    layout.addWidget(sec_goal)

    # --- Section 2: Security Settings ---
    sec_sec = QWidget()
    sec_sec.setObjectName("sectionBox")

    lay_sec = QVBoxLayout()
    lay_sec.setContentsMargins(15, 15, 15, 15)
    lay_sec.setSpacing(10)

    addon.rb_lock_none = QRadioButton("Unlocked")
    addon.rb_lock_blind = QRadioButton("Locked")
    addon.rb_lock_random = QRadioButton("Random Text (200 characters)")
    addon.rb_lock_custom = QRadioButton("Custom Password")

    lock_type = getattr(addon, "lock_type", "none")
    if lock_type == "custom":
        addon.rb_lock_custom.setChecked(True)
    elif lock_type == "blind":
        addon.rb_lock_blind.setChecked(True)
    elif lock_type == "random":
        addon.rb_lock_random.setChecked(True)
    else:
        addon.rb_lock_none.setChecked(True)

    addon.txt_pass = QLineEdit()
    # addon.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
    addon.txt_pass.setFixedWidth(200)
    addon.txt_pass.setFixedHeight(28)

    if hasattr(addon, "custom_password"):
        addon.txt_pass.setText(addon.custom_password)

        # Create a dedicated container widget for the password layout so it collapses entirely
        pass_container = QWidget()
        h_pass = QHBoxLayout(pass_container)
        h_pass.setContentsMargins(25, 0, 0, 0)  # 25px left indent
        h_pass.addWidget(addon.txt_pass)
        h_pass.addStretch()

        def toggle_pass_fields():
            is_custom = addon.rb_lock_custom.isChecked()
            pass_container.setVisible(is_custom)  # Hide the container, not just the text box

        addon.rb_lock_none.toggled.connect(toggle_pass_fields)
        addon.rb_lock_custom.toggled.connect(toggle_pass_fields)
        addon.rb_lock_blind.toggled.connect(toggle_pass_fields)
        addon.rb_lock_random.toggled.connect(toggle_pass_fields)
        toggle_pass_fields()

        if is_update:
            addon.rb_lock_none.setEnabled(False)
            addon.rb_lock_custom.setEnabled(False)
            addon.rb_lock_blind.setEnabled(False)
            addon.rb_lock_random.setEnabled(False)
            addon.txt_pass.setEnabled(False)

        lay_sec.addWidget(addon.rb_lock_none)
        lay_sec.addWidget(addon.rb_lock_blind)
        lay_sec.addWidget(addon.rb_lock_random)
        lay_sec.addWidget(addon.rb_lock_custom)
        lay_sec.addWidget(pass_container)  # Add the container to the main layout

    sec_sec.setLayout(lay_sec)
    layout.addWidget(sec_sec)

    # --- Action Button ---
    btn_text = "Resume Session" if is_update else "Activate Lock"
    btn_color = "#3498db" if is_update else "#27ae60"
    btn_hover = "#2980b9" if is_update else "#2ecc71"

    btn_start = QPushButton(btn_text)
    btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_start.setMinimumWidth(200)
    btn_start.setDefault(True)
    btn_start.setAutoDefault(True)

    btn_start.setStyleSheet(
        f"QPushButton {{ background-color: {btn_color}; color: white; padding: 10px 10px; font-size: 14px; font-weight: bold; border-radius: 6px; border: none;}} "
        f"QPushButton:hover {{ background-color: {btn_hover}; }}"
    )
    btn_start.clicked.connect(lambda: addon.start_lock(d, is_update))

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    btn_layout.addWidget(btn_start)
    btn_layout.addStretch()

    layout.addSpacing(10)
    layout.addLayout(btn_layout)

    layout.addStretch()

    d.setLayout(layout)
    d.exec()

    if is_update and addon.active:
        addon.timer.start(200)


def open_unlock_dialog(lock_type, expected_password):
    """Smart unlock dialog that adapts based on the lock type."""
    d = QDialog(mw)
    d.setWindowTitle("Unlock")
    d.setMinimumWidth(400)

    is_night = theme_manager.night_mode
    if is_night:
        dlg_bg, dlg_fg, input_bg = "#2b2b2b", "white", "#4a4a4a"
    else:
        dlg_bg, dlg_fg, input_bg = "#ececec", "black", "#ffffff"

    d.setStyleSheet(f"""
        QDialog {{ background-color: {dlg_bg}; color: {dlg_fg}; }}
        QLabel {{ color: {dlg_fg}; font-size: 14px; font-weight: bold; }}
        QPushButton {{ border-radius: 6px; border: none; font-weight: bold; padding: 8px 16px; font-size: 13px; color: white; }}
        #btnCancel {{ background-color: #7f8c8d; }}
        #btnCancel:hover {{ background-color: #95a5a6; }}
        #btnUnlock {{ background-color: #e74c3c; }}
        #btnUnlock:hover {{ background-color: #c0392b; }}
    """)

    layout = QVBoxLayout()
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(15)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Prevents wild vertical stretching

    lbl_error = QLabel("")
    lbl_error.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 13px;")
    lbl_error.hide()

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    btn_cancel = QPushButton("Cancel" if lock_type != "blind" else "Close")
    btn_cancel.setObjectName("btnCancel")
    btn_cancel.setAutoDefault(False)
    btn_cancel.clicked.connect(d.reject)
    btn_layout.addWidget(btn_cancel)

    if lock_type == "blind":
        lbl = QLabel("Blind Lock is active. You must complete your goal to unlock this session early!")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addLayout(btn_layout)
        d.setLayout(layout)
        d.exec()
        return False

    elif lock_type == "random":
        lbl = QLabel("Type the following exact text to unlock:")
        layout.addWidget(lbl)

        txt_target = QTextEdit(expected_password)
        txt_target.setReadOnly(True)
        txt_target.setMaximumHeight(80)
        txt_target.setMaximumWidth(800)  # Prevents infinite horizontal stretch
        txt_target.setStyleSheet(
            f"background-color: {input_bg}; color: {dlg_fg}; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace;")

        txt_target.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(txt_target)

        txt_input = QTextEdit()
        txt_input.setMaximumHeight(80)
        txt_input.setMaximumWidth(800)  # Prevents infinite horizontal stretch
        txt_input.setStyleSheet(
            f"background-color: {input_bg}; color: {dlg_fg}; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace;")

        txt_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(txt_input)
        layout.addWidget(lbl_error)

        btn_unlock = QPushButton("Unlock")
        btn_unlock.setObjectName("btnUnlock")
        btn_unlock.setAutoDefault(False)
        btn_layout.addWidget(btn_unlock)

        def attempt_unlock():
            if txt_input.toPlainText() == expected_password:
                d.accept()
            else:
                lbl_error.setText("Incorrect text. Please find and fix your mistake.")
                lbl_error.show()

        btn_unlock.clicked.connect(attempt_unlock)

        d.filter = EventBlocker(block_enter=True, block_paste=True, enter_callback=attempt_unlock, parent=d)
        txt_input.installEventFilter(d.filter)

    elif lock_type == "custom":
        lbl = QLabel("Enter password to quit:")
        layout.addWidget(lbl)

        txt_input = QLineEdit()
        txt_input.setEchoMode(QLineEdit.EchoMode.Password)
        txt_input.setMaximumWidth(400)  # Restricts text box width
        txt_input.setStyleSheet(
            f"background-color: {input_bg}; color: {dlg_fg}; padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        layout.addWidget(txt_input)

        layout.addWidget(lbl_error)

        btn_unlock = QPushButton("Unlock")
        btn_unlock.setObjectName("btnUnlock")
        btn_unlock.setAutoDefault(False)
        btn_layout.addWidget(btn_unlock)

        def attempt_unlock():
            if txt_input.text() == expected_password:
                d.accept()
            else:
                lbl_error.setText("Wrong password, try again.")
                lbl_error.show()

        btn_unlock.clicked.connect(attempt_unlock)

        d.filter = EventBlocker(block_enter=True, block_paste=False, enter_callback=attempt_unlock, parent=d)
        txt_input.installEventFilter(d.filter)

    layout.addLayout(btn_layout)
    d.setLayout(layout)

    return d.exec() == QDialog.DialogCode.Accepted