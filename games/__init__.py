"""Ten short original mini-games.

Brick breaker, voxel mining and the block course use original shapes and colors.
They do not use Minecraft or Roblox assets, characters, logos or interface.
"""

from __future__ import annotations

import random
import time

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from logic import log_exception, praise, say
from petdraw import paint_pet
from sound import GAGS, play, play_gag
from .sprites import (
    BAD_ITEMS,
    CAR_COLORS,
    CARD_SYMBOLS,
    GOOD_ITEMS,
    bevel,
    draw_sprite,
    ground_block,
    speckle,
    sprite_size,
    voxel_tile,
)

GAME_NAMES = [
    "Arkanoid",
    "Voxel Miner",
    "Blocky Obby",
    "Snake",
    "Falling Blocks",
    "Catch",
    "Space Defender",
    "Memory",
    "Pixel Racer",
    "Jump Hero",
]

HELP = {
    "Arkanoid": "Мышь или ← → — ракетка. Раунд до 3 минут.",
    "Voxel Miner": "ЛКМ — добыть блок. ПКМ — поставить. Раунд до 3 минут.",
    "Blocky Obby": "← → — бег, пробел — прыжок. Дойди до флага.",
    "Snake": "Пробел — старт. Стрелки — поворот. Не врежься в стену и в себя.",
    "Falling Blocks": "← → — сдвиг, ↓ — быстрее, пробел — поворот, ↑ — сразу вниз.",
    "Catch": "← → — корзина. Лови падающие предметы.",
    "Space Defender": "← → — корабль, пробел — выстрел. Три волны.",
    "Memory": "Открывай пары одинаковых карточек.",
    "Pixel Racer": "← → — перестроение. Объезжай препятствия.",
    "Jump Hero": "Пробел или ↑ — прыжок. Пробеги как можно дальше.",
}

SHAPES = [
    [(0, 0), (1, 0), (2, 0), (3, 0)],
    [(0, 0), (1, 0), (0, 1), (1, 1)],
    [(0, 0), (1, 0), (2, 0), (1, 1)],
    [(0, 0), (0, 1), (0, 2), (1, 2)],
    [(1, 0), (2, 0), (0, 1), (1, 1)],
    [(0, 0), (1, 0), (1, 1), (2, 1)],
]
BLOCK_COLORS = ["#78DCE8", "#F6C453", "#FF7AA2", "#9BE564", "#B39DDB", "#FF9B71"]


