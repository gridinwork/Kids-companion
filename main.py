"""TechnoLab Agent №3 — Windows companion, screen-time keeper and mini-games."""

from __future__ import annotations

import ctypes
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRect, Qt, QTime, QTimer
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

import logic
from games import GAME_NAMES, MiniGame
from logic import (
    MSG_OK,
    MSG_START,
    SKIN_NAMES,
    CentralState,
    PolicyEngine,
    change_pin,
    configure_paths,
    ensure_pin_file,
    fmt_duration,
    load_persistence,
    log_exception,
    log_line,
    save_config,
    save_persistence,
    set_autostart,
    statistics_text,
    tooltip_for,
    validate_new_pin,
    validate_settings,
    voice_for,
    write_pin_file,
)
from lesson import GAME_LESSONS, SHOW_OFFS, spots_for
from petdraw import export_skin_catalog, icon_for, idle_pose, paint_pet, resolve_skin
from sound import TICKLES, ensure_sounds, play, play_gag, play_trick

say = logic.say


class SayLabel(QLabel):
    """A label whose text is adapted to who the pet is talking to (one named child or two)."""

    def setText(self, text):
        super().setText(say(text))


FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent

STATE_LABELS = {
    "IDLE": "спокойно",
    "HAPPY": "радуется",
    "PLAY": "играет",
    "EAT": "ест",
    "SLEEP": "спит",
    "TIRED": "устал",
    "EXERCISE": "зарядка",
    "REMINDER": "напоминание",
    "WARNING": "предупреждение",
    "LOCK_COUNTDOWN": "скоро блокировка",
    "CELEBRATION": "праздник",
}

STYLE = """
QWidget { background:#1C2128; color:#F4F7FB; font-family:"Segoe UI"; font-size:13px; }
QLabel#petBubble { background:#242932; color:white; border:2px solid #555; border-radius:12px; padding:12px; }
QPushButton { background:#3A4250; color:white; border:none; border-radius:8px; padding:8px 12px; }
QPushButton:hover { background:#4C5666; }
QLineEdit, QSpinBox, QTimeEdit, QComboBox, QTextEdit { background:#12161C; color:white; border:1px solid #3A4250; border-radius:6px; padding:4px; }
QTabWidget::pane { border: 1px solid #3A4250; }
QTabBar::tab { background:#2A3140; color:#F4F7FB; padding:8px 16px; margin-right:4px; }
QTabBar::tab:selected { background:#F6C453; color:#1C2128; }
QTabBar::tab:disabled { color:#8B93A1; }
"""

HIDE_AFTER_MS = 30000
STAY_LINE = "Хорошо, я буду рядом."
HERE_LINES = [
    "Привет, я здесь.",
    "Я всё ещё здесь.",
    "Я рядом. Присмотришь за мной?",
    "Привет! Давай я побуду с тобой.",
    "Я тут и могу просто побыть рядом.",
]
PLAY_LINES = [
    "Хочешь, поиграем?",
    "Давай поиграем? Я знаю несколько игр.",
    "Можем поиграть, если хочешь.",
    "Я хочу поиграть с тобой. Пойдём?",
    "Есть минутка поиграть?",
]
LAUGH_LINES = [
    "Хочешь, я тебя рассмешу?",
    "Давай посмеёмся? Я умею смешные звуки.",
    "Могу построить рожицу. Хочешь?",
    "Пощекочешь меня? Будет смешно.",
    "Хочу, чтобы тебе было весело. Можно?",
]

COMPANION_STYLE = """
QWidget { background: transparent; color: white; }
QLabel#petBubble { background:#242932; color:white; border:2px solid #555; border-radius:12px; padding:10px; }
QPushButton { background:#3A4250; color:white; border:none; border-radius:8px; padding:6px 10px; }
QPushButton:hover { background:#4C5666; }
"""


def _app_id() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TechnoLab.Agent3.KidsCompanion")
    except Exception:
        pass


class PixelPet(QWidget):
    def __init__(self, on_click=None, drag_window=False, on_right=None, on_activity=None):
        super().__init__()
        self.on_click = on_click
        self.drag_window = drag_window
        self.on_right = on_right
        self.on_activity = on_activity
        self.skin = "Пантера"
        self.state_name = "HAPPY"
        self.visual = ""
        self.expression = ""
        self.frame = 0
        self._press = None
        self._window_origin = None
        self._dragged = False
        self.can_drag = lambda: True
        self.idle_anim = False
        self.setFixedSize(140, 140)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        pose, face = "", self.expression
        if self.idle_anim and not self.expression and self.state_name in ("HAPPY", "IDLE"):
            pose, face = idle_pose(self.frame, resolve_skin(self.skin)[1])
        paint_pet(
            painter,
            QRect(0, 0, self.width(), self.height()),
            self.skin,
            self.state_name,
            self.frame,
            self.visual,
            face,
            pose,
        )
        painter.end()
        self.frame += 1

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.on_right:
                self.on_right()
            elif self.drag_window:
                self.window().hide()
            return
        if event.button() == Qt.LeftButton and self.drag_window and self.can_drag():
            self._press = event.globalPosition().toPoint()
            self._window_origin = self.window().pos()
            self._dragged = False
            if self.on_activity:
                self.on_activity(True)
        elif event.button() == Qt.LeftButton and self.on_click:
            self.on_click()

    def mouseMoveEvent(self, event):
        if not self.drag_window or self._press is None or self._window_origin is None:
            return
        delta = event.globalPosition().toPoint() - self._press
        if delta.manhattanLength() > 6:
            self._dragged = True
            self.window().move(self._window_origin + delta)

    def mouseReleaseEvent(self, event):
        if self.drag_window and event.button() == Qt.LeftButton and self._press is not None:
            if not self._dragged and self.on_click:
                self.on_click()
            self._press = None
            self._window_origin = None
            if self.on_activity:
                self.on_activity(False)


