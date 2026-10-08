"""Shared face engine and per-species pixel art for all pets (32x32 grid).

Every pet has the same expressive face: big eyes, nose, mouth, tongue, whiskers, cheeks.
Species only change the silhouette (ears, horns, wings, helmets...) and the face "look".
"""

from __future__ import annotations

from PySide6.QtGui import QColor

PINK = "#FF7AA2"
DEEP_PINK = "#E0557F"
MOUTH_DARK = "#2A1418"
WHITE = "#FFFFFF"

# expression names every pet understands
EXPRESSIONS = (
    "smile", "blink", "sleep", "wink", "laugh", "surprised", "silly", "tongue", "bigtongue",
    "sly", "calm", "cross", "dizzy", "grumpy", "kiss", "puff", "yawn",
)
FUNNY_FACES = ("tongue", "cross", "silly", "bigtongue", "puff", "kiss", "dizzy", "grumpy", "laugh", "wink", "yawn", "surprised", "sly")


def _dark(color: str, percent: int = 150) -> str:
    return QColor(color).darker(percent).name()


def _light(color: str, percent: int = 150) -> str:
    return QColor(color).lighter(percent).name()


# kind -> look. eye: iris colour (None = big dark glossy eye); pupil: slit/round/none/glossy
LOOKS: dict[str, dict] = {
    "panther": dict(eye="#D9B44A", pupil="slit", nose="#4A2E2C", mouth="#8A8A90", whisk="#8A8A90", muzzle=True, rim="#2C2C32", shut="#8C7340", arc="#D9B44A"),
    "cat": dict(eye="#7BD16B", pupil="slit", nose="#E8808F", mouth="#7A4A2A", whisk="#FFF6E0", blush="#F7A07A", muzzle=True),
    "bunny": dict(nose="#FF8FB8", nose_shape="dot", mouth="#B25A7A", blush="#FFB3C9", muzzle=True),
    "fox": dict(eye="#FFB300", pupil="slit", nose="#2B2118", nose_shape="dot", mouth="#5A3A22", whisk="#FFFFFF", muzzle=True),
    "dog": dict(eye="#F4F4F4", pupil="round", nose="#1A1A1A", nose_shape="dot", mouth="#444444", muzzle=True),
    "unicorn": dict(nose="#F7A8FF", nose_shape="dot", mouth="#8A5AA0", blush="#FFB3E6", muzzle=True),
    "fairy": dict(nose="#7DDEFF", nose_shape="dot", mouth="#3A8A7A", blush="#FFB3C9"),
    "owl": dict(eye="#FFD54F", pupil="round", nose="#FFB300", nose_shape="beak", mouth="#5A3A22", muzzle=False),
    "axolotl": dict(nose="#FF6F91", nose_shape="none", mouth="#A04060", blush="#FF6F91"),
    "star": dict(nose="#E0A030", nose_shape="dot", mouth="#8A6A18", blush="#FFB36F"),
    "dragon": dict(eye="#FFD54F", pupil="slit", nose="#2E6B35", nose_shape="nostril", mouth="#1E3A24", muzzle=True),
    "robot": dict(eye="#F6C453", pupil="none", nose_shape="none", mouth="#F6C453"),
    "dino": dict(eye="#FFD54F", pupil="round", nose="#24321C", nose_shape="nostril", mouth="#24321C", blush="#E8A070"),
    "knight": dict(nose="#E8A58F", nose_shape="dot", mouth="#7A4A3A", blush="#F2A38F", skin="#F3D3B3"),
    "astro": dict(nose="#E8A58F", nose_shape="dot", mouth="#7A4A3A", blush="#F2A38F", skin="#FFE9D6"),
    "shark": dict(nose="#16324A", nose_shape="nostril", mouth="#16324A", muzzle=True),
    "wolf": dict(eye="#FFD54F", pupil="slit", nose="#16181C", mouth="#3A3F46", whisk="#E6E9EE", muzzle=True),
    "slime": dict(nose_shape="none", mouth="#1E3A18", blush="#C6FF4A"),
    "golem": dict(eye="#6FFF9A", pupil="none", nose_shape="none", mouth="#2A2420"),
    "ninja": dict(eye="#FFFFFF", pupil="round", nose_shape="none", mouth="#D6DEE8", skin="#E8C9A8"),
    "rover": dict(eye="#4AA3DF", pupil="none", nose_shape="none", mouth="#4AA3DF"),
}


