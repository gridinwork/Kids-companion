"""Small pixel-art objects for the mini-games. Every sprite is drawn in code (ASCII art + palette)."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtGui import QColor, QPainter


@lru_cache(maxsize=None)
def _color(value: str) -> QColor:
    return QColor(value)


# name -> (rows, palette). "." is transparent. Rows are padded to the widest row.
SPRITES: dict[str, tuple[list[str], dict[str, str]]] = {
    "cactus": (
        [
            ".....GG.....",
            "....GggG....",
            "....GggG.G..",
            ".G..GggG.GG.",
            ".GG.GggG.GG.",
            ".GG.GggGGGG.",
            ".GGGGggGGG..",
            "..GGGggG....",
            "....GggG....",
            "....GggG....",
            "....GggG....",
            "....GggG....",
        ],
        {"G": "#2E7D32", "g": "#6FCF6A"},
    ),
    "poop": (
        [
            "......bb......",
            ".....bBBb.....",
            "....bBBhBb....",
            ".....bBBBb....",
            "...bbBBBBBbb..",
            "..bBBBhBBBBBb.",
            "..bBwkBBwkBBb.",
            ".bBBBBBBBBBBBb",
            ".bBBBBkkkBBBBb",
            "bBBBBBBBBBBBBBb",
            "bbbbbbbbbbbbbbb",
        ],
        {"b": "#4A2C12", "B": "#8B5A2B", "h": "#B07A45", "w": "#FFFFFF", "k": "#1B1B1F"},
    ),
    "mouse": (
        [
            "...gg.........",
            "..geeg........",
            "..gggGGGG.....",
            ".GGGGGGGGGG...",
            "tGGGGGGGGGGGk.",
            ".tGGGGGGGGGGGp",
            "..GGGGGGGGGGG.",
            "..gg.GG..gg...",
        ],
        {"G": "#9AA3AD", "g": "#C9D0D8", "e": "#F4A6B8", "k": "#1B1B1F", "p": "#FF7AA2", "t": "#E8A0A8"},
    ),
    "spike": (
        [
            "..ss..",
            ".sdds.",
            ".sdds.",
            "sdddds",
        ],
        {"s": "#E1E7EE", "d": "#7B8794"},
    ),
    "flag": (
        [
            "prrrrr",
            "prrrrr",
            "prrrr.",
            "prrr..",
            "p.....",
            "p.....",
            "p.....",
            "p.....",
            "p.....",
            "pp....",
        ],
        {"p": "#B08A5A", "r": "#E85D4C"},
    ),
    "apple": (
        [
            "...bg..",
            "..gg...",
            ".rrrrr.",
            "rRrrrrr",
            "rRrrrrr",
            "rrrrrrr",
            ".rrrrr.",
            "..r.r..",
        ],
        {"r": "#E53935", "R": "#FF8A80", "g": "#43A047", "b": "#5D4037"},
    ),
    "fish": (
        [
            "...bbbb....B",
            ".bbbbbbbb.BB",
            "bbwkbbbbbBBB",
            ".bbbbbbbb.BB",
            "...bbbb....B",
        ],
        {"b": "#4FC3F7", "B": "#0288D1", "w": "#FFFFFF", "k": "#1B1B1F"},
    ),
    "bone": (
        [
            "ww......ww",
            "wwwwwwwwww",
            "wwsssssssw",
            "ww......ww",
        ],
        {"w": "#F5F0E1", "s": "#CFC7B0"},
    ),
    "bomb": (
        [
            ".....y.",
            "....sr.",
            "...s...",
            "..kkkk.",
            ".kgkkkk",
            "kgkkkkkk",
            "kkkkkkkk",
            "kkkkkkkk",
            ".kkkkkk.",
            "..kkkk..",
        ],
        {"k": "#2B2B33", "g": "#6A6A7C", "y": "#F6C453", "r": "#E85D4C", "s": "#8D6E63"},
    ),
    "star": (
        [
            "...y...",
            "...y...",
            "yyyyyyy",
            ".yyYyy.",
            "..yyy..",
            ".yy.yy.",
            "yy...yy",
        ],
        {"y": "#F6C453", "Y": "#FFF0B0"},
    ),
    "heart": (
        [
            ".rr.rr.",
            "rRrrrrr",
            "rrrrrrr",
            ".rrrrr.",
            "..rrr..",
            "...r...",
        ],
        {"r": "#FF5C7A", "R": "#FFB3C1"},
    ),
    "cheese": (
        [
            ".....yyy",
            "...yyyyy",
            ".yyhyyoy",
            "yyyyyyyy",
            "yoooooooo",
        ],
        {"y": "#F6C453", "o": "#E0A030", "h": "#FFE9A0"},
    ),
    "paw": (
        [
            ".pp..pp.",
            ".pp..pp.",
            "..pppp..",
            ".pppppp.",
            "pppppppp",
            ".pppppp.",
            "..p..p..",
        ],
        {"p": "#6A7586"},
    ),
    "alien": (
        [
            "..g.....g..",
            "...g...g...",
            "..ggggggg..",
            ".gg.ggg.gg.",
            "ggggggggggg",
            "g.ggggggg.g",
            "g.g.....g.g",
            "...gg.gg...",
        ],
        {"g": "#9BE564"},
    ),
    "ufo": (
        [
            "....pppp....",
            "..pppppppp..",
            ".ppcpcpcpcpp",
            "pppppppppppp",
            ".P.P.PP.P.P.",
        ],
        {"p": "#FF7AA2", "P": "#C23B6B", "c": "#BDF0FF"},
    ),
    "ship": (
        [
            ".....w.....",
            "....www....",
            "...wwbww...",
            "..wwwwwww..",
            ".wwwwwwwww.",
            "rw.wwwww.wr",
            "r....w....r",
        ],
        {"w": "#EDEDED", "b": "#4FC3F7", "r": "#E85D4C"},
    ),
    "cloud": (
        [
            "...www.....",
            "..wwwwww...",
            ".wwwwwwwww.",
            "wwwwwwwwwww",
        ],
        {"w": "#3B4656"},
    ),
    # top-down car, facing up. B is the body colour, w the glass.
    "car": (
        [
            "..yBBBBBBy..",
            ".kBBBBBBBBk.",
            ".kBBBBBBBBk.",
            ".kBwwwwwwBk.",
            "..BwwwwwwB..",
            "..BwwwwwwB..",
            "..BBBBBBBB..",
            "..BBBBBBBB..",
            ".kBBwwwwBBk.",
            ".kBBBBBBBBk.",
            "..BBBBBBBB..",
            "..rBBBBBBr..",
        ],
        {"B": "#E85D4C", "w": "#9ED8F5", "k": "#1B1B1F", "y": "#FFF2A8", "r": "#C0392B"},
    ),
    # open sports car for the pet: the cabin is left empty for the driver.
    "roadster": (
        [
            "..yBBBBBBy..",
            ".kBBBBBBBBk.",
            ".kBBBBBBBBk.",
            ".kBBBBBBBBk.",
            "..BDDDDDDB..",
            "..BDDDDDDB..",
            "..BDDDDDDB..",
            "..BDDDDDDB..",
            ".kBBBBBBBBk.",
            ".kBBBBBBBBk.",
            "..BBBBBBBB..",
            "..rBBBBBBr..",
        ],
        {"B": "#F6C453", "D": "#2A2118", "k": "#1B1B1F", "y": "#FFF2A8", "r": "#E85D4C"},
    ),
}

GOOD_ITEMS = ["apple", "fish", "bone", "cheese"]
BAD_ITEMS = ["bomb", "poop"]
CAR_COLORS = ["#E85D4C", "#4FC3F7", "#9BE564", "#B39DDB", "#FF9B71", "#F2F2F2"]
CARD_SYMBOLS = ["apple", "fish", "bone", "star", "mouse", "heart", "cheese", "poop"]


def sprite_size(name: str, scale: int) -> tuple[int, int]:
    rows, _pal = SPRITES[name]
    return max(len(row) for row in rows) * scale, len(rows) * scale


def draw_sprite(painter: QPainter, name: str, x: float, y: float, scale: int = 3, flip: bool = False, colors=None) -> None:
    rows, base = SPRITES[name]
    palette = {**base, **(colors or {})}
    width = max(len(row) for row in rows)
    for j, row in enumerate(rows):
        row = row.ljust(width, ".")
        if flip:
            row = row[::-1]
        i = 0
        while i < width:
            ch = row[i]
            if ch == ".":
                i += 1
                continue
            k = i
            while k < width and row[k] == ch:
                k += 1
            painter.fillRect(int(x + i * scale), int(y + j * scale), (k - i) * scale, scale, _color(palette[ch]))
            i = k


def bevel(painter: QPainter, x: int, y: int, w: int, h: int, color: str) -> None:
    base = _color(color)
    painter.fillRect(x, y, w, h, base)
    painter.fillRect(x, y, w, 2, base.lighter(145))
    painter.fillRect(x, y, 2, h, base.lighter(125))
    painter.fillRect(x, y + h - 2, w, 2, base.darker(155))
    painter.fillRect(x + w - 2, y, 2, h, base.darker(135))


def speckle(painter: QPainter, x: int, y: int, size: int, color: str, count: int, seed: int, dot: int = 4) -> None:
    span = max(1, size - dot)
    for i in range(count):
        px = (seed * 17 + i * 37) % span
        py = (seed * 29 + i * 53) % span
        painter.fillRect(x + px, y + py, dot, dot, _color(color))


def voxel_tile(painter: QPainter, x: int, y: int, size: int, kind: int, seed: int) -> None:
    if kind == 0:
        painter.fillRect(x, y, size, size, _color("#242A33"))
        painter.fillRect(x + 2, y + 2, size - 4, size - 4, _color("#1E242C"))
    elif kind == 1:  # grass over dirt
        bevel(painter, x, y, size, size, "#8A6848")
        speckle(painter, x, y, size, "#6E5238", 4, seed)
        painter.fillRect(x, y, size, 11, _color("#5FAF3A"))
        painter.fillRect(x, y, size, 3, _color("#86D95F"))
        for i in range(4):
            painter.fillRect(x + 3 + i * 9, y + 11, 4, 5 - (i + seed) % 3, _color("#5FAF3A"))
    elif kind == 2:  # dirt
        bevel(painter, x, y, size, size, "#8A6848")
        speckle(painter, x, y, size, "#6E5238", 5, seed)
        speckle(painter, x, y, size, "#A58060", 3, seed + 3, 3)
    elif kind == 3:  # stone
        bevel(painter, x, y, size, size, "#8E98A3")
        speckle(painter, x, y, size, "#737D88", 4, seed, 6)
        speckle(painter, x, y, size, "#A9B3BD", 3, seed + 5, 3)
    else:  # diamond ore
        bevel(painter, x, y, size, size, "#8E98A3")
        speckle(painter, x, y, size, "#737D88", 3, seed, 6)
        for i, (dx, dy) in enumerate(((6, 6), (21, 10), (11, 21), (24, 24))):
            painter.fillRect(x + dx, y + dy, 7, 7, _color("#3ED6C8"))
            painter.fillRect(x + dx, y + dy, 3, 3, _color("#D8FFFB"))


def ground_block(painter: QPainter, x: int, y: int, w: int, h: int) -> None:
    painter.fillRect(x, y, w, h, _color("#6B4A2B"))
    for i in range(max(1, w // 14)):
        painter.fillRect(x + 4 + i * 14, y + 8 + (i * 5) % max(2, h - 10), 4, 3, _color("#4E3520"))
    painter.fillRect(x, y, w, 6, _color("#5FAF3A"))
    painter.fillRect(x, y, w, 2, _color("#86D95F"))
    for i in range(w // 10 + 1):
        painter.fillRect(x + 2 + i * 10, y + 6, 4, 2 + (i % 2) * 2, _color("#5FAF3A"))