class CompanionWindow(QWidget):
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        self.mode = "notice"
        self._laugh_step = 0
        self._declines = 0
        self._recent = {"here": "", "play": "", "laugh": ""}
        self._parked = False
        self._parked_message = ""
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(HIDE_AFTER_MS)
        self._hide_timer.timeout.connect(self.retreat)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(COMPANION_STYLE)
        self.setWindowTitle("TechnoLab Kids Companion 0.3.0")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.bubble_box = QWidget()
        bubble_layout = QVBoxLayout(self.bubble_box)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        self.bubble = QLabel(say(MSG_START))
        self.bubble.setObjectName("petBubble")
        self.bubble.setWordWrap(True)
        self.bubble.setFixedWidth(230)
        bubble_layout.addWidget(self.bubble)
        self.button_row = QHBoxLayout()
        bubble_layout.addLayout(self.button_row)
        layout.addWidget(self.bubble_box, 0, Qt.AlignRight)
        self.pet = PixelPet(
            on_click=agent.on_pet_clicked,
            drag_window=True,
            on_right=agent.open_lesson,
            on_activity=self._on_drag,
        )
        self.pet.setToolTip("Правая кнопка мыши — что я умею")
        self.pet.can_drag = self._can_drag
        self.pet.idle_anim = True
        layout.addWidget(self.pet, 0, Qt.AlignRight)
        self._anchor()
        self.arm_hide()

    def _clear_buttons(self):
        while self.button_row.count():
            item = self.button_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _config(self) -> dict:
        engine = getattr(self.agent, "engine", None)
        return engine.config if engine is not None else {}

    def _placement(self) -> str:
        return self._config().get("pet_position", "free")

    def _can_drag(self) -> bool:
        return self._placement() == "free"

    def apply_placement(self):
        self._anchor()

    def _anchor(self):
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        mode = self._placement()
        side = Qt.AlignLeft if mode == "bottom_left" else Qt.AlignRight
        layout = self.layout()
        layout.setAlignment(self.bubble_box, side)
        layout.setAlignment(self.pet, side)
        if mode == "bottom_left":
            x, y = area.left() + 12, area.bottom() - self.height() - 12
        else:
            cfg = self._config()
            anchor_x, anchor_y = cfg.get("pet_x", -1), cfg.get("pet_y", -1)
            if mode != "free" or anchor_x < 0 or anchor_y < 0:
                anchor_x, anchor_y = area.right() - 12, area.bottom() - 12
            x, y = anchor_x - self.width(), anchor_y - self.height()
        x = max(area.left(), min(x, area.right() - self.width()))
        y = max(area.top(), min(y, area.bottom() - self.height()))
        self.move(x, y)

    def show_prompt(self, text: str, buttons: list[tuple[str, object]], mode: str = "talk"):
        self.mode = mode
        self.bubble.setText(say(text))
        self._clear_buttons()
        for label, callback in buttons:
            button = QPushButton(label)
            button.clicked.connect(callback)
            self.button_row.addWidget(button)
        self.bubble_box.show()
        self._anchor()
        self.agent.remember_line(text)

    def show_system(self, text: str, ack: bool = False):
        buttons = [("Понятно", self.agent.acknowledge)] if ack else []
        state = self.agent.engine.state
        if not ack and state.care_due and text == state.CURRENT_PET_MESSAGE:
            buttons = [("Поиграем", self.agent.open_care), ("Позже", self.retreat)]
        self._parked = False
        self.pet.expression = ""
        self.show_prompt(text, buttons, mode="notice")
        self.show()
        if ack or self.blocked():
            self._hide_timer.stop()
        else:
            self.arm_hide()

    def line_from(self, pool: list[str], key: str) -> str:
        choices = [item for item in pool if item != self._recent.get(key)] or list(pool)
        line = random.choice(choices)
        self._recent[key] = line
        return line

    def blocked(self) -> bool:
        state = self.agent.engine.state
        return (
            self.mode == "laugh"
            or bool(state.pending_routine_title)
            or (state.break_due and not state.break_acknowledged)
            or state.countdown_started
        )

    def arm_hide(self):
        if self.blocked():
            self._hide_timer.stop()
            return
        self._hide_timer.start(HIDE_AFTER_MS)

    def _on_drag(self, active: bool):
        if active:
            self._hide_timer.stop()
        else:
            if self._placement() == "free":
                geo = self.frameGeometry()
                cfg = self._config()
                cfg["pet_x"], cfg["pet_y"] = geo.right() + 1, geo.bottom() + 1
                self.agent.persist()
            self.arm_hide()

    def greet(self):
        self._parked = False
        self._declines = 0
        self.pet.expression = "smile"
        self.show_prompt(
            self.line_from(HERE_LINES, "here"),
            [
                ("Игры", self.ask_play),
                ("Смех", self._ask_laugh),
                ("Уход", self.agent.open_care),
                ("Позже", lambda: self.decline("here")),
            ],
        )
        self.show()
        self.arm_hide()

    def ask_play(self):
        self.pet.expression = "smile"
        self.show_prompt(
            self.line_from(PLAY_LINES, "play"),
            [("Да", self._yes_play), ("Нет", lambda: self.decline("play"))],
        )
        self.arm_hide()

    def _yes_play(self):
        self._declines = 0
        self.quiet()
        self.hide()
        self._parked = True
        self._parked_message = self.agent.engine.state.CURRENT_PET_MESSAGE
        self.agent.open_games()

    def _ask_laugh(self):
        self.pet.expression = "wink"
        self.show_prompt(
            self.line_from(LAUGH_LINES, "laugh"),
            [("Да", self.begin_laugh), ("Нет", lambda: self.decline("laugh"))],
        )
        self.arm_hide()

    def decline(self, source: str):
        self._declines += 1
        if self._declines >= 2:
            self.stay_nearby()
            return
        if source == "laugh":
            self.ask_play()
        else:
            self._ask_laugh()

    def stay_nearby(self):
        self.pet.expression = "smile"
        self.show_prompt(STAY_LINE, [], mode="notice")
        self.show()
        self.arm_hide()

    def begin_laugh(self):
        self._laugh_step = 0
        self._declines = 0
        self.pet.expression = "laugh"
        self.show_prompt("Щекочи меня! Жми на мордочку.", [("Хватит", self.stay_nearby)], mode="laugh")
        self._hide_timer.stop()
        play_gag(self.agent.paths["sounds"], self.agent.pet_voice(), "giggle", self.agent.engine.state.SOUND_ENABLED)

    def poke(self):
        self._laugh_step += 1
        gag, line, face = TICKLES[self._laugh_step % len(TICKLES)]
        self.pet.expression = face
        self.bubble.setText(say(line))
        self.agent.remember_line(line)
        play_gag(self.agent.paths["sounds"], self.agent.pet_voice(), gag, self.agent.engine.state.SOUND_ENABLED)
        self.pet.update()

    def retreat(self):
        if self.blocked():
            self._hide_timer.stop()
            return
        self._declines = 0
        self.quiet()
        self._parked = True
        self._parked_message = self.agent.engine.state.CURRENT_PET_MESSAGE
        self.hide()

    def quiet(self):
        self.mode = "idle"
        self.pet.expression = ""
        self._clear_buttons()
        self.bubble_box.hide()
        self._anchor()
        state = self.agent.engine.state
        alert = (
            state.pending_routine_title
            or (state.break_due and not state.break_acknowledged)
            or state.countdown_started
            or state.LOCK_STATE in ("warning", "countdown", "locked")
        )
        if not alert:
            self.agent.remember_line(MSG_OK)

    def apply_state(self, state: CentralState):
        self.pet.skin = state.SELECTED_SKIN
        self.pet.state_name = state.CURRENT_PET_STATE
        self.pet.visual = state.visual
        if self.mode != "laugh":
            self.pet.expression = ""
        self.pet.update()
        message = state.CURRENT_PET_MESSAGE or ""
        needs_ack = bool(state.pending_routine_title) or (state.break_due and not state.break_acknowledged)
        urgent = needs_ack or state.countdown_started
        if self.mode in ("talk", "laugh") and not urgent:
            return
        if self._parked and not urgent and message == self._parked_message:
            return
        important = message not in ("", MSG_OK) or needs_ack
        if important:
            if self.bubble.text() != say(message) or self.bubble_box.isHidden() or self.mode != "notice":
                self.show_system(message, ack=needs_ack)
        elif self.mode == "notice" and message in ("", MSG_OK):
            self.quiet()
            if not self._hide_timer.isActive():
                self.arm_hide()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class PetsPage(QWidget):
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        self.previews: list[PixelPet] = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите питомца. У каждого своё имя, и все доступны без ограничений."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        grid = QGridLayout(host)
        for index, name in enumerate(SKIN_NAMES):
            card = QWidget()
            column = QVBoxLayout(card)
            pet = PixelPet(on_click=lambda n=name: agent.choose_skin(n))
            pet.setFixedSize(96, 96)
            pet.skin = name
            self.previews.append(pet)
            title = QLabel(name)
            title.setAlignment(Qt.AlignCenter)
            column.addWidget(pet, 0, Qt.AlignCenter)
            column.addWidget(title)
            grid.addWidget(card, index // 5, index % 5)
        scroll.setWidget(host)
        layout.addWidget(scroll)

    def mark_selected(self, name: str):
        for pet in self.previews:
            pet.setStyleSheet("border: 3px solid #F6C453;" if pet.skin == name else "border: 3px solid transparent;")


class LockPage(QWidget):
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        layout = QVBoxLayout(self)
        self.caption = QLabel()
        self.caption.setWordWrap(True)
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setPlaceholderText("PIN или пароль")
        self.button = QPushButton()
        self.button.clicked.connect(self._act)
        hint = QLabel(
            "Пароль по умолчанию — 0000. Он хранится в одном файле PIN.txt в папке программы. "
            "Если пароль забыт, откройте PIN.txt и замените строку."
        )
        hint.setWordWrap(True)
        layout.addWidget(self.caption)
        layout.addWidget(self.pin)
        layout.addWidget(self.button)
        layout.addWidget(hint)
        layout.addStretch(1)

    def refresh(self, locked: bool):
        if locked:
            self.caption.setText(
                "Сейчас включена детская блокировка. Клик по питомцу открывает только игру и «рассмеши». "
                "Настройки и выбор питомца закрыты."
            )
            self.pin.show()
            self.button.setText("Разблокировать")
        else:
            self.caption.setText(
                "Пока блокировка выключена, программа только напоминает и экран не блокирует. "
                "После «Заблокировать» настройки скрываются, а экран блокируется в заданное время, "
                "пока вы не введёте PIN."
            )
            self.pin.hide()
            self.pin.clear()
            self.button.setText("Заблокировать")

    def _act(self):
        if self.agent.engine.state.child_locked:
            if not self.agent.engine.pin_ok(self.pin.text()):
                QMessageBox.warning(self, "PIN", "Неверный пароль.")
                return
            self.pin.clear()
            self.agent.set_child_locked(False)
        else:
            self.agent.set_child_locked(True)


class Dashboard(QMainWindow):
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        self.setWindowTitle("TechnoLab Kids Companion 0.3.0")
        self.resize(820, 640)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        info = QVBoxLayout()
        self.state_label = QLabel()
        self.state_label.setObjectName("dashState")
        self.active_label = QLabel()
        self.active_label.setObjectName("dashActive")
        self.session_label = QLabel()
        self.session_label.setObjectName("dashSession")
        self.remain_label = QLabel()
        self.remain_label.setObjectName("dashRemain")
        self.routine_label = QLabel()
        self.routine_label.setObjectName("dashRoutine")
        self.break_label = QLabel()
        self.break_label.setObjectName("dashBreak")
        for label in (
            self.state_label,
            self.active_label,
            self.session_label,
            self.remain_label,
            self.routine_label,
            self.break_label,
        ):
            label.setWordWrap(True)
            info.addWidget(label)
        layout.addLayout(info)
        self.tabs = QTabWidget()
        self.settings_page = SettingsPanel(agent)
        self.pets_page = PetsPage(agent)
        self.lock_page = LockPage(agent)
        self.tabs.addTab(self.settings_page, "Настройка")
        self.tabs.addTab(self.pets_page, "Питомцы")
        self.tabs.addTab(self.lock_page, "Заблокировать")
        self.tabs.currentChanged.connect(self._guard_tabs)
        layout.addWidget(self.tabs)
        actions = QHBoxLayout()
        self.exit_button = QPushButton("Выйти из программы…")
        self.exit_button.clicked.connect(agent.prompt_exit)
        self.uninstall_button = QPushButton("Удалить программу…")
        self.uninstall_button.clicked.connect(agent.prompt_uninstall)
        actions.addWidget(self.exit_button)
        actions.addWidget(self.uninstall_button)
        layout.addLayout(actions)
        self.pet_previews = self.pets_page.previews

    def apply_state(self, state: CentralState, engine: PolicyEngine):
        now = self.agent.now_provider()
        _remain, daily, schedule = engine.remaining(now)
        self.state_label.setText(
            f"Питомец: {state.SELECTED_SKIN}. Состояние: {STATE_LABELS.get(state.CURRENT_PET_STATE, state.CURRENT_PET_STATE)}."
        )
        self.active_label.setText(f"Активное время сегодня: {fmt_duration(state.ACTIVE_SECONDS_TODAY)}")
        self.session_label.setText(f"Текущая непрерывная сессия: {fmt_duration(state.CONTINUOUS_ACTIVE_SECONDS)}")
        remain_text = fmt_duration(daily)
        if state.PARENT_OVERRIDE_STATE:
            remain_text += ". Можно ещё немного побыть вместе"
        elif schedule < daily:
            remain_text += f". Разрешённое время закончится через {fmt_duration(schedule)}"
        self.remain_label.setText(f"До дневного лимита: {remain_text}")
        self.routine_label.setText(f"Следующий распорядок: {state.NEXT_ROUTINE}")
        self.break_label.setText(f"Перерыв: {engine.break_status()}")
        self.pets_page.mark_selected(state.SELECTED_SKIN)
        self.refresh_lock()

    def refresh_lock(self):
        locked = bool(self.agent.engine.state.child_locked)
        self.tabs.setTabText(2, "Разблокировать" if locked else "Заблокировать")
        self.tabs.setTabEnabled(0, not locked)
        self.tabs.setTabEnabled(1, not locked)
        self.lock_page.refresh(locked)
        if locked and self.tabs.currentIndex() != 2:
            self.tabs.setCurrentIndex(2)

    def _guard_tabs(self, index: int):
        if self.agent.engine.state.child_locked and index != 2:
            self.tabs.setCurrentIndex(2)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class CountdownOverlay(QDialog):
    def __init__(self, on_parent):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet("background:#111111; color:white;")
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size:40px; color:white; background:#111111; padding:24px;")
        button = QPushButton("Родительская разблокировка / отмена")
        button.setStyleSheet("font-size:18px; padding:16px; background:#F6C453; color:#1C2128;")
        button.clicked.connect(on_parent)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label, 1)
        layout.addWidget(button)

    def present(self, text: str):
        self.label.setText(text)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()