class Pal:
    def __init__(self, kind: str, body: str, belly: str, ink: str, accent: str):
        look = LOOKS.get(kind, {})
        c = QColor(body)
        self.kind = kind
        self.body = body
        self.belly = belly
        self.ink = ink
        self.accent = accent
        self.rim = look.get("rim") or (c.lighter(290).name() if c.lightness() < 40 else c.darker(165).name())
        self.hi = c.lighter(120).name()
        self.eye = look.get("eye")
        self.pupil = look.get("pupil", "glossy")
        self.nose = look.get("nose", ink)
        self.nose_shape = look.get("nose_shape", "tri")
        self.mouth = look.get("mouth", ink)
        self.whisk = look.get("whisk")
        self.blush = look.get("blush")
        self.muzzle = bool(look.get("muzzle", False))
        self.shut = look.get("shut", ink)
        self.arc = look.get("arc", ink if self.eye is None else (ink if QColor(body).lightness() >= 40 else self.eye))
        self.skin = look.get("skin")


# ------------------------------------------------------------------ face
def draw_face(px, P: Pal, expr: str, state: str, frame: int) -> None:
    look = 0 if expr in ("blink", "sleep", "laugh", "wink", "yawn", "puff", "kiss", "dizzy") else ((frame // 20) % 3) - 1
    iris, ink, rim = P.eye, P.ink, P.rim
    dark = "#101010"

    def pupil(x, y, h):
        if P.pupil == "slit":
            px(x + 2 + look, y, 1, h, dark)
        elif P.pupil == "round":
            px(x + 1 + look, y + (h - 3) // 2, 3, 3, dark)

    def eye_open(x):
        if iris is None:
            px(x, 13, 5, 4, ink)
            px(x + 1 + max(0, look), 14, 1, 1, WHITE)
            px(x + 3, 16, 1, 1, "#8A8A8A")
        else:
            px(x, 13, 5, 4, iris)
            pupil(x, 13, 4)
            if P.pupil == "round":
                px(x + 1, 14, 1, 1, WHITE)

    def eye_wide(x):
        if iris is None:
            px(x - 1, 12, 7, 6, ink)
            px(x, 13, 2, 2, WHITE)
        else:
            px(x, 12, 5, 6, iris)
            pupil(x, 12, 6)

    def eye_shut(x):
        px(x, 16, 5, 1, P.shut)

    def eye_happy(x):
        px(x, 16, 1, 1, P.arc)
        px(x + 1, 15, 3, 1, P.arc)
        px(x + 4, 16, 1, 1, P.arc)

    def eye_sly(x):
        if iris is None:
            px(x, 14, 5, 3, ink)
            px(x + 1, 15, 1, 1, WHITE)
        else:
            px(x, 15, 5, 2, iris)
            pupil(x, 15, 2)
        px(x, 14, 5, 1, rim)

    def eye_cross(x, inner):
        if iris is None:
            px(x, 13, 5, 4, ink)
            px(x + inner, 13, 2, 4, "#000000")
            px(x + (1 if inner == 3 else 3), 14, 1, 1, WHITE)
        else:
            px(x, 13, 5, 4, iris)
            px(x + inner, 13, 2, 4, dark)

    def eye_dizzy(x):
        for i in range(5):
            px(x + i, 12 + i, 1, 1, ink if iris is None else dark)
            px(x + 4 - i, 12 + i, 1, 1, ink if iris is None else dark)

    def eye_grumpy(x, left):
        if iris is None:
            px(x, 14, 5, 3, ink)
            px(x + 1, 15, 1, 1, WHITE)
        else:
            px(x, 14, 5, 3, iris)
            pupil(x, 14, 3)
        if left:
            px(x, 12, 2, 1, rim)
            px(x + 2, 13, 3, 1, rim)
        else:
            px(x + 3, 12, 2, 1, rim)
            px(x, 13, 3, 1, rim)

    left, right = 9, 18
    if expr in ("blink", "sleep", "yawn", "puff"):
        eye_shut(left)
        eye_shut(right)
    elif expr in ("laugh", "kiss"):
        eye_happy(left)
        eye_happy(right)
    elif expr == "wink":
        eye_shut(left)
        eye_open(right)
    elif expr == "surprised":
        eye_wide(left)
        eye_wide(right)
    elif expr == "silly":
        eye_shut(left)
        eye_wide(right)
    elif expr == "cross":
        eye_cross(left, 3)
        eye_cross(right, 0)
    elif expr == "dizzy":
        eye_dizzy(left)
        eye_dizzy(right)
    elif expr == "grumpy":
        eye_grumpy(left, True)
        eye_grumpy(right, False)
    elif expr in ("sly", "calm"):
        eye_sly(left)
        eye_sly(right)
    else:
        eye_open(left)
        eye_open(right)

    # cheeks, whiskers
    if P.blush and expr in ("smile", "laugh", "kiss", "wink", "tongue", "bigtongue", "blink", "calm"):
        px(7, 18, 3, 2, P.blush)
        px(22, 18, 3, 2, P.blush)
    if P.whisk:
        px(2, 19, 5, 1, P.whisk)
        px(25, 19, 5, 1, P.whisk)
        if expr in ("laugh", "surprised", "puff"):
            px(2, 17, 4, 1, P.whisk)
            px(26, 17, 4, 1, P.whisk)
    if expr == "puff":
        px(5, 17, 5, 5, P.hi)
        px(22, 17, 5, 5, P.hi)

    # nose
    shape, nc = P.nose_shape, P.nose
    if shape == "tri":
        px(14, 18, 4, 1, nc)
        px(15, 19, 2, 1, nc)
    elif shape == "dot":
        px(15, 18, 2, 2, nc)
    elif shape == "beak":
        px(14, 17, 4, 2, nc)
        px(15, 19, 2, 1, _dark(nc, 140))
    elif shape == "nostril":
        px(13, 18, 1, 1, nc)
        px(18, 18, 1, 1, nc)

    # mouth
    m = P.mouth
    wiggle = 1 if (frame // 3) % 2 == 0 else 0
    if expr == "bigtongue":
        px(12, 21, 3, 1, m)
        px(17, 21, 3, 1, m)
        px(15, 20, 2, 1, m)
        px(15 + wiggle, 22, 3, 5, PINK)
        px(16 + wiggle, 23, 1, 3, DEEP_PINK)
    elif expr in ("tongue", "silly", "cross"):
        px(12, 21, 3, 1, m)
        px(17, 21, 3, 1, m)
        px(15, 20, 2, 1, m)
        px(15, 22, 2, 2, PINK)
    elif expr == "surprised":
        px(14, 20, 4, 3, MOUTH_DARK)
        px(15, 21, 2, 1, PINK)
    elif expr == "laugh":
        px(12, 20, 8, 3, MOUTH_DARK)
        px(13, 22, 6, 1, PINK)
        px(12, 20, 1, 1, WHITE)
        px(19, 20, 1, 1, WHITE)
    elif expr == "yawn":
        px(12, 19, 8, 5, MOUTH_DARK)
        px(14, 22, 4, 1, PINK)
    elif expr == "kiss":
        px(15, 20, 2, 3, DEEP_PINK)
        px(24, 8, 2, 1, PINK)
        px(23, 9, 4, 2, PINK)
        px(24, 11, 2, 1, PINK)
        px(25, 12, 1, 1, PINK)
    elif expr == "puff":
        px(15, 21, 2, 1, m)
    elif expr == "grumpy":
        px(12, 22, 2, 1, m)
        px(14, 21, 4, 1, m)
        px(18, 22, 2, 1, m)
    elif expr == "dizzy":
        px(12, 21, 2, 1, m)
        px(14, 22, 2, 1, m)
        px(16, 21, 2, 1, m)
        px(18, 22, 2, 1, m)
    elif expr == "sly":
        px(12, 21, 6, 1, m)
        px(18, 20, 2, 1, m)
    elif expr == "sleep":
        px(14, 21, 4, 1, m)
        px(24, 6, 2, 2, P.accent)
        px(27, 3, 2, 2, P.accent)
    elif expr in ("smile", "wink"):
        px(11, 20, 1, 1, m)
        px(12, 21, 3, 1, m)
        px(15, 20, 2, 1, m)
        px(17, 21, 3, 1, m)
        px(20, 20, 1, 1, m)
    elif state == "EAT":
        px(14, 20, 4, 3, MOUTH_DARK)
    else:
        px(14, 21, 4, 1, m)


# ------------------------------------------------------------------ shared parts
def _ears_pointed(px, P: Pal, inner: str | None = None, tip: str | None = None) -> None:
    for x, y, w, h in ((4, 3, 5, 4), (4, 6, 7, 4), (4, 9, 9, 4), (23, 3, 5, 4), (21, 6, 7, 4), (19, 9, 9, 4)):
        px(x, y, w, h, P.rim)
    for x, y, w, h in ((5, 4, 3, 3), (5, 6, 5, 3), (5, 9, 7, 3), (24, 4, 3, 3), (22, 6, 5, 3), (20, 9, 7, 3)):
        px(x, y, w, h, P.body)
    inner = inner or P.accent
    px(6, 5, 1, 3, inner)
    px(25, 5, 1, 3, inner)
    if tip:
        px(5, 4, 3, 2, tip)
        px(24, 4, 3, 2, tip)


def _ears_round(px, P: Pal, color: str) -> None:
    for x in (3, 23):
        px(x, 5, 6, 6, P.rim)
        px(x + 1, 6, 4, 4, color)


def _ears_tall(px, P: Pal) -> None:
    for x in (8, 20):
        px(x - 1, 0, 6, 13, P.rim)
        px(x, 1, 4, 12, P.body)
        px(x + 1, 2, 2, 9, P.accent)


def _head(px, P: Pal) -> None:
    px(5, 10, 22, 14, P.rim)
    px(6, 11, 20, 12, P.body)
    if P.muzzle:
        px(10, 18, 12, 5, P.belly)


def _torso(px, P: Pal, belly: bool = True) -> None:
    px(9, 22, 14, 8, P.rim)
    px(10, 23, 12, 7, P.body)
    if belly:
        px(12, 24, 8, 5, P.belly)
    px(8, 28, 6, 2, P.rim)
    px(9, 28, 4, 2, P.body)
    px(18, 28, 6, 2, P.rim)
    px(19, 28, 4, 2, P.body)


def _tail(px, P: Pal, tip: str | None = None) -> None:
    px(24, 22, 5, 3, P.rim)
    px(27, 17, 3, 7, P.rim)
    px(25, 23, 3, 2, P.body)
    px(28, 18, 1, 5, P.body)
    if tip:
        px(27, 17, 3, 2, tip)


# ------------------------------------------------------------------ species
def _back(kind, px, P: Pal, frame: int) -> None:
    flap = (frame // 4) % 2
    if kind in ("panther", "cat"):
        _tail(px, P)
    elif kind == "bunny":
        px(23, 25, 6, 5, P.rim)
        px(24, 26, 4, 3, P.belly)
    elif kind == "fox":
        px(22, 18, 9, 8, P.rim)
        px(23, 19, 7, 6, P.accent if False else "#F28C3A")
        px(27, 21, 4, 5, WHITE)
    elif kind == "wolf":
        px(22, 17, 9, 9, P.rim)
        px(23, 18, 7, 7, P.body)
        px(25, 20, 3, 4, P.belly)
    elif kind == "fairy":
        wing = _light(P.accent, 120)
        for side in (0, 1):
            x = 0 if side == 0 else 25
            px(x, 12 - flap, 7, 9, P.rim)
            px(x + 1, 13 - flap, 5, 7, wing)
            px(x + 1, 21 - flap, 5, 4, wing)
    elif kind == "dragon":
        for side in (0, 1):
            x = 0 if side == 0 else 25
            px(x, 8 - flap * 2, 7, 12, P.rim)
            px(x + 1, 9 - flap * 2, 5, 10, _dark(P.body, 120))
        px(24, 24, 7, 3, P.rim)
        px(26, 22, 3, 3, P.accent)
    elif kind == "dino":
        px(23, 23, 8, 4, P.rim)
        px(24, 24, 7, 2, P.body)
        px(10, 7, 3, 5, P.rim)
        px(14, 6, 4, 6, P.rim)
        px(19, 7, 3, 5, P.rim)
    elif kind == "shark":
        px(24, 20, 7, 9, P.rim)
        px(25, 21, 5, 7, P.body)
    elif kind == "robot":
        px(3, 14, 4, 6, P.rim)
        px(25, 14, 4, 6, P.rim)
    elif kind == "astro":
        px(2, 14, 5, 12, P.rim)
        px(25, 14, 5, 12, P.rim)
    elif kind == "golem":
        px(0, 18, 7, 11, P.rim)
        px(25, 18, 7, 11, P.rim)
    elif kind == "ninja":
        px(25, 12, 6, 3, P.accent)
        px(27, 15 + flap, 4, 3, P.accent)
    elif kind == "owl":
        px(2, 18, 6, 11, P.rim)
        px(24, 18, 6, 11, P.rim)
    elif kind == "unicorn":
        px(23, 20, 8, 8, P.rim)
        px(24, 21, 6, 6, P.accent)
    elif kind == "axolotl":
        px(23, 21, 8, 6, P.rim)
        px(24, 22, 6, 4, P.accent)
    elif kind == "knight":
        px(1, 20, 7, 10, P.rim)
        px(2, 21, 5, 8, P.accent)
    elif kind == "dog":
        px(7, 23, 4, 7, "#1A1A1A")
        px(21, 23, 4, 7, "#1A1A1A")


def _ears(kind, px, P: Pal) -> None:
    if kind == "panther":
        _ears_pointed(px, P, inner="#4A2A30")
    elif kind == "cat":
        _ears_pointed(px, P, inner="#F4A6B8")
    elif kind == "bunny":
        _ears_tall(px, P)
    elif kind == "fox":
        _ears_pointed(px, P, inner=WHITE, tip="#2B2118")
    elif kind == "wolf":
        _ears_pointed(px, P, inner="#C9D0D8", tip="#4A5360")
    elif kind == "dog":
        _ears_round(px, P, "#1A1A1A")
    elif kind == "unicorn":
        _ears_pointed(px, P, inner="#F7A8FF")
    elif kind == "fairy":
        _ears_pointed(px, P, inner="#FFB3C9")
    elif kind == "owl":
        for x, y in ((5, 5), (22, 5)):
            px(x, y, 5, 7, P.rim)
            px(x + 1, y + 1, 3, 6, P.body)
    elif kind == "dragon":
        for x in (8, 21):
            px(x, 3, 4, 9, P.rim)
            px(x + 1, 4, 2, 8, P.accent)
        for x in (14, 16):
            px(x, 8, 2, 3, P.accent)
    elif kind == "dino":
        for x, h in ((10, 4), (14, 5), (18, 4)):
            px(x, 10 - h, 4, h + 1, P.rim)
            px(x + 1, 11 - h, 2, h, P.accent)
    elif kind == "shark":
        px(13, 1, 6, 11, P.rim)
        px(14, 2, 4, 10, P.body)
    elif kind == "axolotl":
        for side in (0, 1):
            for i in range(3):
                y = 8 + i * 4
                if side == 0:
                    px(0, y, 7, 3, P.rim)
                    px(1, y + 1, 5, 1, P.accent)
                else:
                    px(25, y, 7, 3, P.rim)
                    px(26, y + 1, 5, 1, P.accent)
    elif kind == "robot":
        px(15, 3, 2, 8, P.rim)
        px(12, 1, 8, 4, P.rim)
        px(13, 2, 6, 2, P.accent)
    elif kind == "astro":
        px(15, 1, 2, 6, P.rim)
        px(13, 0, 6, 3, P.accent)
    elif kind == "knight":
        px(13, 0, 6, 8, P.rim)
        px(14, 1, 4, 7, "#E84D4D")
    elif kind == "rover":
        px(5, 3, 22, 5, P.rim)
        px(6, 4, 20, 3, P.accent)
        px(15, 0, 2, 4, P.rim)
    elif kind == "golem":
        px(7, 4, 6, 6, P.rim)
        px(19, 5, 6, 5, P.rim)
        px(8, 5, 4, 4, P.body)
        px(20, 6, 4, 3, P.body)
    elif kind == "ninja":
        pass
    elif kind == "star":
        pass


def _head_for(kind, px, P: Pal) -> None:
    if kind == "slime":
        px(2, 11, 28, 18, P.rim)
        px(4, 9, 24, 3, P.rim)
        px(3, 12, 26, 16, P.body)
        px(5, 10, 22, 2, P.body)
        px(6, 12, 4, 3, WHITE)
        px(6, 15, 2, 2, WHITE)
        px(10, 18, 12, 6, P.belly)
        px(4, 28, 3, 3, P.body)
        px(24, 28, 3, 3, P.body)
    elif kind == "star":
        for x, y, w, h in ((13, 0, 6, 11), (0, 10, 12, 8), (20, 10, 12, 8), (4, 22, 9, 9), (19, 22, 9, 9), (6, 8, 20, 17)):
            px(x, y, w, h, P.rim)
        for x, y, w, h in ((14, 1, 4, 10), (1, 11, 11, 6), (20, 11, 11, 6), (5, 22, 7, 8), (20, 22, 7, 8), (7, 9, 18, 15)):
            px(x, y, w, h, P.body)
        px(10, 18, 12, 5, P.belly)
    elif kind == "robot":
        px(4, 9, 24, 15, P.rim)
        px(5, 10, 22, 13, P.body)
        px(7, 11, 18, 11, "#163242")
        px(2, 14, 3, 6, P.rim)
        px(27, 14, 3, 6, P.rim)
        px(11, 22, 10, 7, P.rim)
        px(12, 23, 8, 6, P.body)
    elif kind == "rover":
        px(4, 9, 24, 15, P.rim)
        px(5, 10, 22, 13, P.body)
        px(7, 11, 18, 11, "#1C2A33")
        for x in (2, 12, 22):
            px(x, 24, 8, 7, P.rim)
            px(x + 1, 25, 6, 5, P.ink)
            px(x + 3, 27, 2, 1, "#9AA4B2")
    elif kind == "golem":
        px(4, 8, 24, 17, P.rim)
        px(5, 9, 22, 15, P.body)
        px(7, 11, 18, 11, _dark(P.body, 125))
    elif kind == "astro":
        px(3, 6, 26, 20, P.rim)
        px(4, 7, 24, 18, P.body)
        px(6, 10, 20, 14, P.skin or "#FFE9D6")
        px(6, 10, 20, 2, P.accent)
        px(24, 8, 2, 2, WHITE)
    elif kind == "knight":
        px(4, 5, 24, 19, P.rim)
        px(5, 6, 22, 17, P.body)
        px(8, 12, 16, 11, P.skin or "#F3D3B3")
        px(5, 6, 22, 5, _light(P.body, 110))
    elif kind == "ninja":
        px(5, 10, 22, 14, P.rim)
        px(6, 11, 20, 12, P.body)
        px(7, 13, 18, 7, P.skin or "#E8C9A8")
        px(7, 20, 18, 3, "#2B3441")
    elif kind == "owl":
        px(4, 8, 24, 16, P.rim)
        px(5, 9, 22, 14, P.body)
        px(6, 11, 9, 9, P.belly)
        px(17, 11, 9, 9, P.belly)
    elif kind == "dog":
        _head(px, P)
        px(8, 12, 7, 7, "#1A1A1A")
        px(17, 12, 7, 7, "#1A1A1A")
    elif kind == "wolf":
        _head(px, P)
        px(4, 18, 4, 4, P.belly)
        px(24, 18, 4, 4, P.belly)
    elif kind == "fox":
        _head(px, P)
        px(4, 18, 5, 4, WHITE)
        px(23, 18, 5, 4, WHITE)
    else:
        _head(px, P)


def _torso_for(kind, px, P: Pal) -> None:
    if kind in ("slime", "star", "robot", "rover", "golem", "astro", "knight"):
        if kind == "knight":
            px(9, 22, 14, 8, P.rim)
            px(10, 23, 12, 7, P.body)
            px(14, 24, 4, 5, P.accent)
        elif kind == "astro":
            px(9, 22, 14, 8, P.rim)
            px(10, 23, 12, 7, P.body)
            px(14, 25, 4, 3, P.accent)
        elif kind == "golem":
            px(8, 22, 16, 8, P.rim)
            px(9, 23, 14, 7, P.body)
        return
    _torso(px, P, belly=kind not in ("dog", "dragon", "shark") or True)
    if kind == "shark":
        px(12, 24, 8, 5, WHITE)


def _front(kind, px, P: Pal, frame: int, expr: str) -> None:
    if kind == "cat":
        for x in (14, 16, 18):
            px(x, 11, 1, 3, P.rim)
    elif kind == "bunny" and expr in ("smile", "wink", "calm", "blink", "tongue"):
        px(15, 21, 2, 2, WHITE)
        px(15, 22, 2, 1, "#E8E8E8")
    elif kind == "unicorn":
        px(14, 0, 4, 11, P.rim)
        px(15, 1, 2, 9, P.accent)
        px(15, 3, 2, 1, WHITE)
        px(15, 6, 2, 1, WHITE)
        px(3, 9, 4, 14, "#FF8FB8")
        px(3, 14, 4, 4, "#8FD3FF")
        px(25, 9, 4, 14, "#FF8FB8")
        px(25, 14, 4, 4, "#8FD3FF")
    elif kind == "fairy":
        px(13, 4, 6, 7, P.rim)
        px(14, 5, 4, 5, "#F7D56A")
        px(24, 3, 3, 1, WHITE)
        px(25, 2, 1, 3, WHITE)
    elif kind == "owl":
        px(7, 12, 9, 1, P.rim)
        px(16, 12, 9, 1, P.rim)
        px(9, 20, 14, 1, P.rim)
    elif kind == "axolotl":
        px(2, 18, 2, 2, P.accent)
    elif kind == "dragon":
        if expr in ("smile", "wink", "calm", "tongue", "laugh"):
            px(12, 21, 1, 2, WHITE)
            px(19, 21, 1, 2, WHITE)
    elif kind == "dino":
        if expr in ("smile", "wink", "calm", "laugh"):
            px(13, 21, 1, 2, WHITE)
            px(18, 21, 1, 2, WHITE)
    elif kind == "shark":
        if expr in ("smile", "wink", "calm", "tongue", "laugh", "grumpy", "sly"):
            for x in (11, 13, 15, 17, 19):
                px(x, 21, 1, 1, WHITE)
        px(26, 17, 4, 3, P.rim)
        px(2, 17, 4, 3, P.rim)
    elif kind == "robot":
        px(8, 22, 2, 1, P.accent)
        px(22, 22, 2, 1, P.accent)
        px(10, 13, 1, 1, "#4FC3F7")
    elif kind == "knight":
        px(5, 12, 3, 11, _dark(P.body, 120))
        px(24, 12, 3, 11, _dark(P.body, 120))
    elif kind == "ninja":
        px(5, 10, 22, 3, P.accent)
        px(14, 10, 4, 3, _light(P.accent, 130))
    elif kind == "golem":
        px(6, 9, 5, 3, "#6FBF73")
        px(21, 10, 4, 2, "#6FBF73")
        px(14, 9, 1, 4, P.ink)
        px(15, 13, 1, 2, P.ink)
    elif kind == "rover":
        px(7, 22, 18, 1, P.accent)
    elif kind == "slime":
        px(15, 6, 2, 5, "#5FAF3A")
        px(17, 5, 4, 3, "#5FAF3A")
    elif kind == "wolf":
        px(14, 12, 4, 1, _dark(P.body, 140))
    elif kind == "fox":
        px(14, 12, 4, 2, "#F28C3A")


def paint_creature(px, kind: str, body: str, belly: str, ink: str, accent: str, expr: str, state: str, frame: int) -> None:
    P = Pal(kind, body, belly, ink, accent)
    _back(kind, px, P, frame)
    _torso_for(kind, px, P)
    _ears(kind, px, P)
    _head_for(kind, px, P)
    if kind == "axolotl":
        pass
    _front(kind, px, P, frame, expr)
    draw_face(px, P, expr, state, frame)


# ------------------------------------------------------------------ idle behaviour
FACES_FRONT = [
    (30, "smile"), (18, "cross"), (18, "tongue"), (18, "wink"), (20, "bigtongue"), (18, "silly"),
    (18, "puff"), (20, "laugh"), (18, "kiss"), (18, "dizzy"), (16, "surprised"), (18, "sly"),
    (18, "grumpy"), (20, "tongue"), (18, "cross"), (22, "yawn"), (18, "wink"), (20, "bigtongue"),
]

PANTHER_SCRIPT = [
    (30, "front", "smile"), (18, "front", "cross"), (18, "front", "tongue"), (20, "front", "bigtongue"),
    (13, "side_r", ""), (18, "front", "puff"), (20, "front", "laugh"), (18, "front", "wink"),
    (18, "front", "dizzy"), (12, "back", ""), (18, "front", "silly"), (18, "front", "kiss"),
    (18, "front", "grumpy"), (18, "front", "surprised"), (13, "side_l", ""), (18, "front", "sly"),
    (18, "front", "cross"), (20, "front", "tongue"), (22, "front", "yawn"), (18, "front", "laugh"),
    (18, "front", "bigtongue"), (18, "front", "wink"),
]


def idle_pose(frame: int, kind: str = "panther") -> tuple[str, str]:
    """Returns (pose, expression). Mostly funny faces; turning round is rare and short."""
    if kind == "panther":
        script = PANTHER_SCRIPT
    else:
        script = [(length, "front", face) for length, face in FACES_FRONT]
    total = sum(item[0] for item in script)
    tick = frame % total
    for length, pose, face in script:
        if tick < length:
            return pose, face
        tick -= length
    return "front", "smile"
