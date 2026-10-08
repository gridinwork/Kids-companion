"""Policy, persistence and parent PIN for TechnoLab Agent №3.

The agent stores active/idle duration and schedule state only.
It does not read keystrokes, passwords, messages, documents or screen content.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

MSG_START = "Привет! Я твой питомец и друг. Присмотришь за мной сегодня?"
MSG_OK = "Я рядом. Если захочешь, поиграем."
MSG_BREAK = "Я немного устал. Давай вместе отдохнём и разомнёмся?"
MSG_30 = "Мне через полчаса пора спать. Давай ещё немного побудем вместе."
MSG_5 = "Я уже зеваю. Мне пора спать через пять минут."
MSG_ACK_BREAK = "Спасибо! Давай отдохнём вместе, а я посчитаю."
MSG_ACK_ROUTINE = "Ура, мы это сделали вместе!"
MSG_BREAK_DONE = "Ура, мы отдохнули! Я снова бодрый."
MSG_OVERRIDE = "Можно ещё немного побыть вместе."
MSG_TIME_UP = "Мне пора отдыхать. Я устал, давай закончим на сегодня."
MSG_BEDTIME_UP = "Мне уже пора спать. Давай закончим, спокойной ночи!"
MSG_BONUS_LIMIT = "Мы уже получили весь бонус на сегодня. Больше времени не будет."
MSG_LOCKED = "Я засыпаю. Мне пора спать, увидимся позже."
TOOLTIP_PREFIX = "TechnoLab Kids Companion — "
DEFAULT_PIN = "0000"
OVERRIDE_INDEFINITE_MINUTES = 365 * 24 * 60

SKIN_NAMES = [
    "Пантера",
    "Собака",
    "Кот",
    "Зайчик",
    "Единорог",
    "Лисёнок",
    "Дракончик",
    "Робот",
    "Динозаврик",
    "Ниндзя",
]
LEGACY_SKINS = {
    "Pixel Cat": "Кот",
    "Pixel Bunny": "Зайчик",
    "Pixel Fox": "Лисёнок",
    "Pixel Panda": "Собака",
    "Панда": "Собака",
    "Pixel Unicorn": "Единорог",
    "Pixel Dragon": "Дракончик",
    "Pixel Robot": "Робот",
    "Pixel Dino": "Динозаврик",
    "Pixel Ninja": "Ниндзя",
}


def canonical_skin(name: str | None) -> str:
    if name in SKIN_NAMES:
        return str(name)
    if name in LEGACY_SKINS:
        return LEGACY_SKINS[str(name)]
    return "Пантера"


# boy / girl are lighter child voices, man / woman are lower character voices.
PET_VOICES = {
    "Пантера": "man",
    "Кот": "man",
    "Зайчик": "boy",
    "Лисёнок": "boy",
    "Собака": "girl",
    "Единорог": "woman",
    "Дракончик": "boy",
    "Робот": "man",
    "Динозаврик": "boy",
    "Ниндзя": "man",
}


def voice_for(skin: str | None) -> str:
    return PET_VOICES.get(canonical_skin(skin), "boy")

DEFAULT_ROUTINES = [
    {
        "time": "13:00",
        "title": "Обед",
        "message": "Я проголодался! Давай вместе пообедаем.",
        "repeat_minutes": 10,
        "kind": "meal",
    },
    {
        "time": "18:00",
        "title": "Зарядка",
        "message": "Давай немного разомнёмся вместе!",
        "repeat_minutes": 5,
        "kind": "exercise",
    },
    {
        "time": "19:00",
        "title": "Ужин",
        "message": "Я хочу кушать. Давай вместе поужинаем.",
        "repeat_minutes": 10,
        "kind": "meal",
    },
    {
        "time": "20:00",
        "title": "Душ",
        "message": "Мне пора купаться. Пойдём вместе помоемся?",
        "repeat_minutes": 10,
        "kind": "shower",
    },
    {
        "time": "21:30",
        "title": "Сон",
        "message": "Мне пора спать. Давай вместе готовиться ко сну.",
        "repeat_minutes": 5,
        "kind": "bedtime",
    },
]


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def normalize_gender(value) -> str:
    """boy / girl: one child. two: two children, the pet speaks to both ("ребята", "вы")."""
    return value if value in ("boy", "girl", "two") else ""


def normalize_name(value) -> str:
    return " ".join(str(value or "").split())[:24]


# who the pet is talking to; set from the saved config by set_profile()
_PROFILE = {"gender": "", "name": ""}

_PLURAL_WORDS = [
    ("Давай", "Давайте"), ("давай", "давайте"), ("Пойдём", "Пойдёмте"), ("Присмотришь", "Присмотрите"),
    ("захочешь", "захотите"), ("Хочешь", "Хотите"), ("Поиграй", "Поиграйте"), ("Щекочи", "Щекочите"),
    ("Пощекочешь", "Пощекочете"), ("Жми", "Жмите"), ("Лови", "Ловите"), ("Смотри", "Смотрите"),
    ("Нажми", "Нажмите"), ("Беги", "Бегите"), ("Дойди", "Дойдите"), ("Открывай", "Открывайте"),
    ("Объезжай", "Объезжайте"), ("Пробеги", "Пробегите"), ("Поворачивай", "Поворачивайте"),
    ("Ешь", "Ешьте"), ("перепрыгивай", "перепрыгивайте"), ("врежься", "врежьтесь"),
    ("твой", "ваш"), ("тебе", "вам"), ("тебя", "вас"), ("тобой", "вами"), ("тебя", "вас"), ("Ты", "Вы"),
]
_PLURAL_PREFIX_TEXTS = {
    "Мне через полчаса пора спать. Давай ещё немного побудем вместе.",
    "Я уже зеваю. Мне пора спать через пять минут.",
    "Я засыпаю. Мне пора спать, увидимся позже.",
    "Мне пора отдыхать. Я устал, давай закончим на сегодня.",
    "Мне уже пора спать. Давай закончим, спокойной ночи!",
}


def set_profile(cfg: dict) -> None:
    _PROFILE["gender"] = normalize_gender(cfg.get("child_gender"))
    _PROFILE["name"] = normalize_name(cfg.get("child_name"))


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def say(text: str) -> str:
    """Adapt the pet's words to who is listening: one named child, or two children."""
    gender, name = _PROFILE["gender"], _PROFILE["name"]
    if gender == "two":
        if text.startswith("Привет!"):
            text = "Привет, ребята!" + text[len("Привет!"):]
        elif text in _PLURAL_PREFIX_TEXTS or text.startswith("Мне скучно"):
            text = "Ребята, " + _lower_first(text)
        for single, plural in _PLURAL_WORDS:
            text = re.sub(rf"(?<![А-Яа-яЁё]){single}(?![А-Яа-яЁё])", plural, text)
    elif name:
        if text.startswith("Привет!"):
            text = f"Привет, {name}!" + text[len("Привет!"):]
        elif text.startswith("Мне скучно"):
            text = f"{name}, " + _lower_first(text)
    return text