class RoutineEditor(QWidget):
    def __init__(self, routine: dict):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.time = QTimeEdit()
        self.time.setDisplayFormat("HH:mm")
        hour, minute = routine["time"].split(":")
        self.time.setTime(QTime(int(hour), int(minute)))
        self.title = QLineEdit(routine["title"])
        self.message = QLineEdit(routine["message"])
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 180)
        self.repeat.setValue(int(routine["repeat_minutes"]))
        self.kind = routine.get("kind") or "custom"
        layout.addWidget(self.time)
        layout.addWidget(self.title, 1)
        layout.addWidget(self.message, 2)
        layout.addWidget(self.repeat)

    def value(self) -> dict:
        clock = self.time.time()
        return {
            "time": f"{clock.hour():02d}:{clock.minute():02d}",
            "title": self.title.text().strip(),
            "message": self.message.text().strip(),
            "repeat_minutes": self.repeat.value(),
            "kind": self.kind,
        }


class SettingsPanel(QWidget):
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        shell = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        cfg = agent.engine.config
        self.daily = self._spin(1, 1440, cfg["daily_limit_minutes"])
        self.break_after = self._spin(1, 600, cfg["break_after_minutes"])
        self.break_duration = self._spin(1, 180, cfg["break_duration_minutes"])
        self.idle = self._spin(15, 3600, cfg["idle_threshold_seconds"])
        self.final_seconds = self._spin(10, 120, cfg["final_warning_seconds"])
        self.grace = self._spin(30, 3600, cfg["relock_grace_seconds"])
        self.override_minutes = self._spin(1, 240, cfg["override_minutes"])
        self.repeat = self._spin(1, 180, cfg["reminder_repeat_minutes"])
        self.win_bonus = self._spin(0, 60, cfg["win_bonus_minutes"])
        self.bonus_cap = self._spin(0, 240, cfg["bonus_daily_cap_minutes"])
        self.care_after = self._spin(1, 600, cfg["care_after_minutes"])
        self.care_minutes = self._spin(1, 60, cfg["care_minutes"])
        self.allowed_from = self._time(cfg["allowed_from"])
        self.allowed_until = self._time(cfg["allowed_until"])
        self.bedtime_start = self._time(cfg["bedtime_start"])
        self.bedtime_end = self._time(cfg["bedtime_end"])
        self.enforce = QCheckBox("Блокировать вне разрешённых часов и в часы сна")
        self.enforce.setChecked(bool(cfg.get("schedule_enforcement", True)))
        self.sound = QCheckBox("Звук")
        self.sound.setChecked(bool(cfg["sound"]))
        self.notifications = QCheckBox("Всплывающие уведомления")
        self.notifications.setChecked(bool(cfg.get("notifications", True)))
        self.autostart = QCheckBox("Автозапуск Windows")
        try:
            cfg["autostart"] = logic.get_autostart()
        except OSError as exc:
            agent.autostart_error = str(exc)
        self.autostart.setChecked(bool(cfg.get("autostart", False)))
        self.autostart.toggled.connect(self._autostart_changed)
        self.school_enabled = QCheckBox("Учебное время по будням (без лимита, уведомлений и блокировки)")
        self.school_enabled.setChecked(cfg["school_enabled"])
        self.school_from = self._time(cfg["school_from"])
        self.school_until = self._time(cfg["school_until"])
        form.addRow("Дневной лимит, минут", self.daily)
        form.addRow("Перерыв после активной работы, минут", self.break_after)
        form.addRow("Длительность перерыва, минут", self.break_duration)
        form.addRow("Порог бездействия, секунд", self.idle)
        form.addRow("Финальный отсчёт, секунд", self.final_seconds)
        form.addRow("Пауза после блокировки, секунд", self.grace)
        form.addRow("Временная разблокировка, минут", self.override_minutes)
        form.addRow("Повтор напоминания, минут", self.repeat)
        form.addRow("Разрешено с", self.allowed_from)
        form.addRow("Разрешено до", self.allowed_until)
        form.addRow("Сон с", self.bedtime_start)
        form.addRow("Сон до", self.bedtime_end)
        form.addRow(self.enforce)
        form.addRow(self.sound)
        form.addRow(self.notifications)
        form.addRow(self.autostart)
        form.addRow(self.school_enabled)
        form.addRow("Занятия с (понедельник–пятница)", self.school_from)
        form.addRow("Занятия до", self.school_until)
        self.gender = QComboBox()
        self.gender.addItem("Не выбрано", "")
        self.gender.addItem("Мальчик", "boy")
        self.gender.addItem("Девочка", "girl")
        self.gender.addItem("Двое детей", "two")
        self.gender.setCurrentIndex(max(0, self.gender.findData(cfg.get("child_gender", ""))))
        form.addRow("Кто играет", self.gender)
        self.child_name = QLineEdit(cfg.get("child_name", ""))
        self.child_name.setPlaceholderText("для двоих детей имя не нужно")
        form.addRow("Имя ребёнка", self.child_name)
        form.addRow("Минут за прохождение всех 3 уровней игры", self.win_bonus)
        form.addRow("Максимум бонусных минут в день", self.bonus_cap)
        self.place_group = QButtonGroup(self)
        place_box = QVBoxLayout()
        self.place_radios = {}
        for key, label in (
            ("free", "Свободно: питомца можно перетаскивать, место запоминается"),
            ("bottom_right", "Всегда внизу справа"),
            ("bottom_left", "Всегда внизу слева"),
        ):
            radio = QRadioButton(label)
            radio.setChecked(cfg.get("pet_position", "free") == key)
            self.place_group.addButton(radio)
            self.place_radios[key] = radio
            place_box.addWidget(radio)
        form.addRow("Где живёт питомец", place_box)
        self.care_enabled = QCheckBox("Питомец просит поиграть с ним (как тамагочи)")
        self.care_enabled.setChecked(bool(cfg.get("care_enabled", True)))
        form.addRow(self.care_enabled)
        form.addRow("Просить поиграть после, минут работы", self.care_after)
        form.addRow("Сколько минут играть с питомцем", self.care_minutes)
        form.addRow(QLabel("Питомца выбирайте на вкладке «Питомцы»."))
        form.addRow(QLabel("Дела: время, название, текст, повтор в минутах"))
        self.routine_box = QVBoxLayout()
        self.routine_rows: list[RoutineEditor] = []
        for routine in cfg["routines"]:
            self._add_routine(routine)
        form.addRow(self.routine_box)
        add = QPushButton("Добавить дело")
        add.clicked.connect(lambda: self._add_routine({"time": "12:00", "title": "Дело", "message": "Давай сделаем это дело.", "repeat_minutes": 5, "kind": "custom"}))
        form.addRow(add)
        self.stats = QTextEdit()
        self.stats.setReadOnly(True)
        self.stats.setPlainText(statistics_text(agent.engine.stats, agent.engine.state))
        self.stats.setFixedHeight(140)
        form.addRow("Статистика", self.stats)
        self.new_pin = QLineEdit()
        self.new_pin.setEchoMode(QLineEdit.Password)
        self.confirm_pin = QLineEdit()
        self.confirm_pin.setEchoMode(QLineEdit.Password)
        pin_button = QPushButton("Сохранить пароль")
        pin_button.clicked.connect(self._change_pin)
        form.addRow("Новый пароль", self.new_pin)
        form.addRow("Повтор пароля", self.confirm_pin)
        form.addRow(pin_button)
        form.addRow(QLabel("Пароль записывается в файл PIN.txt. Если он забыт, откройте этот файл и замените строку."))
        unlock = QPushButton("Отключить контроль (без блокировки экрана)")
        unlock.clicked.connect(self._unlock)
        form.addRow(unlock)
        resume = QPushButton("Включить контроль снова")
        resume.clicked.connect(self._resume)
        form.addRow(resume)
        if agent.autostart_error:
            form.addRow(QLabel(agent.autostart_error))
        scroll.setWidget(body)
        shell.addWidget(scroll)
        save = QPushButton("Сохранить")
        save.clicked.connect(self._save)
        shell.addWidget(save)

    def _autostart_changed(self, enabled):
        pin, accepted = self.agent._ask_pin("Автозапуск")
        ok = accepted and self.agent.engine.pin_ok(pin)
        if ok:
            ok, error = set_autostart(enabled, log_path=self.agent.paths["log"])
            if not ok:
                QMessageBox.warning(self, "Автозапуск", error)
        elif accepted:
            QMessageBox.warning(self, "PIN", "Неверный PIN.")
        if not ok:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(bool(self.agent.engine.config["autostart"]))
            self.autostart.blockSignals(False)
            return
        self.agent.engine.config["autostart"] = enabled
        self.agent.persist()

    def _spin(self, lo, hi, value):
        box = QSpinBox()
        box.setRange(lo, hi)
        box.setValue(int(value))
        return box

    def _time(self, value: str):
        hour, minute = value.split(":")
        box = QTimeEdit()
        box.setDisplayFormat("HH:mm")
        box.setTime(QTime(int(hour), int(minute)))
        return box

    def _clock(self, box: QTimeEdit) -> str:
        clock = box.time()
        return f"{clock.hour():02d}:{clock.minute():02d}"

    def _add_routine(self, routine: dict):
        row = RoutineEditor(routine)
        remove = QPushButton("Удалить")

        def drop():
            if len(self.routine_rows) <= 1:
                QMessageBox.information(self, "Дела", "Оставьте хотя бы одно дело.")
                return
            self.routine_rows.remove(row)
            wrap.setParent(None)
            wrap.deleteLater()

        remove.clicked.connect(drop)
        wrap = QWidget()
        inner = QVBoxLayout(wrap)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(row)
        inner.addWidget(remove)
        self.routine_box.addWidget(wrap)
        self.routine_rows.append(row)

    def _change_pin(self):
        pin, accepted = self.agent._ask_pin("Смена пароля")
        if not accepted:
            return
        if not self.agent.engine.pin_ok(pin):
            QMessageBox.warning(self, "PIN", "Неверный PIN.")
            return
        error = self.agent.change_password(self.new_pin.text(), self.confirm_pin.text())
        if error:
            QMessageBox.warning(self, "Пароль", error)
            return
        self.new_pin.clear()
        self.confirm_pin.clear()
        QMessageBox.information(self, "Пароль", "Пароль сохранён в файле PIN.txt.")

    def _unlock(self):
        pin, accepted = self.agent._ask_pin("Отключение контроля")
        if not accepted:
            return
        if not self.agent.engine.pin_ok(pin):
            QMessageBox.warning(self, "PIN", "Неверный PIN.")
            return
        self.agent.apply_override()
        QMessageBox.information(self, "Контроль", "Контроль отключён, экран блокироваться не будет, пока вы не включите его снова.")

    def _resume(self):
        self.agent.resume_control()
        QMessageBox.information(self, "Контроль", "Контроль снова включён.")

    def _save(self):
        pin, accepted = self.agent._ask_pin("Сохранение настроек")
        if not accepted:
            return
        if not self.agent.engine.pin_ok(pin):
            QMessageBox.warning(self, "PIN", "Неверный PIN.")
            return
        routines = []
        for row in self.routine_rows:
            item = row.value()
            if not item["title"] or not item["message"]:
                QMessageBox.warning(self, "Parent Mode", "Заполните название и текст каждого дела.")
                return
            routines.append(item)
        cfg = dict(self.agent.engine.config)
        cfg.update(
            {
                "daily_limit_minutes": self.daily.value(),
                "break_after_minutes": self.break_after.value(),
                "break_duration_minutes": self.break_duration.value(),
                "idle_threshold_seconds": self.idle.value(),
                "final_warning_seconds": self.final_seconds.value(),
                "relock_grace_seconds": self.grace.value(),
                "override_minutes": self.override_minutes.value(),
                "reminder_repeat_minutes": self.repeat.value(),
                "allowed_from": self._clock(self.allowed_from),
                "allowed_until": self._clock(self.allowed_until),
                "bedtime_start": self._clock(self.bedtime_start),
                "bedtime_end": self._clock(self.bedtime_end),
                "schedule_enforcement": self.enforce.isChecked(),
                "sound": self.sound.isChecked(),
                "notifications": self.notifications.isChecked(),
                "autostart": self.autostart.isChecked(),
                "school_enabled": self.school_enabled.isChecked(),
                "school_from": self._clock(self.school_from),
                "school_until": self._clock(self.school_until),
                "child_gender": self.gender.currentData() or "",
                "child_name": self.child_name.text().strip(),
                "win_bonus_minutes": self.win_bonus.value(),
                "bonus_daily_cap_minutes": self.bonus_cap.value(),
                "care_enabled": self.care_enabled.isChecked(),
                "care_after_minutes": self.care_after.value(),
                "care_minutes": self.care_minutes.value(),
                "pet_position": next((k for k, r in self.place_radios.items() if r.isChecked()), "free"),
                "selected_skin": self.agent.engine.state.SELECTED_SKIN,
                "routines": routines,
            }
        )
        errors = validate_settings(cfg)
        if errors:
            QMessageBox.warning(self, "Parent Mode", "\n".join(errors))
            return
        self.agent.engine.config.clear()
        self.agent.engine.config.update(cfg)
        self.agent.engine.sync_settings()
        try:
            save_config(self.agent.paths["config"], self.agent.engine.config)
        except OSError as exc:
            log_line(self.agent.paths["log"], f"failed to save config: {exc}")
            QMessageBox.warning(self, "Parent Mode", "Не удалось записать настройки. Приложение продолжает работать.")
            return
        logic.set_profile(self.agent.engine.config)
        self.agent.refresh_views()
        self.agent.companion.apply_placement()
        self.agent.update_tray_icon(force=True)
        QMessageBox.information(self, "Настройка", "Настройки сохранены.")


