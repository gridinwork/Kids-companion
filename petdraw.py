"""Original pixel pets. Each skin is drawn in code; nothing is copied from a game."""

from __future__ import annotations

import json

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from logic import SKIN_NAMES
from petart import idle_pose, paint_creature  # noqa: F401  (idle_pose is re-exported for main.py)

# name, kind, body, belly, ink, accent
SKIN_DEFS = [
    ("Пантера", "panther", "#101010", "#1A1A1A", "#D9B44A", "#4A2A30"),
    ("Собака", "dog", "#F4F4F4", "#FFFFFF", "#1A1A1A", "#1A1A1A"),
    ("Кот", "cat", "#F6C453", "#FFF1C9", "#3A2A1A", "#E07A3D"),
    ("Зайчик", "bunny", "#F7D6E0", "#FFF7FB", "#3A2A32", "#FF8FB8"),
    ("Единорог", "unicorn", "#E7D5FF", "#FFFFFF", "#3A2A4A", "#F7A8FF"),
    ("Лисёнок", "fox", "#F28C3A", "#FFE0C2", "#2B2118", "#FFFFFF"),
    ("Дракончик", "dragon", "#7BD67A", "#D9F5D0", "#1E3A24", "#F26D6D"),
    ("Робот", "robot", "#9AD7FF", "#E7F6FF", "#1C2A33", "#F6C453"),
    ("Динозаврик", "dino", "#8FCB6B", "#E4F5D4", "#24321C", "#5A8F3E"),
    ("Ниндзя", "ninja", "#3E4A59", "#5C6B7A", "#101418", "#E84D4D"),
]
BY_NAME = {item[0]: item for item in SKIN_DEFS}


def resolve_skin(name: str):
    from logic import canonical_skin

    return BY_NAME.get(canonical_skin(name)) or BY_NAME["Кот"]