def praise(gender: str | None, name: str | None = None) -> str:
    """Praise in the right grammatical form for who plays."""
    base = {"boy": "Ты молодец", "girl": "Ты умница", "two": "Вы молодцы"}.get(gender or "")
    if not base:
        return "Отлично!"
    if name is None and gender == _PROFILE["gender"]:
        name = _PROFILE["name"]
    return f"{base}, {name}!" if name and gender != "two" else f"{base}!"


def default_config() -> dict:
    return {
        "version": "0.3.0",
        "parent_pin_hash": hash_pin(DEFAULT_PIN),
        "break_after_minutes": 50,
        "break_duration_minutes": 10,
        "daily_limit_minutes": 180,
        "idle_threshold_seconds": 120,
        "lock_warnings_minutes": [30, 5],
        "final_warning_seconds": 30,
        "relock_grace_seconds": 180,
        "override_minutes": 15,
        "reminder_repeat_minutes": 5,
        "allowed_from": "07:00",
        "allowed_until": "23:00",
        "bedtime_start": "23:00",
        "bedtime_end": "07:00",
        "schedule_enforcement": True,
        "routines": deepcopy(DEFAULT_ROUTINES),
        "selected_skin": "Пантера",
        "sound": True,
        "notifications": True,
        "autostart": False,
        "school_enabled": True,
        "school_from": "08:45",
        "school_until": "13:00",
        "child_gender": "",
        "child_name": "",
        "win_bonus_minutes": 5,
        "bonus_daily_cap_minutes": 15,
        "pet_position": "free",
        "pet_x": -1,
        "pet_y": -1,
        "care_enabled": True,
        "care_after_minutes": 60,
        "care_minutes": 5,
    }