class ProfileDialog(QDialog):
    """First start: who will the pet look after? One named child (boy / girl) or two children."""

    def __init__(self, parent=None, gender: str = "", name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Знакомство")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        intro = QLabel("С кем будет дружить питомец? От этого зависят имя, обращение и слова похвалы.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.group = QButtonGroup(self)
        self.radios = {}
        for key, label in (("boy", "Мальчик"), ("girl", "Девочка"), ("two", "Двое детей")):
            radio = QRadioButton(label)
            radio.toggled.connect(self._sync)
            self.group.addButton(radio)
            self.radios[key] = radio
            layout.addWidget(radio)
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("Имя ребёнка")
        layout.addWidget(self.name)
        self.hint = QLabel("Для двоих питомец не называет имён: «Привет, ребята!», «Мне пора спать, ребята».")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        row = QHBoxLayout()
        later = QPushButton("Позже")
        later.clicked.connect(self.reject)
        ok = QPushButton("Готово")
        ok.clicked.connect(self._accept)
        row.addStretch(1)
        row.addWidget(later)
        row.addWidget(ok)
        layout.addLayout(row)
        if gender in self.radios:
            self.radios[gender].setChecked(True)
        self._sync()

    def choice(self) -> tuple[str, str]:
        for key, radio in self.radios.items():
            if radio.isChecked():
                return key, ("" if key == "two" else logic.normalize_name(self.name.text()))
        return "", ""

    def _sync(self):
        two = self.radios["two"].isChecked()
        self.name.setEnabled(not two)
        self.hint.setVisible(two)

    def _accept(self):
        gender, name = self.choice()
        if not gender:
            QMessageBox.warning(self, "Знакомство", "Выберите: мальчик, девочка или двое детей.")
            return
        if gender != "two" and not name:
            QMessageBox.warning(self, "Знакомство", "Напишите имя ребёнка.")
            return
        self.accept()


class CareWindow(QDialog):
    """Tamagotchi corner: the child looks after the pet. Time counts only while the child is touching the buttons."""

    ACTIONS = {
        "pet": ("HAPPY", "smile", "Мррр… как приятно!", "purr"),
        "feed": ("EAT", "tongue", "Ням-ням! Очень вкусно!", "pop"),
        "ball": ("EXERCISE", "laugh", "Лови мячик! Ха-ха!", "trill"),
    }

    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        self._last_touch = 0.0
        self.setWindowTitle("Поиграй со мной")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.resize(420, 520)
        root = QVBoxLayout(self)
        self.title = QLabel("Побудь со мной")
        self.title.setStyleSheet("font-size:18px;")
        self.pet = PixelPet()
        self.pet.idle_anim = True
        self.pet.setFixedSize(220, 220)
        self.caption = SayLabel()
        self.caption.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        row = QHBoxLayout()
        for key, label in (("pet", "Погладить"), ("feed", "Покормить"), ("ball", "Мячик")):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, k=key: self._act(k))
            row.addWidget(button)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.hide)
        root.addWidget(self.title)
        root.addWidget(self.pet, 0, Qt.AlignCenter)
        root.addWidget(self.caption)
        root.addWidget(self.bar)
        root.addLayout(row)
        root.addWidget(close)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self.pet.update)
        self._anim.start(90)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._second)
        self._tick.start(1000)
        self._calm = QTimer(self)
        self._calm.setSingleShot(True)
        self._calm.timeout.connect(self._rest)

    def sync(self):
        self.pet.skin = self.agent.engine.state.SELECTED_SKIN
        self._rest()
        self._refresh()

    def _rest(self):
        self.pet.state_name = "REMINDER" if self.agent.engine.state.care_due else "HAPPY"
        self.pet.expression = "" if not self.agent.engine.state.care_due else "sly"
        self.pet.update()

    def _need_seconds(self) -> int:
        return int(self.agent.engine.config["care_minutes"]) * 60

    def _refresh(self):
        state = self.agent.engine.state
        need = self._need_seconds()
        self.bar.setRange(0, need)
        self.bar.setValue(min(state.care_seconds, need))
        left = max(0, need - state.care_seconds)
        if state.care_due:
            self.caption.setText(f"Мне скучно. Поиграй со мной ещё {left // 60}:{left % 60:02d}. Жми кнопки!")
        else:
            self.caption.setText("Мне с тобой хорошо. Можно меня погладить, покормить или бросить мячик.")

    def _act(self, key: str):
        pet_state, face, line, trick = self.ACTIONS[key]
        self._last_touch = time.monotonic()
        self.pet.state_name = pet_state
        self.pet.expression = face
        self.caption.setText(line)
        play_trick(
            self.agent.paths["sounds"],
            self.pet.skin,
            self.agent.pet_voice(),
            trick,
            self.agent.engine.state.SOUND_ENABLED,
        )
        self._calm.start(2500)
        self.pet.update()

    def _second(self):
        if not self.isVisible():
            return
        if time.monotonic() - self._last_touch <= 20:
            if self.agent.care_tick(1):
                self.pet.state_name = "CELEBRATION"
                self.pet.expression = "laugh"
                self.caption.setText(self.agent.engine.state.CURRENT_PET_MESSAGE)
                self._calm.start(5000)
                return
        if not self._calm.isActive():
            self._refresh()