class MiniGame(QWidget):
    def __init__(self, name: str, sound_enabled=lambda: True, sounds_dir=None, on_crash=None, on_close=None, log_path=None, voice="boy", skin=None, gender=None, on_win=None, bonus_minutes=None):
        super().__init__()
        self.on_win = on_win
        self.bonus_minutes = bonus_minutes if callable(bonus_minutes) else (lambda: 5)
        self.level = 1
        self.gender = gender if callable(gender) else (lambda: gender or "")
        self.skin = skin if callable(skin) else (lambda: skin or "Пантера")
        if name not in GAME_NAMES:
            raise ValueError(name)
        self.name = name
        self.sound_enabled = sound_enabled
        self.sounds_dir = sounds_dir
        self.voice = voice if voice in ("boy", "girl", "man", "woman") else "boy"
        self._cheers = 0
        self.on_crash = on_crash
        self.on_close = on_close
        self.log_path = log_path
        self.setWindowTitle(f"Мини-игра — {name}")
        self.setFixedSize(640, 500)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.round_limit = 180
        self.reset_round()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(33)
        self._paused_at = None

    def reset_round(self):
        self.started = time.monotonic()
        self.frame = 0
        self.score = 0
        self.over = False
        self.over_text = ""
        self.keys = set()
        self.emote = ""
        self.emote_until = 0
        self.hop_until = 0
        self.won = False
        self.over_hint = ""
        self.target = 0
        lv = self.level - 1
        kind = self.name
        if kind == "Arkanoid":
            self.px = 320
            self.bx, self.by = 320.0, 300.0
            self.mul = (1.0, 1.25, 1.5)[lv]
            self.bdx, self.bdy = 4.2 * self.mul, -4.4 * self.mul
            self.lives = 3
            self.bricks = []
            for row in range((3, 4, 5)[lv]):
                for col in range(8):
                    self.bricks.append([28 + col * 74, 36 + row * 26, 66, 18, True, (col * 36 + row * 18) % 360])
        elif kind == "Voxel Miner":
            self.grid = [[0 for _ in range(12)] for _ in range(8)]
            for y in range(8):
                for x in range(12):
                    if y == 2:
                        self.grid[y][x] = 1
                    elif y > 2:
                        self.grid[y][x] = 4 if (x + y) % 7 == 0 else 3 if y > 5 else 2
            self.inventory = 0
            self.cursor = (0, 0)
            self.target = (30, 60, 100)[lv]
        elif kind == "Blocky Obby":
            self.px, self.py = 40.0, 408.0
            self.vx, self.vy = 0.0, 0.0
            self.on_ground = True
            self.platforms = [
                (0, 440, 190, 18),
                (230, 390, 120, 16),
                (400, 340, 110, 16),
                (250, 280, 110, 16),
                (80, 230, 120, 16),
                (280, 170, 130, 16),
                (470, 120, 120, 16),
            ]
            self.hazards = [(210, 448, 36, 12), (360, 448, 50, 12)]
            if lv >= 1:
                self.hazards += [(268, 374, 24, 16), (432, 324, 24, 16)]
            if lv >= 2:
                self.hazards += [(300, 264, 24, 16), (112, 214, 24, 16), (506, 104, 24, 16)]
            self.goal = (540, 78, 28, 40)
        elif kind == "Snake":
            self.waiting = True
            self.snake_every = (6, 5, 4)[lv]
            self.target = (5, 10, 15)[lv]
            self.snake = [(8, 8), (7, 8), (6, 8)]
            self.direction = (1, 0)
            self.next_dir = (1, 0)
            self.food = (14, 8)
        elif kind == "Falling Blocks":
            self.well = [[0 for _ in range(10)] for _ in range(18)]
            self.drop_acc = 0
            self.lines = 0
            self.base_drop = (28, 20, 14)[lv]
            self.target = (3, 6, 10)[lv]
            self._spawn_piece()
        elif kind == "Catch":
            self.basket = 280
            self.items = []
            self.lives = 3
            self.spawn_every = (28, 24, 20)[lv]
            self.fall_base = (4, 5, 6)[lv]
            self.target = (15, 25, 40)[lv]
        elif kind == "Space Defender":
            self.ship = 300
            self.bullets = []
            self.rows = (2, 3, 4)[lv]
            self.dx_base = (2, 3, 4)[lv]
            self.enemies = [{"x": 40 + col * 70, "y": 40 + row * 36, "alive": True} for row in range(self.rows) for col in range(8)]
            self.enemy_dx = self.dx_base
            self.cooldown = 0
            self.wave = 1
        elif kind == "Memory":
            symbols = list(range(8)) * 2
            random.shuffle(symbols)
            self.cards = symbols
            self.opened = []
            self.matched = set()
            self.wait = 0
            self.wait_frames = (36, 24, 14)[lv]
            self.moves = 0
        elif kind == "Pixel Racer":
            self.lane = 1
            self.obstacles = []
            self.distance = 0
            self.road_off = 0
            self.base_speed = (5, 6, 7)[lv]
            self.speed = self.base_speed
            self.target = (60, 120, 200)[lv]
        elif kind == "Jump Hero":
            self.hx, self.hy = 80.0, 360.0
            self.hvy = 0.0
            self.h_ground = True
            self.obstacles = [{"x": 700, "w": 36, "h": 36, "kind": "cactus"}]
            self.run = 0
            self.obst_every = (55, 45, 38)[lv]
            self.jump_speed = (5, 6, 7)[lv]
            self.target = (100, 200, 300)[lv]

    def pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self._paused_at = time.monotonic()

    def resume(self):
        if self._paused_at:
            self.started += time.monotonic() - self._paused_at
            self._paused_at = None
        if not self.timer.isActive() and not self.over:
            self.timer.start(33)

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
        if self.on_close:
            self.on_close(self)

    def _on_timer(self):
        try:
            if self.over:
                return
            self.frame += 1
            if self.name != "Memory" and time.monotonic() - self.started >= self.round_limit:
                self.finish("Время вышло. Давай ещё, когда захочешь!")
                return
            self.step()
            self.update()
        except Exception:
            log_exception(self.log_path, f"game crash: {self.name}")
            self.timer.stop()
            if self.on_crash:
                self.on_crash(self.name)
            self.close()

    def finish(self, text: str):
        self.over = True
        self.over_text = say(text)
        self.timer.stop()
        if self.sounds_dir is not None:
            play_gag(self.sounds_dir, self.voice, "giggle", bool(self.sound_enabled()))
        else:
            self._blip("celebration.wav")
        self.update()

    def _emote(self, expr: str, frames: int = 14):
        self.emote = expr
        self.emote_until = self.frame + frames

    def _face(self) -> str:
        if self.over:
            return "laugh" if self.score > 0 else "surprised"
        if self.frame < self.emote_until:
            return self.emote
        return ""

    def _pet(self, painter, x, bottom, size, state="HAPPY", expr=None):
        """Draw the chosen pet; x is the left edge, bottom is the line its feet stand on."""
        face = self._face() if expr is None else expr
        top = int(bottom - size * 0.92)
        paint_pet(painter, QRect(int(x), top, int(size), int(size)), self.skin(), state, self.frame, "", face)

    def _blip(self, name="game.wav"):
        if name == "game.wav":
            self._emote("laugh")
        elif name == "game_low.wav":
            self._emote("surprised")
        if self.sounds_dir is None:
            return
        if name == "game.wav":
            self._cheers += 1
            if self._cheers % 4 == 0:
                play_gag(self.sounds_dir, self.voice, GAGS[(self._cheers // 4) % len(GAGS)], bool(self.sound_enabled()))
                return
        play(self.sounds_dir, name, bool(self.sound_enabled()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R and self.over:
            if self.won:
                self.level = self.level + 1 if self.level < 3 else 1
            self.reset_round()
            self.timer.start(33)
            return
        self.keys.add(event.key())
        if self.over:
            return
        if self.name == "Snake":
            if self.waiting:
                if event.key() == Qt.Key_Space:
                    self.waiting = False
                    self.started = time.monotonic()
                self.update()
                return
            mapping = {
                Qt.Key_Left: (-1, 0),
                Qt.Key_Right: (1, 0),
                Qt.Key_Up: (0, -1),
                Qt.Key_Down: (0, 1),
            }
            nxt = mapping.get(event.key())
            if nxt and (nxt[0] != -self.direction[0] or nxt[1] != -self.direction[1]):
                self.next_dir = nxt
        elif self.name == "Falling Blocks":
            if event.key() == Qt.Key_Left:
                self._shift_piece(-1, 0)
            elif event.key() == Qt.Key_Right:
                self._shift_piece(1, 0)
            elif event.key() == Qt.Key_Space:
                self._rotate_piece()
            elif event.key() == Qt.Key_Down:
                self._shift_piece(0, 1)
            elif event.key() == Qt.Key_Up:
                while self._shift_piece(0, 1):
                    self.score += 1
        elif self.name == "Memory":
            pass
        elif self.name == "Pixel Racer":
            if event.key() == Qt.Key_Left:
                self.lane = max(0, self.lane - 1)
            elif event.key() == Qt.Key_Right:
                self.lane = min(2, self.lane + 1)
        self.update()

    def keyReleaseEvent(self, event):
        self.keys.discard(event.key())

    def mouseMoveEvent(self, event):
        if self.name == "Arkanoid" and not self.over:
            self.px = max(50, min(590, event.position().x()))

    def mousePressEvent(self, event):
        if self.over:
            return
        pos = event.position()
        if self.name == "Voxel Miner":
            cell = self._voxel_cell(pos.x(), pos.y())
            if not cell:
                return
            x, y = cell
            self.cursor = cell
            if event.button() == Qt.LeftButton and self.grid[y][x]:
                kind = self.grid[y][x]
                self.grid[y][x] = 0
                self.inventory += 1
                self.score += {1: 1, 2: 2, 3: 4, 4: 8}.get(kind, 1)
                self._blip()
            elif event.button() == Qt.RightButton and self.grid[y][x] == 0 and self.inventory:
                self.grid[y][x] = 2
                self.inventory -= 1
                self._blip("game_low.wav")
        elif self.name == "Memory":
            self._memory_click(pos.x(), pos.y())
        self.update()

    def step(self):
        self._step_game()
        self._check_goal()

    def _progress(self) -> int:
        return self.lines if self.name == "Falling Blocks" else self.score

    def _check_goal(self):
        if self.target and not self.over and self._progress() >= self.target:
            self.win(f"Уровень {self.level} пройден! {praise(self.gender())}")

    def win(self, text: str):
        if self.over:
            return
        self.won = True
        minutes = int(self.bonus_minutes())
        if self.level >= 3:
            # extra time is paid once, only for finishing all three levels
            granted = 0
            if minutes > 0 and self.on_win:
                granted = int(self.on_win(minutes) or 0)
            bonus = f"+{granted} мин игры! " if granted > 0 else "Бонус на сегодня уже получен. "
            self.over_hint = f"{bonus}3 победы из 3! R — сыграть заново"
        else:
            tail = f" Пройди все 3 уровня — получишь +{minutes} мин." if minutes > 0 else ""
            self.over_hint = f"R — уровень {self.level + 1} из 3.{tail}"
        self.finish(text)

    def _step_game(self):
        name = self.name
        if name == "Arkanoid":
            self._step_arkanoid()
        elif name == "Snake":
            if self.waiting:
                self.started = time.monotonic()
            elif self.frame % self.snake_every == 0:
                self._step_snake()
        elif name == "Falling Blocks":
            self._step_blocks()
        elif name == "Catch":
            self._step_catch()
        elif name == "Space Defender":
            self._step_space()
        elif name == "Memory":
            if self.wait:
                self.wait -= 1
                if self.wait == 0:
                    self.opened = []
        elif name == "Pixel Racer":
            self._step_racer()
        elif name == "Jump Hero":
            self._step_jump()
        elif name == "Blocky Obby":
            self._step_obby()
        elif name == "Voxel Miner":
            pass

    def _step_arkanoid(self):
        if Qt.Key_Left in self.keys:
            self.px -= 8
        if Qt.Key_Right in self.keys:
            self.px += 8
        self.px = max(50, min(590, self.px))
        self.bx += self.bdx
        self.by += self.bdy
        if self.bx < 12 or self.bx > 628:
            self.bdx *= -1
        if self.by < 12:
            self.bdy = abs(self.bdy)
        for brick in self.bricks:
            if not brick[4]:
                continue
            x, y, w, h = brick[:4]
            if x <= self.bx <= x + w and y <= self.by <= y + h:
                brick[4] = False
                self.bdy *= -1
                self.score += 10
                self._blip()
                break
        if 430 <= self.by <= 454 and abs(self.bx - self.px) < 58 and self.bdy > 0:
            self.bdy = -abs(self.bdy)
            self.bdx += (self.bx - self.px) / 18
            self.bdx = max(-7, min(7, self.bdx))
            self._blip()
        if abs(self.bdy) < 2:
            self.bdy = -3 if self.bdy < 0 else 3
        if self.by > 490:
            self.lives -= 1
            self.bx, self.by = float(self.px), 360.0
            self.bdy = -4.4 * self.mul
            if self.lives <= 0:
                self.finish("Попытки кончились. Ещё разок?")
                return
        if self.bricks and all(not brick[4] for brick in self.bricks):
            self.win(f"Все блоки разбиты! {praise(self.gender())}")

    def _step_snake(self):
        self.direction = self.next_dir
        head_x, head_y = self.snake[0]
        nxt = (head_x + self.direction[0], head_y + self.direction[1])
        if nxt[0] < 0 or nxt[1] < 0 or nxt[0] >= 20 or nxt[1] >= 16 or nxt in self.snake:
            self.finish("Ой, змейка столкнулась. Ещё разок?")
            return
        self.snake.insert(0, nxt)
        if nxt == self.food:
            self.score += 1
            self._blip()
            choices = [(x, y) for x in range(20) for y in range(16) if (x, y) not in self.snake]
            self.food = random.choice(choices) if choices else nxt
        else:
            self.snake.pop()

    def _spawn_piece(self):
        shape = random.choice(SHAPES)
        color = random.randrange(1, len(BLOCK_COLORS) + 1)
        self.piece = [(3 + x, y) for x, y in shape]
        self.piece_color = color
        if not self._fits(self.piece):
            self.finish("Стакан полный. Здорово играли!")

    def _fits(self, cells):
        for x, y in cells:
            if x < 0 or x >= 10 or y >= 18:
                return False
            if y >= 0 and self.well[y][x]:
                return False
        return True

    def _shift_piece(self, dx, dy):
        moved = [(x + dx, y + dy) for x, y in self.piece]
        if self._fits(moved):
            self.piece = moved
            return True
        return False

    def _rotate_piece(self):
        pivot_x, pivot_y = self.piece[0]
        rotated = []
        for x, y in self.piece:
            dx, dy = x - pivot_x, y - pivot_y
            rotated.append((pivot_x - dy, pivot_y + dx))
        if self._fits(rotated):
            self.piece = rotated

    def _lock_piece(self):
        for x, y in self.piece:
            if y >= 0:
                self.well[y][x] = self.piece_color
        cleared = 0
        kept = []
        for row in self.well:
            if all(row):
                cleared += 1
            else:
                kept.append(row)
        while len(kept) < 18:
            kept.insert(0, [0] * 10)
        self.well = kept
        if cleared:
            self.lines += cleared
            self.hop_until = self.frame + 24
            self._emote("laugh", 24)
            self.score += cleared * 10
            self._blip()

    def _step_blocks(self):
        self.drop_acc += 1
        speed = 8 if Qt.Key_Down in self.keys else max(6, self.base_drop - self.score // 20)
        if self.drop_acc < speed:
            return
        self.drop_acc = 0
        if not self._shift_piece(0, 1):
            self._lock_piece()
            if not self.over:
                self._spawn_piece()

    def _step_catch(self):
        if Qt.Key_Left in self.keys:
            self.basket -= 8
        if Qt.Key_Right in self.keys:
            self.basket += 8
        self.basket = max(10, min(560, self.basket))
        if self.frame % self.spawn_every == 0:
            good = random.random() > 0.2
            self.items.append(
                {"x": random.randint(20, 600), "y": 40, "good": good, "kind": random.choice(GOOD_ITEMS if good else BAD_ITEMS)}
            )
        kept = []
        for item in self.items:
            item["y"] += self.fall_base + self.score // 8
            if item["y"] >= 430 and abs(item["x"] - (self.basket + 35)) < 48:
                if item["good"]:
                    self.score += 1
                    self._blip()
                else:
                    self.lives -= 1
                    self._blip("game_low.wav")
            elif item["y"] > 480:
                if item["good"]:
                    self.lives -= 1
            else:
                kept.append(item)
        self.items = kept
        if self.lives <= 0:
            self.finish("Корзина пустая. Попробуем ещё?")

    def _step_space(self):
        if Qt.Key_Left in self.keys:
            self.ship -= 6
        if Qt.Key_Right in self.keys:
            self.ship += 6
        self.ship = max(20, min(600, self.ship))
        self.cooldown = max(0, self.cooldown - 1)
        if Qt.Key_Space in self.keys and self.cooldown == 0:
            self.bullets.append([self.ship + 12, 400])
            self.cooldown = 12
            self._blip()
        self.bullets = [[x, y - 9] for x, y in self.bullets if y > 0]
        alive = [enemy for enemy in self.enemies if enemy["alive"]]
        if alive:
            xs = [enemy["x"] for enemy in alive]
            if min(xs) < 10 or max(xs) > 580:
                self.enemy_dx *= -1
                for enemy in alive:
                    enemy["y"] += 12
            for enemy in alive:
                enemy["x"] += self.enemy_dx
        for bullet in self.bullets:
            for enemy in self.enemies:
                if not enemy["alive"]:
                    continue
                if enemy["x"] <= bullet[0] <= enemy["x"] + 28 and enemy["y"] <= bullet[1] <= enemy["y"] + 20:
                    enemy["alive"] = False
                    bullet[1] = -20
                    self.score += 5
                    self._blip()
                    break
        for enemy in self.enemies:
            if enemy["alive"] and enemy["y"] > 390 and abs((enemy["x"] + 14) - (self.ship + 16)) < 30:
                self.finish("Ой, корабль подбит. Ещё разок?")
                return
        if alive and max(enemy["y"] for enemy in alive) > 430:
            self.finish("Волна прошла. Давай ещё раз!")
            return
        if not any(enemy["alive"] for enemy in self.enemies):
            if self.wave >= 3:
                self.win(f"Три волны отбиты! {praise(self.gender())}")
            else:
                self.wave += 1
                self.enemies = [
                    {"x": 40 + col * 70, "y": 30 + row * 34, "alive": True}
                    for row in range(self.rows)
                    for col in range(8)
                ]
                self.enemy_dx = self.dx_base + self.wave

    def _memory_click(self, x, y):
        if self.wait or len(self.opened) >= 2:
            return
        for index in range(16):
            col, row = index % 4, index // 4
            left, top = 150 + col * 90, 70 + row * 90
            if left <= x <= left + 72 and top <= y <= top + 72 and index not in self.matched and index not in self.opened:
                self.opened.append(index)
                self._blip()
                if len(self.opened) == 2:
                    self.moves += 1
                    a, b = self.opened
                    if self.cards[a] == self.cards[b]:
                        self.matched.update(self.opened)
                        self.opened = []
                        self.score = len(self.matched) // 2
                        if len(self.matched) == 16:
                            self.win(f"Пары найдены за {self.moves} ходов. {praise(self.gender())}")
                    else:
                        self.wait = self.wait_frames
                        self._emote("surprised", 24)
                return

    def _step_racer(self):
        self.distance += 1
        self.road_off = (self.road_off + self.speed) % 64
        self.score = self.distance // 10
        self.speed = self.base_speed + min(8, self.distance // 400)
        if self.frame % max(18, 40 - self.speed * 2) == 0:
            busy = {item["lane"] for item in self.obstacles if item["y"] < 40}
            lanes = [lane for lane in range(3) if lane not in busy] or [random.randrange(3)]
            self.obstacles.append(
                {"lane": random.choice(lanes), "y": -60, "v": random.choice((1, 2, 2, 3)), "color": random.choice(CAR_COLORS)}
            )
        player_y = 390
        kept = []
        for item in self.obstacles:
            item["y"] += self.speed - item["v"]
            lane_x = 150 + item["lane"] * 140
            player_x = 150 + self.lane * 140
            if abs(lane_x - player_x) < 20 and abs(item["y"] - player_y) < 36:
                self.finish("Гонка окончена. Было весело!")
                return
            if item["y"] < 520:
                kept.append(item)
        self.obstacles = kept

    def _step_jump(self):
        if (Qt.Key_Space in self.keys or Qt.Key_Up in self.keys) and self.h_ground:
            self.hvy = -12
            self.h_ground = False
            self._blip()
        self.hvy = min(12, self.hvy + 0.7)
        self.hy += self.hvy
        if self.hy >= 360:
            self.hy = 360
            self.hvy = 0
            self.h_ground = True
        self.run += 4
        self.score = self.run // 20
        if self.frame % self.obst_every == 0:
            kind = random.choice(("cactus", "poop", "mouse", "cactus", "mouse"))
            width, height = sprite_size(kind, 3)
            self.obstacles.append({"x": 680, "w": width, "h": height, "kind": kind})
        kept = []
        for item in self.obstacles:
            item["x"] -= self.jump_speed + (2 if item.get("kind") == "mouse" else 0)
            top = 392 - item["h"]
            if self.hx + 24 > item["x"] + 6 and self.hx + 4 < item["x"] + item["w"] - 6 and self.hy + 32 > top:
                self.finish("Прыжок не вышел. Ещё разок?")
                return
            if item["x"] > -40:
                kept.append(item)
        self.obstacles = kept

    def _step_obby(self):
        self.vx = 0
        if Qt.Key_Left in self.keys or Qt.Key_A in self.keys:
            self.vx = -4
        if Qt.Key_Right in self.keys or Qt.Key_D in self.keys:
            self.vx += 4
        if (Qt.Key_Space in self.keys or Qt.Key_Up in self.keys or Qt.Key_W in self.keys) and self.on_ground:
            self.vy = -11
            self.on_ground = False
            self._blip()
        self.vy = min(14, self.vy + 0.65)
        self.px += self.vx
        self.px = max(0, min(610, self.px))
        self.py += self.vy
        self.on_ground = False
        landed = None
        feet = self.py + 32
        previous_feet = feet - self.vy
        for plat in self.platforms:
            px, py, pw, _ph = plat
            horizontal = self.px < px + pw and self.px + 22 > px
            if horizontal and self.vy >= 0 and previous_feet <= py + 2 and feet >= py:
                if landed is None or py < landed[1]:
                    landed = plat
        if landed:
            self.py = landed[1] - 32
            self.vy = 0
            self.on_ground = True
        for hazard in self.hazards:
            if _overlap((self.px, self.py, 22, 32), hazard):
                self.px, self.py = 40.0, 408.0
                self.vy = 0
                self.on_ground = True
                self._blip("game_low.wav")
        if self.py > 500:
            self.px, self.py = 40.0, 408.0
            self.vy = 0
            self.on_ground = True
        if _overlap((self.px, self.py, 22, 32), self.goal):
            self.score = 1
            self.win(f"Полоса пройдена! {praise(self.gender())}")

    def _voxel_cell(self, x, y):
        left, top, size = 70, 70, 40
        col = int((x - left) // size)
        row = int((y - top) // size)
        if 0 <= col < 12 and 0 <= row < 8:
            return col, row
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#161A20"))
            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.setPen(Qt.white)
            painter.drawText(16, 24, f"{self.name}  победы {self.level - 1}/3  счёт {self.score}")
            if self.target:
                painter.setFont(QFont("Segoe UI", 10))
                painter.drawText(330, 24, f"цель {min(self._progress(), self.target)}/{self.target}")
                painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(16, 488, say(HELP[self.name]) + ("    R — ещё раз" if self.over else ""))
            {
                "Arkanoid": self._paint_arkanoid,
                "Voxel Miner": self._paint_voxel,
                "Blocky Obby": self._paint_obby,
                "Snake": self._paint_snake,
                "Falling Blocks": self._paint_blocks,
                "Catch": self._paint_catch,
                "Space Defender": self._paint_space,
                "Memory": self._paint_memory,
                "Pixel Racer": self._paint_racer,
                "Jump Hero": self._paint_jump,
            }[self.name](painter)
            if self.over:
                painter.fillRect(80, 180, 480, 110, QColor(10, 12, 16, 220))
                painter.setPen(Qt.white)
                painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
                painter.drawText(QRect(80, 200, 480, 40), Qt.AlignCenter, self.over_text)
                painter.setFont(QFont("Segoe UI", 10))
                painter.drawText(QRect(80, 240, 480, 30), Qt.AlignCenter, say(self.over_hint) if self.over_hint else "R — сыграть ещё раз")
        finally:
            painter.end()

    def _paint_arkanoid(self, painter: QPainter):
        for brick in self.bricks:
            if brick[4]:
                bevel(painter, brick[0], brick[1], brick[2], brick[3], QColor.fromHsv(brick[5], 150, 230).name())
                painter.fillRect(brick[0] + brick[2] // 2 - 6, brick[1] + brick[3] // 2 - 1, 12, 2, QColor(255, 255, 255, 70))
        self._pet(painter, int(self.px) - 22, 440, 44, "EXERCISE" if self.frame < self.emote_until else "HAPPY")
        bevel(painter, int(self.px) - 50, 440, 100, 12, "#D9DEE6")
        painter.fillRect(int(self.px) - 50, 440, 12, 12, QColor("#E85D4C"))
        painter.fillRect(int(self.px) + 38, 440, 12, 12, QColor("#E85D4C"))
        painter.setBrush(QColor("#F6C453"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(self.bx) - 7, int(self.by) - 7, 14, 14)
        painter.setBrush(QColor("#FFF3C4"))
        painter.drawEllipse(int(self.bx) - 4, int(self.by) - 5, 5, 5)
        painter.setPen(Qt.white)
        painter.drawText(520, 24, f"жизни {self.lives}")

    def _paint_voxel(self, painter: QPainter):
        for y in range(8):
            for x in range(12):
                voxel_tile(painter, 70 + x * 40, 70 + y * 40, 36, self.grid[y][x], x * 5 + y * 3)
        cx, cy = self.cursor
        self._pet(painter, 70 + cx * 40 - 2, 150, 44, "EXERCISE" if self.frame < self.emote_until else "HAPPY")
        painter.setPen(QPen(QColor("#F6C453"), 2))
        painter.drawRect(70 + cx * 40, 70 + cy * 40, 36, 36)
        painter.setPen(Qt.white)
        painter.drawText(70, 420, f"в рюкзаке блоков: {self.inventory}")

    def _paint_obby(self, painter: QPainter):
        ground_block(painter, 0, 458, 640, 22)
        for plat in self.platforms:
            ground_block(painter, plat[0], plat[1], plat[2], max(plat[3], 16))
        for hx, hy, hw, hh in self.hazards:
            count = max(1, hw // 18 + (1 if hw % 18 else 0))
            for i in range(count):
                draw_sprite(painter, "spike", hx + i * 18, hy + hh - 12, 3)
        gx, gy, gw, gh = self.goal
        draw_sprite(painter, "flag", gx, gy, 4)
        self._pet(painter, int(self.px) - 11, int(self.py) + 32, 44, "HAPPY" if self.on_ground else "EXERCISE")

    def _paint_snake(self, painter: QPainter):
        for index, (x, y) in enumerate(self.snake[1:]):
            tone = "#7FD35A" if index % 2 == 0 else "#69BF47"
            bevel(painter, 16 + x * 28, 40 + y * 26, 24, 22, tone)
            painter.fillRect(16 + x * 28 + 9, 40 + y * 26 + 8, 6, 6, QColor("#4F9F32"))
        draw_sprite(painter, "apple", 16 + self.food[0] * 28 + 1, 40 + self.food[1] * 26 - 1, 3)
        head_x, head_y = self.snake[0]
        self._pet(painter, 16 + head_x * 28 + 12 - 19, 40 + head_y * 26 + 11 + 17, 38)
        if self.waiting:
            painter.fillRect(120, 190, 400, 90, QColor(10, 12, 16, 220))
            painter.setPen(Qt.white)
            painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
            painter.drawText(QRect(120, 205, 400, 40), Qt.AlignCenter, say("Нажми пробел, чтобы начать"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(QRect(120, 245, 400, 30), Qt.AlignCenter, "Стрелки — поворот")

    def _paint_blocks(self, painter: QPainter):
        origin_x, origin_y, size = 200, 40, 22
        hop = 14 * abs((self.frame % 6) - 3) // 3 if self.frame < self.hop_until else 0
        danger = any(self.well[3])
        self._pet(painter, 28, 430 - hop, 150, "EXERCISE" if hop else "HAPPY", "surprised" if danger and not self.over else None)
        painter.fillRect(origin_x, origin_y, 10 * size, 18 * size, QColor("#12161C"))
        painter.setPen(QColor("#222831"))
        for col in range(1, 10):
            painter.drawLine(origin_x + col * size, origin_y, origin_x + col * size, origin_y + 18 * size)
        for row in range(1, 18):
            painter.drawLine(origin_x, origin_y + row * size, origin_x + 10 * size, origin_y + row * size)
        painter.setPen(QColor("#394049"))
        painter.drawRect(origin_x - 2, origin_y - 2, 10 * size + 4, 18 * size + 4)
        for y, row in enumerate(self.well):
            for x, cell in enumerate(row):
                if cell:
                    bevel(painter, origin_x + x * size, origin_y + y * size, size - 1, size - 1, BLOCK_COLORS[cell - 1])
        if not self.over:
            for x, y in self.piece:
                if y >= 0:
                    bevel(painter, origin_x + x * size, origin_y + y * size, size - 1, size - 1, BLOCK_COLORS[self.piece_color - 1])

    def _paint_catch(self, painter: QPainter):
        self._pet(painter, int(self.basket) + 35 - 30, 442, 60, "EXERCISE" if self.frame < self.emote_until else "HAPPY")
        bx = int(self.basket)
        painter.fillRect(bx, 440, 70, 14, QColor("#C98A3A"))
        for i in range(1, 7):
            painter.fillRect(bx + i * 10 - 2, 444, 2, 10, QColor("#8F5E22"))
        painter.fillRect(bx, 440, 70, 4, QColor("#E6B060"))
        painter.fillRect(bx, 452, 70, 2, QColor("#8F5E22"))
        for item in self.items:
            draw_sprite(painter, item.get("kind", "apple"), int(item["x"]) - 4, int(item["y"]) - 4, 3)
        painter.setPen(Qt.white)
        painter.drawText(520, 24, f"жизни {self.lives}")

    def _paint_space(self, painter: QPainter):
        for i in range(40):
            sx = (i * 97) % 640
            sy = (i * 61 + self.frame // 3 * (1 + i % 3)) % 470
            painter.fillRect(sx, sy, 2, 2, QColor(255, 255, 255, 60 + (i % 4) * 30))
        low = any(e["alive"] and e["y"] > 300 for e in self.enemies)
        self._pet(painter, int(self.ship) + 16 - 22, 424, 44, "HAPPY", "surprised" if low and self.frame >= self.emote_until else None)
        draw_sprite(painter, "ship", int(self.ship) - 1, 414, 3)
        for x, y in self.bullets:
            painter.fillRect(int(x), int(y), 4, 12, QColor("#F6C453"))
            painter.fillRect(int(x) + 1, int(y), 2, 6, QColor("#FFFFFF"))
        for index, enemy in enumerate(self.enemies):
            if enemy["alive"]:
                kind = "alien" if (index // 8) % 2 == 0 else "ufo"
                draw_sprite(painter, kind, int(enemy["x"]) - 3, int(enemy["y"]) - 2, 3)
        painter.setPen(Qt.white)
        painter.drawText(500, 24, f"волна {self.wave}/3")

    def _paint_memory(self, painter: QPainter):
        self._pet(painter, 14, 300, 120, "EXERCISE" if self.frame < self.emote_until else "HAPPY", "surprised" if self.wait else None)
        for index, symbol in enumerate(self.cards):
            col, row = index % 4, index // 4
            left, top = 150 + col * 90, 70 + row * 90
            shown = index in self.matched or index in self.opened
            if shown:
                bevel(painter, left, top, 72, 72, "#F6E8C8" if index not in self.matched else "#CDEFB8")
                name = CARD_SYMBOLS[symbol]
                width, height = sprite_size(name, 4)
                draw_sprite(painter, name, left + (72 - width) // 2, top + (72 - height) // 2, 4)
            else:
                bevel(painter, left, top, 72, 72, "#3A4250")
                draw_sprite(painter, "paw", left + 12, top + 14, 6)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(16, 460, f"ходы {self.moves}")

    def _paint_racer(self, painter: QPainter):
        # grass, road, kerbs and scrolling lane marks
        painter.fillRect(0, 34, 640, 436, QColor("#2F6B33"))
        for i in range(40):
            gx = (i * 53) % 640
            if 103 <= gx <= 523:
                continue
            gy = 34 + ((i * 71 + self.road_off * 2) % 430)
            painter.fillRect(gx, gy, 4, 6, QColor("#3E8A44"))
        painter.fillRect(103, 34, 420, 436, QColor("#3A3F47"))
        painter.fillRect(99, 34, 4, 436, QColor("#F2F2F2"))
        painter.fillRect(523, 34, 4, 436, QColor("#F2F2F2"))
        for lane_line in (243, 383):
            y = 34 - 64 + self.road_off
            while y < 470:
                painter.fillRect(lane_line - 2, max(34, y), 4, 32 if y >= 34 else max(0, y + 32 - 34), QColor("#F6C453"))
                y += 64
        # traffic: cars drive the same way, slower, so the pet overtakes them
        for item in self.obstacles:
            draw_sprite(painter, "car", 173 + item["lane"] * 140 - 24, int(item["y"]), 4, colors={"B": item["color"]})
        car_x = 173 + self.lane * 140 - 24
        draw_sprite(painter, "roadster", car_x, 388, 4)
        self._pet(painter, car_x + 2, 436, 44, "HAPPY")

    def _paint_jump(self, painter: QPainter):
        # clouds and far hills for depth
        for i, cx in enumerate((60, 260, 470)):
            drift = (cx - self.frame // 2 * (1 + i % 2)) % 760 - 80
            draw_sprite(painter, "cloud", drift, 70 + i * 40, 4)
        painter.fillRect(0, 340, 640, 52, QColor("#1D252E"))
        ground_block(painter, 0, 392, 640, 24)
        run_bob = -2 if self.h_ground and (self.frame // 4) % 2 == 0 else 0
        self._pet(painter, int(self.hx) - 10, int(self.hy) + 32 + run_bob, 48, "HAPPY" if self.h_ground else "EXERCISE")
        for item in self.obstacles:
            draw_sprite(painter, item["kind"], int(item["x"]), 392 - item["h"], 3, flip=item["kind"] == "mouse")


def _overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by