def countdown_message(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return (
        "Мне пора спать, я засыпаю через "
        f"{seconds // 60:02d}:{seconds % 60:02d}. Давай сохраним игру."
    )


def care_message(minutes: int) -> str:
    return f"Мне скучно без тебя. Поиграй со мной {int(minutes)} мин!"


def care_done_message(gender: str | None) -> str:
    done = {"boy": "поиграл", "girl": "поиграла"}.get(gender or "", "поиграли")
    return f"Ура! Мне было очень весело. Спасибо, что {done} со мной!"


def tooltip_for(message: str) -> str:
    line = " ".join((message or "").split())
    return f"{TOOLTIP_PREFIX}{line}"


def fmt_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _clamp_int(value, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _clock_ok(value: str) -> bool:
    try:
        datetime.strptime(str(value), "%H:%M")
        return True
    except ValueError:
        return False


def infer_kind(title: str) -> str:
    text = (title or "").casefold()
    if any(word in text for word in ("заряд", "размин", "exercise", "спорт")):
        return "exercise"
    if any(word in text for word in ("душ", "купан", "shower")):
        return "shower"
    if any(word in text for word in ("сон", "спать", "bed", "ноч")):
        return "bedtime"
    return "custom"


def _clean_routines(value) -> list:
    if not isinstance(value, list):
        return deepcopy(DEFAULT_ROUTINES)
    cleaned = []
    for item in value:
        if not isinstance(item, dict) or not _clock_ok(item.get("time", "")):
            continue
        title = str(item.get("title", "")).strip() or "Напоминание"
        message = str(item.get("message", "")).strip() or "Давай сделаем запланированное дело."
        kind = str(item.get("kind", "")).strip().lower() or infer_kind(title)
        if kind not in ("exercise", "shower", "bedtime", "custom"):
            kind = infer_kind(title)
        cleaned.append(
            {
                "time": str(item["time"]),
                "title": title,
                "message": message,
                "repeat_minutes": _clamp_int(item.get("repeat_minutes", 5), 5, 1, 180),
                "kind": kind,
            }
        )
    return cleaned or deepcopy(DEFAULT_ROUTINES)


def normalize_config(raw) -> tuple[dict, bool]:
    """Return config and whether the parent PIN was reset to the default."""
    cfg = default_config()
    pin_reset = True
    if isinstance(raw, dict):
        for key in (
            "break_after_minutes",
            "break_duration_minutes",
            "daily_limit_minutes",
            "idle_threshold_seconds",
            "final_warning_seconds",
            "relock_grace_seconds",
            "override_minutes",
            "reminder_repeat_minutes",
        ):
            cfg[key] = _clamp_int(raw.get(key, cfg[key]), cfg[key], 1 if key != "idle_threshold_seconds" else 15, 100000)
        cfg["break_after_minutes"] = _clamp_int(raw.get("break_after_minutes", 50), 50, 1, 600)
        cfg["break_duration_minutes"] = _clamp_int(raw.get("break_duration_minutes", 10), 10, 1, 180)
        cfg["daily_limit_minutes"] = _clamp_int(raw.get("daily_limit_minutes", 180), 180, 1, 1440)
        cfg["idle_threshold_seconds"] = _clamp_int(raw.get("idle_threshold_seconds", 120), 120, 15, 3600)
        cfg["final_warning_seconds"] = _clamp_int(raw.get("final_warning_seconds", 30), 30, 10, 120)
        cfg["relock_grace_seconds"] = _clamp_int(raw.get("relock_grace_seconds", 180), 180, 30, 3600)
        cfg["override_minutes"] = _clamp_int(raw.get("override_minutes", 15), 15, 1, 240)
        cfg["reminder_repeat_minutes"] = _clamp_int(raw.get("reminder_repeat_minutes", 5), 5, 1, 180)
        for key in ("allowed_from", "allowed_until", "bedtime_start", "bedtime_end", "school_from", "school_until"):
            if _clock_ok(raw.get(key, "")):
                cfg[key] = str(raw[key])
        if "schedule_enforcement" in raw:
            cfg["schedule_enforcement"] = bool(raw["schedule_enforcement"])
        if "sound" in raw:
            cfg["sound"] = bool(raw["sound"])
        if "notifications" in raw:
            cfg["notifications"] = bool(raw["notifications"])
        if "school_enabled" in raw:
            cfg["school_enabled"] = bool(raw["school_enabled"])
        if cfg["school_from"] >= cfg["school_until"]:
            cfg["school_from"], cfg["school_until"] = "08:45", "13:00"
        if "autostart" in raw:
            cfg["autostart"] = bool(raw["autostart"])
        cfg["selected_skin"] = canonical_skin(str(raw.get("selected_skin") or ""))
        cfg["child_gender"] = normalize_gender(raw.get("child_gender"))
        cfg["child_name"] = normalize_name(raw.get("child_name"))
        cfg["win_bonus_minutes"] = _clamp_int(raw.get("win_bonus_minutes", 5), 5, 0, 60)
        cfg["bonus_daily_cap_minutes"] = _clamp_int(raw.get("bonus_daily_cap_minutes", 15), 15, 0, 240)
        cfg["care_after_minutes"] = _clamp_int(raw.get("care_after_minutes", 60), 60, 1, 600)
        cfg["care_minutes"] = _clamp_int(raw.get("care_minutes", 5), 5, 1, 60)
        cfg["pet_x"] = _clamp_int(raw.get("pet_x", -1), -1, -1, 20000)
        cfg["pet_y"] = _clamp_int(raw.get("pet_y", -1), -1, -1, 20000)
        if raw.get("pet_position") in ("free", "bottom_right", "bottom_left"):
            cfg["pet_position"] = raw["pet_position"]
        if "care_enabled" in raw:
            cfg["care_enabled"] = bool(raw["care_enabled"])
        warnings = raw.get("lock_warnings_minutes")
        if isinstance(warnings, list) and warnings:
            cleaned = []
            for item in warnings:
                try:
                    cleaned.append(int(item))
                except (TypeError, ValueError):
                    continue
            if cleaned:
                cfg["lock_warnings_minutes"] = sorted(set(cleaned), reverse=True)
        cfg["routines"] = _clean_routines(raw.get("routines"))
        stored = raw.get("parent_pin_hash")
        if isinstance(stored, str) and len(stored) == 64 and all(c in "0123456789abcdef" for c in stored.lower()):
            cfg["parent_pin_hash"] = stored.lower()
            pin_reset = False
        else:
            cfg["parent_pin_hash"] = hash_pin(DEFAULT_PIN)
            pin_reset = True
    cfg["version"] = "0.3.0"
    return cfg, pin_reset


def public_config(cfg: dict) -> dict:
    return {key: cfg[key] for key in default_config()}


class Effect:
    def __init__(self, kind: str, **data):
        self.kind = kind
        self.data = data

    def __repr__(self) -> str:
        return f"Effect({self.kind!r}, {self.data!r})"


class CentralState:
    """Single source of truth shared by the pet, tray and dashboard."""

    def __init__(self, day: str | None = None):
        self.day = day or ""
        self.CURRENT_PET_MESSAGE = ""
        self.CURRENT_PET_STATE = "HAPPY"
        self.SELECTED_SKIN = "Пантера"
        self.child_locked = False
        self.last_limit_notify = ""
        self.bonus_today_seconds = 0
        self.care_due = False
        self.care_seconds = 0
        self.active_since_care = 0
        self.care_done_today = 0
        self.last_care_notify = ""
        self.ACTIVE_SECONDS_TODAY = 0
        self.CONTINUOUS_ACTIVE_SECONDS = 0
        self.IDLE_SECONDS = 0.0
        self.DAILY_LIMIT = 180
        self.BREAK_INTERVAL = 50
        self.BREAK_DURATION = 10
        self.NEXT_ROUTINE = ""
        self.SOUND_ENABLED = True
        self.LOCK_STATE = "none"
        self.PARENT_OVERRIDE_STATE = False
        self.longest_session_seconds = 0
        self.breaks = 0
        self.routines_completed: list[str] = []
        self.warned: list[str] = []
        self.countdown_started = False
        self.countdown_left = 0
        self.countdown_paused = False
        self.locked = False
        self.override_until = ""
        self.break_due = False
        self.break_acknowledged = False
        self.last_break_notify = ""
        self.routine_last_notify: dict[str, str] = {}
        self.pending_routine_title = ""
        self.post_lock_anchor = ""
        self.alert_until = ""
        self.visual = ""
        self.notifications_enabled = True

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "CURRENT_PET_MESSAGE": self.CURRENT_PET_MESSAGE,
            "CURRENT_PET_STATE": self.CURRENT_PET_STATE,
            "SELECTED_SKIN": self.SELECTED_SKIN,
            "ACTIVE_SECONDS_TODAY": self.ACTIVE_SECONDS_TODAY,
            "CONTINUOUS_ACTIVE_SECONDS": self.CONTINUOUS_ACTIVE_SECONDS,
            "IDLE_SECONDS": self.IDLE_SECONDS,
            "LOCK_STATE": self.LOCK_STATE,
            "PARENT_OVERRIDE_STATE": self.PARENT_OVERRIDE_STATE,
            "longest_session_seconds": self.longest_session_seconds,
            "breaks": self.breaks,
            "routines_completed": list(self.routines_completed),
            "warned": list(self.warned),
            "countdown_started": self.countdown_started,
            "countdown_left": self.countdown_left,
            "locked": self.locked,
            "override_until": self.override_until,
            "break_due": self.break_due,
            "break_acknowledged": self.break_acknowledged,
            "last_break_notify": self.last_break_notify,
            "routine_last_notify": dict(self.routine_last_notify),
            "pending_routine_title": self.pending_routine_title,
            "post_lock_anchor": self.post_lock_anchor,
            "alert_until": self.alert_until,
            "visual": self.visual,
            "child_locked": self.child_locked,
            "bonus_today_seconds": self.bonus_today_seconds,
            "care_due": self.care_due,
            "care_seconds": self.care_seconds,
            "active_since_care": self.active_since_care,
            "care_done_today": self.care_done_today,
        }

    @classmethod
    def from_dict(cls, raw: dict, day: str) -> "CentralState":
        state = cls(day=str(raw.get("day") or day))
        state.CURRENT_PET_MESSAGE = str(raw.get("CURRENT_PET_MESSAGE") or "")
        state.CURRENT_PET_STATE = str(raw.get("CURRENT_PET_STATE") or "HAPPY")
        state.SELECTED_SKIN = canonical_skin(str(raw.get("SELECTED_SKIN") or ""))
        state.child_locked = bool(raw.get("child_locked"))
        state.bonus_today_seconds = _clamp_int(raw.get("bonus_today_seconds", 0), 0, 0, 100000)
        state.care_due = bool(raw.get("care_due"))
        state.care_seconds = _clamp_int(raw.get("care_seconds", 0), 0, 0, 100000)
        state.active_since_care = _clamp_int(raw.get("active_since_care", 0), 0, 0, 1000000)
        state.care_done_today = _clamp_int(raw.get("care_done_today", 0), 0, 0, 1000)
        state.ACTIVE_SECONDS_TODAY = _clamp_int(raw.get("ACTIVE_SECONDS_TODAY", 0), 0, 0, 200000)
        state.CONTINUOUS_ACTIVE_SECONDS = _clamp_int(raw.get("CONTINUOUS_ACTIVE_SECONDS", 0), 0, 0, 200000)
        try:
            state.IDLE_SECONDS = max(0.0, float(raw.get("IDLE_SECONDS") or 0))
        except (TypeError, ValueError):
            state.IDLE_SECONDS = 0.0
        state.LOCK_STATE = str(raw.get("LOCK_STATE") or "none")
        state.PARENT_OVERRIDE_STATE = bool(raw.get("PARENT_OVERRIDE_STATE"))
        state.longest_session_seconds = _clamp_int(raw.get("longest_session_seconds", 0), 0, 0, 200000)
        state.breaks = _clamp_int(raw.get("breaks", 0), 0, 0, 100000)
        done = raw.get("routines_completed")
        state.routines_completed = [str(x) for x in done] if isinstance(done, list) else []
        warned = raw.get("warned")
        state.warned = [str(x) for x in warned] if isinstance(warned, list) else []
        state.countdown_started = bool(raw.get("countdown_started"))
        state.countdown_left = _clamp_int(raw.get("countdown_left", 0), 0, 0, 600)
        state.locked = bool(raw.get("locked"))
        state.override_until = str(raw.get("override_until") or "")
        state.break_due = bool(raw.get("break_due"))
        state.break_acknowledged = bool(raw.get("break_acknowledged"))
        state.last_break_notify = str(raw.get("last_break_notify") or "")
        notes = raw.get("routine_last_notify")
        state.routine_last_notify = {str(k): str(v) for k, v in notes.items()} if isinstance(notes, dict) else {}
        state.pending_routine_title = str(raw.get("pending_routine_title") or "")
        state.post_lock_anchor = str(raw.get("post_lock_anchor") or "")
        state.alert_until = str(raw.get("alert_until") or "")
        state.visual = str(raw.get("visual") or "")
        return state

    def reset_for_day(self, day: str) -> None:
        self.day = day
        self.ACTIVE_SECONDS_TODAY = 0
        self.CONTINUOUS_ACTIVE_SECONDS = 0
        self.IDLE_SECONDS = 0.0
        self.longest_session_seconds = 0
        self.breaks = 0
        self.routines_completed = []
        self.warned = []
        self.countdown_started = False
        self.countdown_left = 0
        self.countdown_paused = False
        self.locked = False
        self.bonus_today_seconds = 0
        self.care_done_today = 0
        self.care_due = False
        self.care_seconds = 0
        self.active_since_care = 0
        self.break_due = False
        self.break_acknowledged = False
        self.last_break_notify = ""
        self.routine_last_notify = {}
        self.pending_routine_title = ""
        self.post_lock_anchor = ""
        self.alert_until = ""
        self.visual = ""
        self.LOCK_STATE = "none"
        self.CURRENT_PET_STATE = "HAPPY"


def configure_paths(root: Path) -> dict:
    root = Path(root)
    for name in ("data", "logs", "skins", "sounds", "games", "Doc"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return {
        "root": root,
        "config": root / "config.json",
        "state": root / "data" / "state.json",
        "stats": root / "data" / "statistics.json",
        "log": root / "logs" / "agent.log",
        "sounds": root / "sounds",
        "skins": root / "skins",
        "pin": root / "PIN.txt",
    }


def log_line(log_path: Path | None, message: str) -> None:
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except OSError:
        pass


def log_exception(log_path: Path | None, where: str) -> None:
    log_line(log_path, f"{where}\n{traceback.format_exc()}")


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _backup_corrupt(path: Path, log_path: Path | None) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.name}.corrupt-{stamp}.bak")
    try:
        shutil.copy2(path, dest)
    except OSError as exc:
        log_line(log_path, f"failed to back up {path.name}: {exc}")
        return
    log_line(log_path, f"corrupt file backed up and reset: {path.name} -> {dest.name}")


def read_json_object(path: Path, log_path: Path | None) -> tuple[dict | None, bool]:
    """Return (object, failed). Missing file is not a failure."""
    if not path.exists():
        return None, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        log_line(log_path, f"unreadable {path.name}: {exc}")
        _backup_corrupt(path, log_path)
        return None, True
    if not isinstance(data, dict):
        log_line(log_path, f"{path.name} is not an object")
        _backup_corrupt(path, log_path)
        return None, True
    return data, False


def load_config(path: Path, log_path: Path | None) -> dict:
    raw, failed = read_json_object(path, log_path)
    cfg, pin_reset = normalize_config(raw or {})
    if raw and raw.get("selected_skin") not in (None, *SKIN_NAMES, *LEGACY_SKINS):
        log_line(log_path, f"missing skin {raw.get('selected_skin')!r}, using Пантера")
    should_save = failed or raw is None or pin_reset or "parent_pin" in (raw or {}) or public_config(cfg) != _comparable(raw)
    if pin_reset and raw is not None:
        log_line(log_path, "parent PIN stored as hash; default PIN applied")
    if should_save:
        try:
            atomic_write_json(path, public_config(cfg))
        except OSError as exc:
            log_line(log_path, f"failed to save config: {exc}")
    return cfg


def _comparable(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return {}
    cfg, _pin_reset = normalize_config(raw)
    return public_config(cfg)


def save_config(path: Path, cfg: dict) -> None:
    atomic_write_json(path, public_config(cfg))


def empty_stats() -> dict:
    return {"days": {}}


def snapshot_day(state: CentralState) -> dict:
    return {
        "active_seconds": state.ACTIVE_SECONDS_TODAY,
        "longest_session_seconds": state.longest_session_seconds,
        "breaks": state.breaks,
        "routines_completed": list(state.routines_completed),
    }


def archive_state(stats: dict, state: CentralState) -> None:
    if not state.day:
        return
    days = stats.setdefault("days", {})
    days[state.day] = snapshot_day(state)


def load_persistence(paths: dict, today: str) -> tuple[dict, CentralState, dict]:
    log_path = paths["log"]
    config = load_config(paths["config"], log_path)
    raw_stats, _failed = read_json_object(paths["stats"], log_path)
    stats = empty_stats()
    if isinstance(raw_stats, dict) and isinstance(raw_stats.get("days"), dict):
        stats["days"] = raw_stats["days"]
    elif raw_stats is not None:
        log_line(log_path, "statistics reset because days were missing")
    raw_state, _state_failed = read_json_object(paths["state"], log_path)
    if isinstance(raw_state, dict) and raw_state.get("day"):
        state = CentralState.from_dict(raw_state, today)
    else:
        state = CentralState(day=today)
    if state.day != today:
        archive_state(stats, state)
        state.reset_for_day(today)
        try:
            atomic_write_json(paths["stats"], stats)
            atomic_write_json(paths["state"], state.to_dict())
        except OSError as exc:
            log_line(log_path, f"failed to persist day rollover: {exc}")
    return config, state, stats


def save_persistence(paths: dict, config: dict, state: CentralState, stats: dict) -> None:
    archive_state(stats, state)
    atomic_write_json(paths["config"], public_config(config))
    atomic_write_json(paths["state"], state.to_dict())
    atomic_write_json(paths["stats"], stats)


def seconds_of_day(value: datetime | str) -> int:
    if isinstance(value, datetime):
        return value.hour * 3600 + value.minute * 60 + value.second
    hour, minute = str(value).split(":")
    return int(hour) * 3600 + int(minute) * 60


def in_bedtime(cur: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end


def school_active(now: datetime, cfg: dict) -> bool:
    """Recurring local weekday window; independent of boot time."""
    return bool(cfg.get("school_enabled", True) and now.weekday() < 5
                and seconds_of_day(cfg.get("school_from", "08:45")) <= seconds_of_day(now)
                < seconds_of_day(cfg.get("school_until", "13:00")))


def schedule_blocked(now: datetime, cfg: dict) -> bool:
    if not cfg.get("schedule_enforcement", True):
        return False
    cur = seconds_of_day(now)
    start = seconds_of_day(cfg["bedtime_start"])
    end = seconds_of_day(cfg["bedtime_end"])
    if in_bedtime(cur, start, end):
        return True
    allowed_from = seconds_of_day(cfg["allowed_from"])
    allowed_until = seconds_of_day(cfg["allowed_until"])
    if allowed_from == allowed_until:
        return False
    if allowed_from < allowed_until:
        return not (allowed_from <= cur < allowed_until)
    return not (cur >= allowed_from or cur < allowed_until)


def seconds_until_block(now: datetime, cfg: dict) -> int:
    if not cfg.get("schedule_enforcement", True):
        return 24 * 3600
    if schedule_blocked(now, cfg):
        return 0
    cur = seconds_of_day(now)
    origin = datetime.combine(now.date(), datetime.min.time())
    candidates = []
    for key in ("allowed_from", "allowed_until", "bedtime_start", "bedtime_end"):
        mark = seconds_of_day(cfg[key])
        delta = (mark - cur) % (24 * 3600)
        if delta:
            candidates.append(delta)
    for delta in sorted(set(candidates)):
        probe = origin + timedelta(seconds=cur + delta)
        previous = probe - timedelta(seconds=1)
        if schedule_blocked(probe, cfg) and not schedule_blocked(previous, cfg):
            return delta
    return 24 * 3600


def read_pin_file(path: Path) -> str:
    """The parent password lives in one plain file so it can be read or replaced."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_PIN
    for line in text.splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            return item
    return DEFAULT_PIN


def write_pin_file(path: Path, pin: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pin.strip() + "\n", encoding="utf-8")


def ensure_pin_file(path: Path) -> str:
    if not path.exists():
        write_pin_file(path, DEFAULT_PIN)
        return DEFAULT_PIN
    return read_pin_file(path)


def validate_new_pin(new_pin: str, confirm: str) -> str:
    if new_pin != confirm:
        return "Пароль не совпадает."
    cleaned = str(new_pin).strip()
    if not cleaned or any(char in cleaned for char in "\r\n"):
        return "Введите пароль одной строкой."
    if not 4 <= len(cleaned) <= 32:
        return "Пароль должен быть от 4 до 32 символов."
    return ""


def pin_matches(cfg: dict, pin: str) -> bool:
    stored = str(cfg.get("parent_pin_hash") or "")
    if not stored or pin is None:
        return False
    return hmac.compare_digest(hash_pin(pin), stored)


def change_pin(cfg: dict, new_pin: str, confirm: str) -> str:
    if new_pin != confirm:
        return "PIN не совпадает."
    if not str(new_pin).isdigit() or not 4 <= len(str(new_pin)) <= 8:
        return "PIN должен состоять из 4–8 цифр."
    cfg["parent_pin_hash"] = hash_pin(str(new_pin))
    return ""


def autostart_command(python_exe: str | None = None, script_path: str | None = None) -> str:
    if getattr(sys, "frozen", False) and python_exe is None and script_path is None:
        return f'"{sys.executable}"'
    python_exe = python_exe or sys.executable
    script_path = script_path or str(Path(__file__).resolve().parent / "main.py")
    return f'"{python_exe}" "{script_path}"'


def _write_autostart(enabled: bool, command: str) -> None:
    import winreg

    key = winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    try:
        if enabled:
            winreg.SetValueEx(key, "TechnoLabKidsCompanion", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "TechnoLabKidsCompanion")
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def get_autostart() -> bool:
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            command, _ = winreg.QueryValueEx(key, "TechnoLabKidsCompanion")
            return command == autostart_command()
    except FileNotFoundError:
        return False


def set_autostart(
    enabled: bool,
    command: str | None = None,
    log_path: Path | None = None,
    writer=None,
) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Автозапуск доступен только в Windows."
    try:
        (writer or _write_autostart)(enabled, command or autostart_command())
        return True, ""
    except Exception as exc:  # registry or permission problems must not crash Parent Mode
        log_line(log_path, f"autostart configuration failure: {exc}")
        return False, f"Не удалось изменить автозапуск: {exc}"


def query_idle_seconds() -> float:
    """Seconds since the last mouse or keyboard input. The input itself is not recorded."""
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        now = ctypes.windll.kernel32.GetTickCount()
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        return 0.0


def lock_workstation() -> bool:
    """Ask Windows to lock the interactive session. Credentials stay with Windows."""
    try:
        return bool(ctypes.windll.user32.LockWorkStation())
    except Exception:
        return False


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def routine_visual(kind: str) -> tuple[str, str]:
    if kind == "exercise":
        return "EXERCISE", ""
    if kind == "shower":
        return "REMINDER", "shower"
    if kind == "meal":
        return "EAT", ""
    if kind == "bedtime":
        return "SLEEP", ""
    return "REMINDER", ""


class PolicyEngine:
    def __init__(self, config: dict, state: CentralState, stats: dict):
        self.config = config
        self.state = state
        self.stats = stats
        self.pin_file: Path | None = None
        self.last_bonus = 0
        self.sync_settings()

    def sync_settings(self) -> None:
        cfg = self.config
        state = self.state
        state.DAILY_LIMIT = int(cfg["daily_limit_minutes"])
        state.BREAK_INTERVAL = int(cfg["break_after_minutes"])
        state.BREAK_DURATION = int(cfg["break_duration_minutes"])
        state.SOUND_ENABLED = bool(cfg["sound"])
        state.notifications_enabled = bool(cfg.get("notifications", True))
        state.SELECTED_SKIN = canonical_skin(cfg.get("selected_skin"))

    def pin_ok(self, pin: str) -> bool:
        if self.pin_file is not None:
            if pin is None:
                return False
            stored = read_pin_file(self.pin_file).encode("utf-8")
            given = str(pin).encode("utf-8")
            if len(stored) != len(given):
                return False
            return hmac.compare_digest(stored, given)
        return pin_matches(self.config, pin)

    @property
    def daily_limit_seconds(self) -> int:
        return int(self.config["daily_limit_minutes"]) * 60

    @property
    def break_after_seconds(self) -> int:
        return int(self.config["break_after_minutes"]) * 60

    @property
    def break_duration_seconds(self) -> int:
        return int(self.config["break_duration_minutes"]) * 60

    def remaining(self, now: datetime) -> tuple[int, int, int]:
        daily = max(0, self.daily_limit_seconds - self.state.ACTIVE_SECONDS_TODAY)
        schedule = seconds_until_block(now, self.config)
        return min(daily, schedule), daily, schedule

    def override_active(self, now: datetime) -> bool:
        until = _parse_iso(self.state.override_until)
        return bool(until and now < until)

    def next_routine(self, now: datetime) -> tuple[datetime, dict] | None:
        upcoming: list[tuple[datetime, dict]] = []
        later: list[tuple[datetime, dict]] = []
        for routine in self.config["routines"]:
            if routine["title"] in self.state.routines_completed:
                continue
            hour, minute = routine["time"].split(":")
            scheduled = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            if scheduled >= now.replace(second=0, microsecond=0):
                upcoming.append((scheduled, routine))
            else:
                later.append((scheduled + timedelta(days=1), routine))
        pool = upcoming or later
        if not pool:
            return None
        return min(pool, key=lambda item: item[0])

    def next_routine_label(self, now: datetime) -> str:
        found = self.next_routine(now)
        if not found:
            return "Нет запланированных дел"
        when, routine = found
        if when.date() == now.date():
            return f"{routine['title']} в {routine['time']}"
        return f"{routine['title']} завтра в {routine['time']}"

    def break_status(self) -> str:
        state = self.state
        if state.break_due:
            return f"Давай сделаем паузу. Отдыхов сегодня: {state.breaks}"
        if state.IDLE_SECONDS >= self.break_duration_seconds and state.CONTINUOUS_ACTIVE_SECONDS == 0:
            return f"Сейчас отдыхаем. Отдыхов сегодня: {state.breaks}"
        left = self.break_after_seconds - state.CONTINUOUS_ACTIVE_SECONDS
        if left < 0:
            left = 0
        return f"До паузы {fmt_duration(left)}. Отдыхов сегодня: {state.breaks}"

    def tick(self, now: datetime, idle_for: float) -> list[Effect]:
        effects: list[Effect] = []
        self._rollover(now, effects)
        self.state.IDLE_SECONDS = max(0.0, float(idle_for))
        if school_active(now, self.config):
            state = self.state
            if state.countdown_started or state.locked:
                effects.append(Effect("countdown_cancel"))
            state.countdown_started = state.countdown_paused = state.locked = False
            state.countdown_left = 0
            state.post_lock_anchor = state.pending_routine_title = state.alert_until = ""
            state.break_due = state.break_acknowledged = state.care_due = False
            state.CONTINUOUS_ACTIVE_SECONDS = state.active_since_care = 0
            state.last_break_notify = state.last_care_notify = ""
            state.LOCK_STATE = "school"
            state.CURRENT_PET_STATE = "IDLE"
            state.CURRENT_PET_MESSAGE = "Время занятий до " + self.config["school_until"]
            state.visual = ""
            # Do not replay missed school-time routines after 13:00.
            for routine in self.config["routines"]:
                if seconds_of_day(routine["time"]) <= seconds_of_day(now):
                    state.routine_last_notify[routine["title"]] = "skipped"
            self.sync_settings()
            state.NEXT_ROUTINE = self.next_routine_label(now)
            return effects
        if self.state.LOCK_STATE == "school":
            self.state.LOCK_STATE = "none"
            self.state.CURRENT_PET_MESSAGE = MSG_OK
        self._activity(now, effects)
        self._routines(now, effects)
        self._care(now, effects)
        self._limits(now, effects)
        self._ambient(now)
        self.sync_settings()
        self.state.NEXT_ROUTINE = self.next_routine_label(now)
        return effects

    def reveal_status(self, now: datetime) -> str | None:
        """Replace the startup greeting with the current meaningful status."""
        state = self.state
        if state.countdown_started or state.LOCK_STATE in ("countdown", "locked"):
            return None
        if state.pending_routine_title:
            return None
        remain, _daily, _schedule = self.remaining(now)
        final_seconds = int(self.config["final_warning_seconds"])
        if remain <= final_seconds or self.override_active(now):
            return None
        if remain <= 5 * 60:
            state.CURRENT_PET_MESSAGE = MSG_5
            state.CURRENT_PET_STATE = "WARNING"
            state.LOCK_STATE = "warning"
        elif remain <= 30 * 60:
            state.CURRENT_PET_MESSAGE = MSG_30
            state.CURRENT_PET_STATE = "WARNING"
            state.LOCK_STATE = "warning"
        elif state.break_due:
            state.CURRENT_PET_MESSAGE = MSG_BREAK
            state.CURRENT_PET_STATE = "TIRED"
        else:
            state.CURRENT_PET_MESSAGE = MSG_OK
            self._ambient(now)
        return state.CURRENT_PET_MESSAGE

    def acknowledge(self, now: datetime) -> list[Effect]:
        state = self.state
        if state.pending_routine_title:
            title = state.pending_routine_title
            if title not in state.routines_completed:
                state.routines_completed.append(title)
            state.pending_routine_title = ""
            return self._celebrate(now, self._with_praise(MSG_ACK_ROUTINE))
        if state.break_due and not state.break_acknowledged:
            state.break_acknowledged = True
            state.CURRENT_PET_MESSAGE = MSG_ACK_BREAK
            state.CURRENT_PET_STATE = "TIRED"
            state.visual = ""
            return [Effect("message", text=MSG_ACK_BREAK, sound="")]
        return []

    def grant_override(self, now: datetime, minutes: int | None = None) -> list[Effect]:
        span = int(minutes or self.config["override_minutes"])
        until = now + timedelta(minutes=span)
        state = self.state
        state.override_until = until.isoformat(timespec="seconds")
        state.PARENT_OVERRIDE_STATE = True
        state.countdown_started = False
        state.countdown_left = 0
        state.countdown_paused = False
        state.locked = False
        state.post_lock_anchor = ""
        state.warned = []
        state.LOCK_STATE = "override"
        state.CURRENT_PET_MESSAGE = MSG_OVERRIDE
        state.CURRENT_PET_STATE = "HAPPY"
        state.alert_until = ""
        state.visual = ""
        return [Effect("countdown_cancel"), Effect("message", text=MSG_OVERRIDE, sound="celebration")]

    def resume_control(self) -> None:
        state = self.state
        state.override_until = ""
        state.PARENT_OVERRIDE_STATE = False
        state.LOCK_STATE = "none"

    def grant_bonus(self, minutes: int) -> list[Effect]:
        """A won game gives the child extra screen time: it is taken off today's used time."""
        state = self.state
        cap = int(self.config.get("bonus_daily_cap_minutes", 15)) * 60
        granted = min(int(minutes) * 60, max(0, cap - state.bonus_today_seconds))
        self.last_bonus = granted // 60
        effects: list[Effect] = []
        if granted <= 0:
            state.CURRENT_PET_MESSAGE = MSG_BONUS_LIMIT
            effects.append(Effect("message", text=MSG_BONUS_LIMIT, sound="", notify=False))
            return effects
        state.bonus_today_seconds += granted
        state.ACTIVE_SECONDS_TODAY = max(0, state.ACTIVE_SECONDS_TODAY - granted)
        if state.countdown_started and not state.locked:
            remain = min(
                max(0, self.daily_limit_seconds - state.ACTIVE_SECONDS_TODAY),
                seconds_until_block(datetime.now(), self.config),
            )
            if remain > int(self.config["final_warning_seconds"]):
                state.countdown_started = False
                state.countdown_left = 0
                state.LOCK_STATE = "none"
                effects.append(Effect("countdown_cancel"))
        text = f"Ура, мы прошли все уровни! Нам добавили {granted // 60} мин."
        state.CURRENT_PET_MESSAGE = text
        effects.append(Effect("message", text=text, sound="celebration"))
        return effects

    def _care(self, now: datetime, effects: list[Effect]) -> None:
        """Tamagotchi rule: after a long session the pet asks the child to play with it for a few minutes."""
        state = self.state
        cfg = self.config
        if not cfg.get("care_enabled", True):
            state.care_due = False
            return
        if not state.care_due and state.active_since_care >= int(cfg["care_after_minutes"]) * 60:
            state.care_due = True
            state.last_care_notify = ""
        if not state.care_due or state.countdown_started or state.locked:
            return
        self._maybe_repeat(now, state.last_care_notify, int(cfg["reminder_repeat_minutes"]) * 60, effects, self._fire_care)

    def _fire_care(self, now: datetime, effects: list[Effect]) -> None:
        state = self.state
        text = care_message(int(self.config["care_minutes"]))
        state.last_care_notify = now.isoformat(timespec="seconds")
        state.CURRENT_PET_MESSAGE = text
        state.CURRENT_PET_STATE = "REMINDER"
        state.visual = ""
        state.alert_until = ""
        effects.append(Effect("message", text=text, sound="routine", notify=True, title="Мне скучно"))

    def add_care_seconds(self, seconds: int, now: datetime) -> list[Effect]:
        state = self.state
        state.care_seconds += int(seconds)
        if state.care_seconds < int(self.config["care_minutes"]) * 60:
            return []
        state.care_due = False
        state.care_seconds = 0
        state.active_since_care = 0
        state.care_done_today += 1
        state.last_care_notify = ""
        return self._celebrate(now, care_done_message(self.config.get("child_gender")))

    def _with_praise(self, text: str) -> str:
        gender = self.config.get("child_gender")
        return f"{text} {praise(gender)}" if gender else text

    def _celebrate(self, now: datetime, text: str) -> list[Effect]:
        state = self.state
        state.CURRENT_PET_MESSAGE = text
        state.CURRENT_PET_STATE = "CELEBRATION"
        state.visual = ""
        state.alert_until = (now + timedelta(seconds=8)).isoformat(timespec="seconds")
        return [Effect("message", text=text, sound="celebration")]

    def _rollover(self, now: datetime, effects: list[Effect]) -> None:
        today = now.date().isoformat()
        if self.state.day == today:
            return
        if self.state.day:
            archive_state(self.stats, self.state)
            effects.append(Effect("day_rollover", day=self.state.day))
        self.state.reset_for_day(today)

    def _activity(self, now: datetime, effects: list[Effect]) -> None:
        state = self.state
        idle_for = state.IDLE_SECONDS
        threshold = int(self.config["idle_threshold_seconds"])
        active = idle_for < threshold
        if not active and idle_for >= self.break_duration_seconds:
            if state.break_due:
                state.break_due = False
                state.break_acknowledged = False
                state.last_break_notify = ""
                state.breaks += 1
                state.CONTINUOUS_ACTIVE_SECONDS = 0
                effects.extend(self._celebrate(now, MSG_BREAK_DONE))
            elif state.CONTINUOUS_ACTIVE_SECONDS:
                state.CONTINUOUS_ACTIVE_SECONDS = 0
            return
        if not active:
            return
        state.ACTIVE_SECONDS_TODAY += 1
        state.active_since_care += 1
        state.CONTINUOUS_ACTIVE_SECONDS += 1
        if state.CONTINUOUS_ACTIVE_SECONDS > state.longest_session_seconds:
            state.longest_session_seconds = state.CONTINUOUS_ACTIVE_SECONDS
        if state.countdown_started or state.locked:
            return
        if state.CONTINUOUS_ACTIVE_SECONDS >= self.break_after_seconds and not state.break_due:
            state.break_due = True
            state.break_acknowledged = False
        if state.break_due and not state.break_acknowledged:
            self._maybe_repeat(
                now,
                state.last_break_notify,
                int(self.config["reminder_repeat_minutes"]) * 60,
                effects,
                self._fire_break,
            )

    def _fire_break(self, now: datetime, effects: list[Effect]) -> None:
        self.state.last_break_notify = now.isoformat(timespec="seconds")
        self.state.CURRENT_PET_MESSAGE = MSG_BREAK
        self.state.CURRENT_PET_STATE = "TIRED"
        self.state.visual = ""
        self.state.alert_until = ""
        effects.append(Effect("message", text=MSG_BREAK, sound="routine", notify=True, title="Давай отдохнём"))

    def _maybe_repeat(self, now, last_iso: str, every: int, effects, fire) -> None:
        last = _parse_iso(last_iso)
        if last is None or (now - last).total_seconds() >= every:
            fire(now, effects)

    def _routines(self, now: datetime, effects: list[Effect]) -> None:
        pending = self.state.pending_routine_title
        for routine in self.config["routines"]:
            title = routine["title"]
            if pending and title != pending:
                continue
            if title in self.state.routines_completed:
                continue
            if self.state.routine_last_notify.get(title) == "skipped":
                continue
            hour, minute = routine["time"].split(":")
            scheduled = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            late = (now - scheduled).total_seconds()
            if late < 0:
                continue
            repeat = int(routine["repeat_minutes"]) * 60
            last = self.state.routine_last_notify.get(title, "")
            if last == "" and late > max(repeat, 60):
                self.state.routine_last_notify[title] = "skipped"
                continue
            last_dt = _parse_iso(last)
            if last_dt is not None and (now - last_dt).total_seconds() < repeat:
                continue
            self._fire_routine(now, routine, effects)
            return

    def _fire_routine(self, now: datetime, routine: dict, effects: list[Effect]) -> None:
        state = self.state
        title = routine["title"]
        state.routine_last_notify[title] = now.isoformat(timespec="seconds")
        state.pending_routine_title = title
        pet_state, visual = routine_visual(routine["kind"])
        state.CURRENT_PET_MESSAGE = routine["message"]
        state.CURRENT_PET_STATE = pet_state
        state.visual = visual
        state.alert_until = (now + timedelta(seconds=45)).isoformat(timespec="seconds")
        effects.append(
            Effect("message", text=routine["message"], sound="routine", notify=True, title=title)
        )

    def _limits(self, now: datetime, effects: list[Effect]) -> None:
        state = self.state
        override = self.override_active(now)
        state.PARENT_OVERRIDE_STATE = override
        if override:
            if state.countdown_started:
                state.countdown_started = False
                state.countdown_left = 0
                effects.append(Effect("countdown_cancel"))
            state.LOCK_STATE = "override"
            return
        if not state.child_locked and (state.countdown_started or state.locked):
            # screen locking exists only while the parent has switched "Заблокировать" on
            state.countdown_started = False
            state.countdown_left = 0
            state.locked = False
            state.post_lock_anchor = ""
            state.LOCK_STATE = "none"
            effects.append(Effect("countdown_cancel"))
        if state.locked:
            self._relock_watch(now, effects)
            return
        remain, _daily, _schedule = self.remaining(now)
        if not state.child_locked and remain <= 0:
            self._maybe_repeat(
                now,
                state.last_limit_notify,
                int(self.config["reminder_repeat_minutes"]) * 60,
                effects,
                self._fire_limit_notice,
            )
            return
        final_seconds = int(self.config["final_warning_seconds"])
        if remain > 30 * 60:
            state.warned = [item for item in state.warned if item not in ("30", "5")]
        elif remain > 5 * 60:
            state.warned = [item for item in state.warned if item != "5"]
        if state.countdown_started:
            if state.countdown_paused:
                return
            state.countdown_left -= 1
            state.LOCK_STATE = "countdown"
            state.CURRENT_PET_STATE = "LOCK_COUNTDOWN"
            if state.countdown_left <= 0:
                state.countdown_started = False
                state.countdown_left = 0
                state.locked = True
                state.LOCK_STATE = "locked"
                state.post_lock_anchor = ""
                state.CURRENT_PET_MESSAGE = MSG_LOCKED
                state.CURRENT_PET_STATE = "SLEEP"
                effects.append(Effect("message", text=MSG_LOCKED, sound="warning", notify=True, title="Подскажу"))
                effects.append(Effect("lock"))
            else:
                text = countdown_message(state.countdown_left)
                state.CURRENT_PET_MESSAGE = text
                effects.append(Effect("countdown_tick", seconds=state.countdown_left, text=text))
            return
        if state.child_locked and remain <= final_seconds:
            state.countdown_started = True
            state.countdown_left = final_seconds
            state.LOCK_STATE = "countdown"
            state.CURRENT_PET_STATE = "LOCK_COUNTDOWN"
            state.visual = ""
            text = countdown_message(state.countdown_left)
            state.CURRENT_PET_MESSAGE = text
            effects.append(Effect("countdown_start", seconds=state.countdown_left, text=text))
            effects.append(Effect("message", text=text, sound="warning", notify=True, title="Подскажу"))
            return
        if remain <= 5 * 60 and "5" not in state.warned:
            state.warned.append("5")
            state.LOCK_STATE = "warning"
            state.CURRENT_PET_STATE = "WARNING"
            state.CURRENT_PET_MESSAGE = MSG_5
            state.alert_until = ""
            effects.append(Effect("message", text=MSG_5, sound="warning", notify=True, title="Подскажу"))
        elif remain <= 30 * 60 and "30" not in state.warned and remain > 5 * 60:
            state.warned.append("30")
            state.LOCK_STATE = "warning"
            state.CURRENT_PET_STATE = "WARNING"
            state.CURRENT_PET_MESSAGE = MSG_30
            state.alert_until = ""
            effects.append(Effect("message", text=MSG_30, sound="warning", notify=True, title="Подскажу"))

    def _fire_limit_notice(self, now: datetime, effects: list[Effect]) -> None:
        state = self.state
        _remain, _daily, schedule = self.remaining(now)
        text = MSG_BEDTIME_UP if schedule <= 0 else MSG_TIME_UP
        state.last_limit_notify = now.isoformat(timespec="seconds")
        state.LOCK_STATE = "warning"
        state.CURRENT_PET_STATE = "WARNING"
        state.CURRENT_PET_MESSAGE = text
        state.visual = ""
        state.alert_until = ""
        effects.append(Effect("message", text=text, sound="warning", notify=True, title="Подскажу"))

    def _relock_watch(self, now: datetime, effects: list[Effect]) -> None:
        state = self.state
        if state.IDLE_SECONDS >= int(self.config["idle_threshold_seconds"]):
            return
        if not state.post_lock_anchor:
            state.post_lock_anchor = now.isoformat(timespec="seconds")
            return
        anchor = _parse_iso(state.post_lock_anchor)
        if anchor and (now - anchor).total_seconds() >= int(self.config["relock_grace_seconds"]):
            state.locked = False
            state.post_lock_anchor = ""
            state.countdown_started = True
            state.countdown_left = int(self.config["final_warning_seconds"])
            state.LOCK_STATE = "countdown"
            state.CURRENT_PET_STATE = "LOCK_COUNTDOWN"
            text = countdown_message(state.countdown_left)
            state.CURRENT_PET_MESSAGE = text
            effects.append(Effect("countdown_start", seconds=state.countdown_left, text=text))
            effects.append(Effect("message", text=text, sound="warning", notify=True, title="Подскажу"))

    def _ambient(self, now: datetime) -> None:
        state = self.state
        if state.countdown_started:
            state.CURRENT_PET_STATE = "LOCK_COUNTDOWN"
            state.LOCK_STATE = "countdown"
            return
        alert = _parse_iso(state.alert_until)
        if alert and now < alert:
            return
        if alert and now >= alert:
            state.alert_until = ""
        remain, _daily, _schedule = self.remaining(now)
        if state.LOCK_STATE == "warning" and remain <= 30 * 60 and not self.override_active(now):
            state.CURRENT_PET_STATE = "WARNING"
            return
        if state.break_due:
            state.CURRENT_PET_STATE = "TIRED"
            return
        if state.care_due:
            state.CURRENT_PET_STATE = "REMINDER"
            return
        if state.locked:
            state.CURRENT_PET_STATE = "SLEEP"
            state.LOCK_STATE = "locked"
            return
        if state.IDLE_SECONDS >= int(self.config["idle_threshold_seconds"]):
            state.CURRENT_PET_STATE = "SLEEP"
            if state.LOCK_STATE not in ("warning", "locked"):
                state.LOCK_STATE = "none"
            return
        state.CURRENT_PET_STATE = "IDLE"
        if state.LOCK_STATE not in ("warning", "override"):
            state.LOCK_STATE = "none"


def statistics_text(stats: dict, state: CentralState) -> str:
    lines = [
        f"Сегодня ({state.day})",
        f"  активное время: {fmt_duration(state.ACTIVE_SECONDS_TODAY)}",
        f"  самая длинная сессия: {fmt_duration(state.longest_session_seconds)}",
        f"  перерывы: {state.breaks}",
        f"  выполненные дела: {', '.join(state.routines_completed) or '—'}",
        "",
        "Прошлые дни",
    ]
    days = stats.get("days") or {}
    history = sorted((day, payload) for day, payload in days.items() if day != state.day)
    if not history:
        lines.append("  пока нет")
    for day, payload in history[-14:]:
        if not isinstance(payload, dict):
            continue
        lines.append(
            f"  {day}: активно {fmt_duration(payload.get('active_seconds', 0))}, "
            f"длинная сессия {fmt_duration(payload.get('longest_session_seconds', 0))}, "
            f"перерывы {payload.get('breaks', 0)}"
        )
    return "\n".join(lines)


def validate_settings(cfg: dict) -> list[str]:
    errors = []
    for key, label, lo, hi in (
        ("daily_limit_minutes", "Дневной лимит", 1, 1440),
        ("break_after_minutes", "Интервал перерыва", 1, 600),
        ("break_duration_minutes", "Длительность перерыва", 1, 180),
        ("idle_threshold_seconds", "Порог бездействия", 15, 3600),
        ("override_minutes", "Временная разблокировка", 1, 240),
        ("final_warning_seconds", "Финальный отсчёт", 10, 120),
    ):
        value = cfg.get(key)
        if not isinstance(value, int) or not lo <= value <= hi:
            errors.append(f"{label}: допустимо {lo}–{hi}.")
    for key in ("allowed_from", "allowed_until", "bedtime_start", "bedtime_end", "school_from", "school_until"):
        if not _clock_ok(cfg.get(key, "")):
            errors.append(f"Время {key} должно быть в формате ЧЧ:ММ.")
    if cfg.get("school_from", "08:45") >= cfg.get("school_until", "13:00"):
        errors.append("Начало занятий должно быть раньше окончания.")
    titles = set()
    for routine in cfg.get("routines") or []:
        if not _clock_ok(routine.get("time", "")):
            errors.append("У каждого дела должно быть время ЧЧ:ММ.")
        title = str(routine.get("title", "")).strip()
        if not title:
            errors.append("У дела должно быть название.")
        elif title in titles:
            errors.append(f"Повторяется название дела: {title}.")
        titles.add(title)
    if cfg.get("selected_skin") not in SKIN_NAMES:
        errors.append("Выберите один из 20 скинов.")
    return errors