class LessonWindow(QDialog):
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        self.page = 0
        self.spot_buttons: list[QPushButton] = []
        self.game_count = 0
        self.setWindowTitle("Что я умею")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.resize(480, 620)
        root = QVBoxLayout(self)
        self.title = QLabel("Я умею вот что")
        self.title.setStyleSheet("font-size:18px;")
        self.pet = PixelPet()
        self.pet.setFixedSize(160, 160)
        self.caption = SayLabel("Нажми кнопку — и я покажу.")
        self.caption.setObjectName("lessonCaption")
        self.caption.setWordWrap(True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._skills_page())
        self.stack.addWidget(self._games_page())
        self.spots_page = QWidget()
        self.spots_layout = QGridLayout(self.spots_page)
        self.stack.addWidget(self.spots_page)
        self.back = QPushButton("Назад")
        self.next = QPushButton("Дальше")
        close = QPushButton("Закрыть")
        self.back.clicked.connect(lambda: self._go(self.page - 1))
        self.next.clicked.connect(lambda: self._go(self.page + 1))
        close.clicked.connect(self.hide)
        nav = QHBoxLayout()
        nav.addWidget(self.back)
        nav.addWidget(self.next)
        nav.addWidget(close)
        top = QHBoxLayout()
        top.addWidget(self.pet, 0, Qt.AlignTop)
        top.addWidget(self.caption, 1)
        root.addWidget(self.title)
        root.addLayout(top)
        root.addWidget(self.stack, 1)
        root.addLayout(nav)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.pet.update)
        self._timer.start(90)
        self.sync_pet()

    def _skills_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        hint = QLabel("Правая кнопка по мне на рабочем столе снова открывает это окошко.")
        hint.setWordWrap(True)
        grid.addWidget(hint, 0, 0, 1, 2)
        for index, item in enumerate(SHOW_OFFS):
            button = QPushButton(item[0])
            button.clicked.connect(lambda _checked=False, number=index: self._demo(number))
            grid.addWidget(button, index // 2 + 1, index % 2)
        return page

    def _games_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        form = QVBoxLayout(host)
        for name, text in GAME_LESSONS.items():
            self.game_count += 1
            title = QLabel(name)
            title.setStyleSheet("font-size:15px;")
            body = QLabel(text)
            body.setWordWrap(True)
            play = QPushButton("Играть")
            play.clicked.connect(lambda _checked=False, game=name: self.agent.launch_game(game))
            form.addWidget(title)
            form.addWidget(body)
            form.addWidget(play)
        form.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll)
        return page

    def _fill_spots(self):
        while self.spots_layout.count():
            item = self.spots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.spot_buttons = []
        kind = resolve_skin(self.pet.skin)[1]
        for index, (label, trick, line, face) in enumerate(spots_for(kind)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, sound=trick, words=line, look=face: self._spot(sound, words, look))
            self.spots_layout.addWidget(button, index // 2, index % 2)
            self.spot_buttons.append(button)

    def sync_pet(self):
        self.pet.skin = self.agent.engine.state.SELECTED_SKIN
        self._fill_spots()
        self._go(self.page)

    def _go(self, page: int):
        self.page = max(0, min(2, page))
        self.stack.setCurrentIndex(self.page)
        titles = ["Я умею вот что", "Игры", "Ты можешь меня рассмешить"]
        self.title.setText(titles[self.page])
        self.back.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < 2)
        if self.page == 0:
            self.caption.setText("Нажми кнопку — и я покажу, что умею.")
            self.pet.expression = "smile"
            self.pet.state_name = "HAPPY"
        elif self.page == 1:
            self.caption.setText("В каждой игре написано, что нажимать. Я рядом.")
            self.pet.expression = "smile"
            self.pet.state_name = "PLAY"
        else:
            self.caption.setText("Нажми, куда меня пощекотать. У меня свой звук.")
            self.pet.expression = "smile"
            self.pet.state_name = "HAPPY"

    def _play(self, trick: str):
        play_trick(
            self.agent.paths["sounds"],
            self.pet.skin,
            self.agent.pet_voice(),
            trick,
            self.agent.engine.state.SOUND_ENABLED,
        )

    def _demo(self, index: int):
        _label, trick, line, face, state = SHOW_OFFS[index]
        self.pet.expression = face
        self.pet.state_name = state
        self.caption.setText(line)
        self.pet.update()
        self._play(trick)

    def _spot(self, trick: str, line: str, face: str):
        self.pet.expression = face
        self.pet.state_name = "HAPPY"
        self.caption.setText(line)
        self.pet.update()
        self._play(trick)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class Agent(QObject):
    def __init__(self, app: QApplication, root: Path = ROOT, locker=None, idle_provider=None, now_provider=None):
        super().__init__()
        self.app = app
        app.setQuitOnLastWindowClosed(False)
        self.root = Path(root)
        self.paths = configure_paths(self.root)
        self.locker = locker or logic.lock_workstation
        self.idle_provider = idle_provider or logic.query_idle_seconds
        self.now_provider = now_provider or datetime.now
        self.games: list[MiniGame] = []
        self.autostart_error = ""
        self._ticks = 0
        self._last_tip = ""
        self._icon_key = None
        self._startup_pending = True
        self._stopping = False
        self.tray = None
        self.lesson = None
        self.care = None
        try:
            ensure_sounds(self.paths["sounds"])
        except Exception:
            log_exception(self.paths["log"], "missing sound")
        today = self.now_provider().date().isoformat()
        try:
            config, state, stats = load_persistence(self.paths, today)
        except Exception:
            log_exception(self.paths["log"], "persistence")
            config = logic.default_config()
            state = CentralState(day=today)
            stats = logic.empty_stats()
        self.engine = PolicyEngine(config, state, stats)
        logic.set_profile(config)
        ensure_pin_file(self.paths["pin"])
        self.engine.pin_file = self.paths["pin"]
        state.CURRENT_PET_MESSAGE = MSG_START
        state.CURRENT_PET_STATE = "HAPPY"
        try:
            export_skin_catalog(self.paths["skins"])
        except Exception:
            log_exception(self.paths["log"], "missing skin asset, using default drawing")
        self.companion = CompanionWindow(self)
        self.dashboard = Dashboard(self)
        self.overlay = CountdownOverlay(self.prompt_override)
        self.anim = QTimer(self)
        self.anim.timeout.connect(self._animate)
        self.anim.start(140)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(1000)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.show_companion)
        self._setup_tray()
        icon = icon_for(state.SELECTED_SKIN, state.CURRENT_PET_STATE, state.visual)
        app.setWindowIcon(icon)
        if not self.school_active():
            self.companion.apply_state(state)
        else:
            self.companion.hide()
            self.overlay.hide()
        self.dashboard.apply_state(state, self.engine)
        self._set_tooltip(state.CURRENT_PET_MESSAGE)
        if self.school_active():
            self.companion.hide()
        else:
            self.companion.show()
        log_line(self.paths["log"], "agent started")
        if not self.school_active() and not os.environ.get("KIDS_NO_PROMPT") and not config.get("child_gender"):
            QTimer.singleShot(800, self.ensure_profile)
        QTimer.singleShot(8000, self._finish_startup)

    def _animate(self):
        self.companion.pet.update()
        for pet in self.dashboard.pet_previews:
            pet.update()

    def _setup_tray(self):
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                raise RuntimeError("system tray unavailable")
            tray = QSystemTrayIcon(self)
            tray.setIcon(icon_for(self.engine.state.SELECTED_SKIN))
            from PySide6.QtWidgets import QMenu

            menu = QMenu(self.dashboard)
            self.menu = menu
            menu.addAction("Открыть", self.show_dashboard)
            menu.addAction("Показать питомца", self.show_companion)
            menu.addAction("Мини-игры", self.open_games)
            menu.addAction("Что я умею", self.open_lesson)
            menu.addAction("Parent Mode", self.prompt_parent)
            menu.addSeparator()
            menu.addAction("Выход", self.prompt_exit)
            tray.setContextMenu(menu)
            tray.activated.connect(self._tray_activated)
            tray.show()
            self.tray = tray
            self.update_tray_icon(force=True)
        except Exception:
            log_exception(self.paths["log"], "tray initialization error")
            self.tray = None
            self.dashboard.show()

    def _tray_activated(self, reason):
        trigger = QSystemTrayIcon.ActivationReason.Trigger
        double = QSystemTrayIcon.ActivationReason.DoubleClick
        if reason == double:
            self._click_timer.stop()
            self.show_dashboard()
        elif reason == trigger:
            self._click_timer.start(250)

    def _set_tooltip(self, message: str):
        tip = tooltip_for(say(message or MSG_OK))
        self._last_tip = tip
        if self.tray is not None:
            self.tray.setToolTip(tip)

    def update_tray_icon(self, force: bool = False):
        state = self.engine.state
        key = (state.SELECTED_SKIN, state.CURRENT_PET_STATE, state.visual)
        if not force and key == self._icon_key:
            return
        self._icon_key = key
        icon = icon_for(state.SELECTED_SKIN, state.CURRENT_PET_STATE, state.visual)
        self.app.setWindowIcon(icon)
        self.companion.setWindowIcon(icon)
        self.dashboard.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)

    def show_companion(self):
        was_hidden = not self.companion.isVisible()
        self.companion.show()
        self.companion.raise_()
        self.companion.activateWindow()
        if was_hidden and not self.companion.blocked():
            self.companion.greet()
        else:
            self.companion._parked = False
            self.companion.arm_hide()

    def show_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def open_games(self):
        dialog = QDialog(self.dashboard)
        dialog.setWindowTitle("Мини-игры")
        grid = QGridLayout(dialog)
        for index, name in enumerate(GAME_NAMES):
            button = QPushButton(name)
            button.clicked.connect(lambda _checked=False, game=name, host=dialog: (self.launch_game(game), host.accept()))
            grid.addWidget(button, index // 2, index % 2)
        dialog.resize(420, 320)
        dialog.exec()

    def on_game_win(self, minutes: int) -> int:
        effects = self.engine.grant_bonus(minutes)
        self._handle_effects(effects)
        self.refresh_views()
        self.persist()
        return self.engine.last_bonus

    def open_care(self):
        if getattr(self, "care", None) is None:
            self.care = CareWindow(self)
        self.care.sync()
        self.care.show()
        self.care.raise_()
        self.care.activateWindow()
        self.companion.arm_hide()

    def care_tick(self, seconds: int):
        before = self.engine.state.care_done_today
        effects = self.engine.add_care_seconds(seconds, self.now_provider())
        self._handle_effects(effects)
        self.refresh_views()
        if self.engine.state.care_done_today != before:
            self.persist()
            return True
        return False

    def apply_profile(self, gender: str, name: str):
        self.engine.config["child_gender"] = logic.normalize_gender(gender)
        self.engine.config["child_name"] = logic.normalize_name(name) if gender != "two" else ""
        logic.set_profile(self.engine.config)
        self.persist()
        panel = getattr(self.dashboard, "settings_page", None)
        if panel is not None:
            index = panel.gender.findData(self.engine.config["child_gender"])
            panel.gender.setCurrentIndex(max(0, index))
            panel.child_name.setText(self.engine.config["child_name"])

    def ensure_profile(self) -> bool:
        if self._stopping or self.school_active():
            return False
        """Ask the parent who the pet looks after (first start, and before the first game if skipped)."""
        if self.engine.config.get("child_gender") in ("boy", "girl", "two"):
            return True
        dialog = ProfileDialog(self.dashboard, self.engine.config.get("child_gender", ""), self.engine.config.get("child_name", ""))
        if dialog.exec() != QDialog.Accepted:
            return False
        gender, name = dialog.choice()
        self.apply_profile(gender, name)
        self.engine.state.CURRENT_PET_MESSAGE = MSG_START
        self.companion.show_system(MSG_START)
        return True

    def ensure_gender(self) -> bool:
        return self.ensure_profile()

    def launch_game(self, name: str):
        if not self.ensure_gender():
            return
        try:
            game = MiniGame(
                name,
                sound_enabled=lambda: self.engine.state.SOUND_ENABLED,
                sounds_dir=self.paths["sounds"],
                voice=self.pet_voice(),
                skin=lambda: self.engine.state.SELECTED_SKIN,
                gender=lambda: self.engine.config.get("child_gender", ""),
                on_win=self.on_game_win,
                bonus_minutes=lambda: self.engine.config.get("win_bonus_minutes", 5),
                on_crash=self._game_crashed,
                on_close=self._forget_game,
                log_path=self.paths["log"],
            )
            self.games.append(game)
            game.show()
            game.raise_()
            game.activateWindow()
            self.refresh_views()
        except Exception:
            log_exception(self.paths["log"], f"game crash: {name}")
            QMessageBox.warning(self.dashboard, "Мини-игра", "Игра закрыта из-за ошибки. Питомец продолжает работать.")

    def _game_crashed(self, name: str):
        QMessageBox.warning(self.dashboard, "Мини-игра", "Игра закрыта из-за ошибки. Питомец продолжает работать.")

    def _forget_game(self, game: MiniGame):
        self.games = [item for item in self.games if item is not game]
        self.refresh_views()

    def pause_games(self):
        for game in list(self.games):
            try:
                game.pause()
            except RuntimeError:
                pass

    def resume_games(self):
        for game in list(self.games):
            try:
                game.resume()
            except RuntimeError:
                pass

    def school_active(self):
        return logic.school_active(self.now_provider(), self.engine.config)

    def refresh_views(self):
        state = self.engine.state
        if self.games and state.CURRENT_PET_STATE in ("HAPPY", "IDLE") and not state.break_due and not state.countdown_started:
            state.CURRENT_PET_STATE = "PLAY"
        if not self.school_active():
            self.companion.apply_state(state)
        else:
            self.companion.hide()
            self.overlay.hide()
        self.dashboard.apply_state(state, self.engine)
        tip = tooltip_for(say(state.CURRENT_PET_MESSAGE or MSG_OK))
        if tip != self._last_tip:
            self._set_tooltip(state.CURRENT_PET_MESSAGE or MSG_OK)
        self.update_tray_icon()

    def _show_notice(self, text: str, sound_name: str | None, notify: bool, title: str):
        if self._stopping or self.school_active():
            return
        self._startup_pending = False
        text = say(text)
        if sound_name and self.engine.state.SOUND_ENABLED:
            play(self.paths["sounds"], f"{sound_name}.wav", True)
        if notify and self.engine.state.notifications_enabled and self.tray is not None:
            try:
                self.tray.showMessage(title or "TechnoLab", text, QSystemTrayIcon.MessageIcon.Information, 4000)
            except Exception:
                log_exception(self.paths["log"], "notification")
        self.refresh_views()

    def _handle_effects(self, effects):
        for effect in effects:
            kind = effect.kind
            if kind == "message":
                self._show_notice(
                    effect.data.get("text", ""),
                    effect.data.get("sound") or None,
                    bool(effect.data.get("notify")),
                    effect.data.get("title") or "TechnoLab",
                )
            elif kind == "countdown_start":
                self._startup_pending = False
                self.overlay.present(effect.data.get("text", ""))
                self.pause_games()
                self.refresh_views()
            elif kind == "countdown_tick":
                self.overlay.label.setText(effect.data.get("text", ""))
                self.refresh_views()
            elif kind == "countdown_cancel":
                self.overlay.hide()
                self.resume_games()
            elif kind == "lock":
                self.overlay.hide()
                self._do_lock()

    def _do_lock(self):
        if self._stopping or self.school_active():
            return
        if not self.engine.state.child_locked:
            log_line(self.paths["log"], "lock skipped: child lock is off")
            return
        if self.engine.override_active(self.now_provider()):
            log_line(self.paths["log"], "lock skipped: parent PIN override is active")
            return
        try:
            ok = bool(self.locker())
            if not ok:
                log_line(self.paths["log"], "LockWorkStation returned false")
        except Exception:
            log_exception(self.paths["log"], "lock")

    def on_tick(self):
        if self._stopping:
            return
        try:
            effects = self.engine.tick(self.now_provider(), self.idle_provider())
            self._handle_effects(effects)
            self.refresh_views()
            self._ticks += 1
            if self._ticks % 10 == 0:
                self.persist()
        except Exception:
            log_exception(self.paths["log"], "tick")

    def _finish_startup(self):
        if self._stopping or self.school_active() or not self._startup_pending:
            return
        self._startup_pending = False
        text = self.engine.reveal_status(self.now_provider())
        if text:
            self.refresh_views()

    def acknowledge(self):
        effects = self.engine.acknowledge(self.now_provider())
        self._handle_effects(effects)
        self.refresh_views()
        self.persist()

    def apply_override(self):
        effects = self.engine.grant_override(self.now_provider(), logic.OVERRIDE_INDEFINITE_MINUTES)
        self._handle_effects(effects)
        self.refresh_views()
        self.persist()

    def resume_control(self):
        self.engine.resume_control()
        self.refresh_views()
        self.persist()

    def prompt_override(self):
        self.engine.state.countdown_paused = True
        try:
            pin, ok = QInputDialog.getText(self.overlay, "Родитель", "PIN:", QLineEdit.Password)
        finally:
            self.engine.state.countdown_paused = False
        if not ok:
            return
        if not self.engine.pin_ok(pin):
            QMessageBox.warning(self.overlay, "PIN", "Неверный PIN.")
            return
        self.apply_override()

    def _ask_pin(self, title: str) -> tuple[str, bool]:
        parent = self.overlay if self.overlay.isVisible() else self.dashboard
        return QInputDialog.getText(parent, title, "Родительский PIN:", QLineEdit.Password)

    def on_pet_clicked(self):
        if self.companion.mode == "laugh":
            self.companion.poke()
            return
        state = self.engine.state
        if state.countdown_started:
            self.companion.show_system(state.CURRENT_PET_MESSAGE or MSG_OK)
            return
        if state.pending_routine_title or (state.break_due and not state.break_acknowledged):
            self.companion.show_system(state.CURRENT_PET_MESSAGE or MSG_OK, ack=True)
            return
        self.companion.greet()

    def pet_voice(self) -> str:
        return voice_for(self.engine.state.SELECTED_SKIN)

    def open_lesson(self):
        if self.lesson is None:
            self.lesson = LessonWindow(self)
        self.lesson.sync_pet()
        self.lesson.show()
        self.lesson.raise_()
        self.lesson.activateWindow()
        self.companion.arm_hide()

    def remember_line(self, text: str):
        self.engine.state.CURRENT_PET_MESSAGE = text
        self._set_tooltip(text)

    def choose_skin(self, name: str):
        if self.engine.state.child_locked or name not in SKIN_NAMES:
            return
        self.engine.config["selected_skin"] = name
        self.engine.sync_settings()
        try:
            save_config(self.paths["config"], self.engine.config)
        except OSError as exc:
            log_line(self.paths["log"], f"failed to save skin: {exc}")
        self.refresh_views()
        self.update_tray_icon(force=True)
        self.companion.show_system(f"Теперь я {name}. Буду рядом и помогу.")
        if self.lesson is not None and self.lesson.isVisible():
            self.lesson.sync_pet()

    def set_child_locked(self, locked: bool):
        self.engine.state.child_locked = bool(locked)
        self.persist()
        self.dashboard.refresh_lock()
        if locked:
            self.companion.show_system("Я с тобой. Можем поиграть или посмеяться.")
        else:
            self.companion.show_system("Настройки снова открыты.")

    def change_password(self, new_pin: str, confirm: str) -> str:
        error = validate_new_pin(new_pin, confirm)
        if error:
            return error
        cleaned = new_pin.strip()
        try:
            write_pin_file(self.paths["pin"], cleaned)
            self.engine.config["parent_pin_hash"] = logic.hash_pin(cleaned)
            save_config(self.paths["config"], self.engine.config)
        except OSError as exc:
            log_line(self.paths["log"], f"failed to save pin: {exc}")
            return "Не удалось записать пароль."
        return ""

    def prompt_parent(self):
        self.show_dashboard()
        self.dashboard.refresh_lock()
        if not self.engine.state.child_locked:
            self.dashboard.tabs.setCurrentIndex(0)

    def prompt_exit(self):
        pin, ok = self._ask_pin("Выход")
        if not ok:
            return
        self.request_exit_with_pin(pin, notify=True)

    def request_exit_with_pin(self, pin: str, notify: bool = False) -> bool:
        if not self.engine.pin_ok(pin):
            if notify:
                QMessageBox.warning(self.dashboard, "PIN", "Неверный PIN. Приложение продолжает работать.")
            return False
        self.shutdown()
        return True

    def persist(self):
        try:
            save_persistence(self.paths, self.engine.config, self.engine.state, self.engine.stats)
        except Exception:
            log_exception(self.paths["log"], "save")

    def prompt_uninstall(self):
        pin, accepted = self._ask_pin("Удаление программы")
        if not accepted:
            return
        if not self.engine.pin_ok(pin):
            QMessageBox.warning(self.dashboard, "PIN", "Неверный PIN.")
            return
        from setup_wizard import schedule_uninstall
        if QMessageBox.question(self.dashboard, "Удаление программы",
                "Удалить программу, настройки, пароль и статистику с этого компьютера?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            schedule_uninstall(self.root)
        except Exception as exc:
            QMessageBox.warning(self.dashboard, "Удаление", str(exc))
            return
        self.shutdown()

    def shutdown(self):
        if self._stopping:
            return
        self._stopping = True
        for owner in (self, *self.app.topLevelWidgets()):
            for timer in owner.findChildren(QTimer):
                timer.stop()
        self.pause_games()
        self.overlay.hide()
        for window in self.app.topLevelWidgets():
            window.hide()
        if self.tray is not None:
            self.tray.hide()
        import sound
        if sound.winsound is not None:
            sound.winsound.PlaySound(None, 0)
        self.persist()
        log_line(self.paths["log"], "agent exit")
        self.app.quit()


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--self-test" in argv:
        import unittest

        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if FROZEN and not (ROOT / "installed.flag").exists():
        from setup_wizard import run_setup

        return run_setup(argv)
    _app_id()
    app = QApplication(argv)
    app.setApplicationName("TechnoLab Kids Companion")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    import hashlib
    server_name = "TechnoLabKids-" + hashlib.sha256(str(ROOT.resolve()).lower().encode()).hexdigest()[:24]
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        socket.write(b"uninstall" if "--uninstall" in argv else b"open")
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return 0
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(server_name):
        QMessageBox.warning(None, "Kids Companion", "Программа уже запускается. Повторите попытку.")
        return 1
    agent = Agent(app, ROOT)
    def connected():
        client = server.nextPendingConnection()
        def receive():
            command = bytes(client.readAll())
            client.disconnectFromServer()
            client.deleteLater()
            if command == b"uninstall":
                agent.prompt_uninstall()
            elif command == b"open":
                agent.show_dashboard()
        client.readyRead.connect(receive)
        if client.bytesAvailable():
            receive()
    server.newConnection.connect(connected)
    if "--uninstall" in argv:
        QTimer.singleShot(0, agent.prompt_uninstall)
    app.aboutToQuit.connect(agent.persist)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