def expression_for(frame: int, state: str, kind: str = "") -> str:
    """Face cycle: blink, smile and a few funny faces. Not only a vertical bob."""
    if state == "SLEEP":
        return "sleep"
    if state == "LOCK_COUNTDOWN":
        return "surprised" if (frame // 4) % 2 == 0 else "blink"
    if state in ("WARNING", "TIRED"):
        return "blink" if frame % 24 < 2 else "calm"
    if state == "CELEBRATION":
        return "laugh" if (frame // 6) % 2 == 0 else "smile"
    tick = frame % 36
    if tick in (0, 1):
        return "blink"
    if 10 <= tick <= 16:
        faces = ("smile", "wink", "tongue", "cross", "laugh", "bigtongue", "puff", "kiss", "silly", "sly")
        return faces[(frame // 36) % len(faces)]
    return "smile"


def paint_pet(
    painter: QPainter,
    rect: QRect,
    skin: str,
    state: str,
    frame: int,
    visual: str = "",
    expression: str = "",
    pose: str = "",
) -> None:
    _name, kind, body, belly, ink, accent = resolve_skin(skin)
    scale = rect.width() / 32.0
    expr = expression or expression_for(frame, state, kind)
    bob = 0
    if state == "EXERCISE":
        bob = -2 if (frame // 4) % 2 == 0 else 0
    elif expr == "laugh":
        bob = -2 if (frame // 3) % 2 == 0 else 0

    def px(x, y, w, h, color):
        painter.fillRect(
            int(rect.x() + x * scale),
            int(rect.y() + (y + bob) * scale),
            max(1, int(w * scale)),
            max(1, int(h * scale)),
            QColor(color),
        )

    if state == "LOCK_COUNTDOWN" and frame % 4 == 0:
        painter.fillRect(rect, QColor("#4A1218"))
    elif state == "WARNING":
        painter.fillRect(rect, QColor(40, 28, 28, 40))

    if visual == "shower" or state == "PLAY":
        for index, drop in enumerate(((4, 6), (26, 8), (7, 18), (27, 20))):
            if (frame + index) % 6 < 4:
                px(drop[0], drop[1], 2, 2, "#7EC8FF")

    if kind == "panther" and pose in ("side_r", "side_l"):
        draw = px if pose == "side_r" else (lambda x, y, w, h, color: px(32 - x - w, y, w, h, color))
        _paint_panther_side(draw, expr, frame, body, belly, ink, accent)
    elif kind == "panther" and pose == "back":
        _paint_panther_back(px, frame, body, accent, ink)
    else:
        paint_creature(px, kind, body, belly, ink, accent, expr, state, frame)
    _paint_extras(px, state, body, accent, ink)


def _paint_extras(px, state, body, accent, ink) -> None:
    if state == "EXERCISE":
        px(5, 10, 3, 6, body)
        px(24, 10, 3, 6, body)
    elif state == "PLAY":
        px(5, 16, 4, 3, body)
        px(23, 16, 4, 3, body)

    if state == "WARNING":
        px(22, 12, 2, 3, "#7EC8FF")
    if state == "CELEBRATION":
        px(2, 6, 2, 2, accent)
        px(28, 8, 2, 2, "#FFFFFF")
        px(4, 22, 2, 2, accent)
    if state == "REMINDER":
        px(24, 6, 4, 4, accent)
        px(25, 7, 2, 2, ink)


def _paint_panther_side(px, expr, frame, body, muzzle, gold, ear_in) -> None:
    """Profile facing right (the left-facing pose mirrors px). Legs walk, tail swings."""
    rim = "#2C2C32"
    dim = "#8C7340"
    gray = "#8A8A90"
    pink = "#FF7AA2"
    step = (frame // 3) % 4
    lift = 1 if step in (1, 3) else 0
    sway = (0, 1, 2, 1)[step]
    by = 17 - lift
    off = (-1, 0, 1, 0)[step]
    # tail
    px(3, 20, 3, 3, rim)
    px(3, 15, 3, 6, rim)
    px(3 + sway, 11, 3, 5, rim)
    px(4, 16, 1, 5, body)
    px(4 + sway, 12, 1, 4, body)
    # body
    px(5, by, 18, 9, rim)
    px(6, by + 1, 16, 7, body)
    # legs: far pair, then near pair
    for x in (15 - off, 8 - off, 19 + off, 12 + off):
        px(x - 1, 25, 5, 5, rim)
        px(x, 25, 3, 4, body)
    # ears and head
    px(25, by - 12, 5, 6, rim)
    px(26, by - 11, 3, 5, body)
    px(19, by - 13, 5, 7, rim)
    px(20, by - 12, 3, 6, body)
    px(21, by - 11, 1, 3, ear_in)
    px(19, by - 8, 12, 12, rim)
    px(20, by - 7, 10, 10, body)
    px(27, by - 3, 5, 5, muzzle)
    px(30, by - 3, 2, 2, "#4A2E2C")
    # eye
    if expr in ("blink", "sleep", "wink"):
        px(25, by - 4, 3, 1, dim)
    elif expr == "laugh":
        px(25, by - 4, 1, 1, gold)
        px(26, by - 5, 2, 1, gold)
        px(28, by - 4, 1, 1, gold)
    elif expr == "surprised":
        px(25, by - 6, 4, 4, gold)
        px(27, by - 6, 1, 4, "#101010")
    elif expr in ("sly", "calm"):
        px(25, by - 4, 3, 2, gold)
        px(25, by - 5, 3, 1, rim)
        px(27, by - 4, 1, 2, "#101010")
    else:
        px(25, by - 5, 3, 3, gold)
        px(27, by - 5, 1, 3, "#101010")
    # mouth
    if expr in ("tongue", "silly", "cross"):
        px(27, by + 1, 4, 1, gray)
        px(28, by + 2, 2, 2, pink)
    elif expr == "laugh":
        px(27, by + 1, 4, 2, "#2A1418")
        px(28, by + 2, 2, 1, pink)
    else:
        px(27, by + 1, 4, 1, gray)
    px(30, by - 1, 2, 1, gray)


def _paint_panther_back(px, frame, body, ear_in, gold) -> None:
    """Seen from behind: round head, wide back, tail swaying up the right side."""
    rim = "#2C2C32"
    gray = "#8A8A90"
    sway = (0, 1, 2, 1, 0, -1, -2, -1)[(frame // 3) % 8]
    for i in range(10):
        x = min(29, 26 + (i * 3) // 8 + (sway * i) // 8)
        y = 27 - i * 2
        px(x, y, 3, 3, rim)
        px(x + 1, y, 1, 3, body)
    px(7, 19, 18, 10, rim)
    px(8, 20, 16, 8, body)
    px(8, 28, 6, 2, rim)
    px(9, 28, 4, 2, body)
    px(18, 28, 6, 2, rim)
    px(19, 28, 4, 2, body)
    px(4, 3, 5, 4, rim)
    px(4, 6, 7, 4, rim)
    px(4, 9, 9, 4, rim)
    px(23, 3, 5, 4, rim)
    px(21, 6, 7, 4, rim)
    px(19, 9, 9, 4, rim)
    px(5, 4, 3, 3, body)
    px(5, 6, 5, 3, body)
    px(5, 9, 7, 3, body)
    px(24, 4, 3, 3, body)
    px(22, 6, 5, 3, body)
    px(20, 9, 7, 3, body)
    px(5, 10, 22, 13, rim)
    px(6, 11, 20, 11, body)
    px(2, 17, 4, 1, gray)
    px(26, 17, 4, 1, gray)
    px(9, 16, 2, 1, "#1E1E22")
    px(21, 16, 2, 1, "#1E1E22")


def icon_for(skin: str, state: str = "HAPPY", visual: str = "") -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, False)
    paint_pet(painter, QRect(0, 0, 64, 64), skin, state, 0, visual, "smile")
    painter.end()
    return QIcon(pixmap)


def export_skin_catalog(folder) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    catalog = []
    for name, kind, body, belly, ink, accent in SKIN_DEFS:
        catalog.append(
            {"name": name, "kind": kind, "body": body, "belly": belly, "ink": ink, "accent": accent}
        )
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        paint_pet(painter, QRect(0, 0, 64, 64), name, "HAPPY", 0, "", "smile")
        painter.end()
        pixmap.save(str(folder / f"{kind}.png"))
    (folder / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [name for name in SKIN_NAMES if name not in BY_NAME]
    if missing:
        raise RuntimeError(f"skin catalog incomplete: {missing}")
