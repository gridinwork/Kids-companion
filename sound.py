"""Original tones and pet voices. Playback never changes the Windows volume mixer.

Tickle voices follow the toy-pet idea: a giggle, then surprise sounds
such as a toot, a burp, a sneeze, a hiccup, a raspberry and a yawn.
Nothing here is taken from another game.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

try:
    import winsound
except ImportError:  # pragma: no cover - Windows-only playback
    winsound = None

RATE = 22050

TONES = {
    "routine.wav": (880, 0.14),
    "warning.wav": (520, 0.20),
    "celebration.wav": (1175, 0.16),
    "game.wav": (740, 0.05),
    "game_low.wav": (196, 0.09),
}

# Pitch scale: boys and girls sit higher, men and women lower.
VOICES = {
    "boy": 1.45,
    "girl": 1.85,
    "man": 0.72,
    "woman": 1.12,
}
GAGS = ("giggle", "fart", "burp", "sneeze", "hiccup", "raspberry", "yawn")

TICKLES = [
    ("giggle", "Хи-хи!", "laugh"),
    ("giggle", "Ещё, щекотно!", "wink"),
    ("fart", "Пум! Ой!", "silly"),
    ("giggle", "Хи-хи-хи!", "laugh"),
    ("burp", "Буээп!", "surprised"),
    ("sneeze", "Апчхи!", "blink"),
    ("giggle", "Ой, щекотно!", "smile"),
    ("hiccup", "Ик!", "surprised"),
    ("raspberry", "Пффф!", "tongue"),
    ("yawn", "Уааа… и снова щекотно!", "sleep"),
]


def _noise(index: int) -> float:
    value = (index * 1103515245 + 12345) & 0x7FFFFFFF
    return (value / 0x3FFFFFFF) - 1.0


def _write_samples(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        frames = bytearray()
        for sample in samples:
            clipped = max(-32767, min(32767, int(sample)))
            frames += struct.pack("<h", clipped)
        handle.writeframes(frames)


def _write_tone(path: Path, frequency: float, duration: float) -> None:
    count = int(RATE * duration)
    samples = []
    for index in range(count):
        env = 1.0
        fade = int(RATE * 0.01)
        if index < fade:
            env = index / fade
        elif index > count - fade:
            env = max(0.0, (count - index) / fade)
        samples.append(math.sin(2 * math.pi * frequency * index / RATE) * 9000 * env)
    _write_samples(path, samples)


def _push(samples: list[float], freq: float, duration: float, amp: float, slide: float = 1.0, noisy: float = 0.0) -> None:
    count = max(1, int(RATE * duration))
    for index in range(count):
        t = index / RATE
        env = math.sin(math.pi * index / count)
        current = freq * (1 + (slide - 1) * (index / count))
        tone = math.sin(2 * math.pi * current * t)
        if noisy:
            tone = tone * (1 - noisy) + _noise(index + len(samples)) * noisy
        samples.append(tone * amp * env)


def _render_gag(voice: str, gag: str) -> list[float]:
    return _render_gag_at(VOICES.get(voice, 1.0), gag)


def _render_gag_at(pitch: float, gag: str) -> list[float]:
    samples: list[float] = []
    if gag == "giggle":
        for burst in range(4):
            _push(samples, 360 * pitch * (1 + burst * 0.04), 0.07, 11000)
            samples.extend([0.0] * int(RATE * 0.035))
    elif gag == "fart":
        _push(samples, 78 * pitch, 0.42, 15000, slide=0.35, noisy=0.72)
    elif gag == "burp":
        _push(samples, 210 * pitch, 0.26, 13000, slide=0.42, noisy=0.35)
    elif gag == "sneeze":
        _push(samples, 640 * pitch, 0.05, 12000, noisy=0.8)
        samples.extend([0.0] * int(RATE * 0.04))
        _push(samples, 420 * pitch, 0.16, 14000, slide=0.7, noisy=0.45)
    elif gag == "hiccup":
        _push(samples, 520 * pitch, 0.045, 14000, slide=1.4)
        samples.extend([0.0] * int(RATE * 0.08))
        _push(samples, 390 * pitch, 0.04, 9000)
    elif gag == "raspberry":
        _push(samples, 140 * pitch, 0.28, 12000, slide=0.8, noisy=0.85)
    else:
        _push(samples, 240 * pitch, 0.62, 8000, slide=0.55, noisy=0.08)
    return samples


def gag_filename(voice: str, gag: str) -> str:
    safe_voice = voice if voice in VOICES else "boy"
    safe_gag = gag if gag in GAGS else "giggle"
    return f"{safe_voice}_{safe_gag}.wav"


def ensure_sounds(folder: Path) -> None:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for name, (frequency, duration) in TONES.items():
            path = folder / name
            if not path.exists() or path.stat().st_size < 44:
                _write_tone(path, frequency, duration)
        for voice in VOICES:
            for gag in GAGS:
                path = folder / gag_filename(voice, gag)
                if not path.exists() or path.stat().st_size < 44:
                    _write_samples(path, _render_gag(voice, gag))
    except OSError:
        return


def play(folder: Path, name: str, enabled: bool) -> None:
    if not enabled or winsound is None:
        return
    path = folder / name
    if not path.exists():
        return
    try:
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        return


def play_gag(folder: Path, voice: str, gag: str, enabled: bool) -> None:
    ensure_sounds(folder)
    play(folder, gag_filename(voice, gag), enabled)


def pet_pitch(skin: str, voice: str) -> float:
    base = VOICES.get(voice, 1.0)
    wobble = 0.84 + (sum(ord(char) for char in (skin or "Кот")) % 19) / 40.0
    return base * wobble


def trick_filename(skin: str, trick: str) -> str:
    slug = "".join(char if char.isalnum() else "_" for char in (skin or "Кот"))
    return f"trick_{slug}_{trick}.wav"


def _render_trick_at(pitch: float, trick: str) -> list[float]:
    if trick in GAGS:
        return _render_gag_at(pitch, trick)
    samples: list[float] = []
    if trick == "purr":
        count = int(RATE * 0.55)
        for index in range(count):
            t = index / RATE
            env = 0.35 + 0.65 * abs(math.sin(2 * math.pi * 26 * t))
            samples.append(math.sin(2 * math.pi * 92 * pitch * t) * 9000 * env)
        return samples
    if trick == "meow":
        _push(samples, 520 * pitch, 0.16, 12000, slide=1.35)
        _push(samples, 340 * pitch, 0.18, 10000, slide=0.55)
        return samples
    if trick == "hiss":
        _push(samples, 1400 * pitch, 0.32, 9000, slide=0.8, noisy=0.92)
        return samples
    if trick == "sparkle":
        for freq in (880, 1175, 1568, 2093):
            _push(samples, freq * pitch * 0.5, 0.06, 9000)
        return samples
    if trick == "bubble":
        for _ in range(4):
            _push(samples, 360 * pitch, 0.05, 10000, slide=1.6, noisy=0.25)
            samples.extend([0.0] * int(RATE * 0.04))
        return samples
    if trick == "bark":
        _push(samples, 180 * pitch, 0.09, 14000, slide=0.7, noisy=0.25)
        samples.extend([0.0] * int(RATE * 0.05))
        _push(samples, 150 * pitch, 0.12, 14000, slide=0.6, noisy=0.3)
        return samples
    simple = {
        "squeak": (740, 0.11, 12000, 1.45, 0.0),
        "thump": (88, 0.14, 14000, 0.45, 0.35),
        "pop": (500, 0.06, 11000, 1.8, 0.25),
        "growl": (108, 0.4, 13000, 0.7, 0.55),
        "rumble": (68, 0.46, 12000, 0.85, 0.4),
        "neigh": (360, 0.34, 11000, 1.55, 0.12),
        "clang": (640, 0.18, 12000, 0.55, 0.05),
        "whoosh": (280, 0.28, 10000, 0.4, 0.78),
        "beep": (860, 0.09, 10000, 1.0, 0.0),
        "hoot": (300, 0.24, 9000, 0.85, 0.04),
        "flap": (170, 0.16, 11000, 1.25, 0.5),
        "chomp": (190, 0.08, 13000, 0.4, 0.62),
        "splash": (230, 0.3, 12000, 0.48, 0.82),
        "roar": (92, 0.46, 15000, 0.55, 0.48),
        "laser": (480, 0.2, 11000, 2.3, 0.12),
        "buzz": (210, 0.26, 10000, 1.0, 0.72),
        "honk": (240, 0.16, 13000, 0.75, 0.22),
        "wag": (420, 0.1, 9000, 1.25, 0.0),
        "chop": (280, 0.09, 13000, 0.65, 0.4),
        "trill": (560, 0.2, 10000, 1.18, 0.08),
    }
    freq, duration, amp, slide, noisy = simple.get(trick, (360, 0.16, 10000, 1.0, 0.0))
    _push(samples, freq * pitch, duration, amp, slide=slide, noisy=noisy)
    if trick == "beep":
        samples.extend([0.0] * int(RATE * 0.05))
        _push(samples, freq * pitch * 1.25, duration, amp)
    return samples


def render_trick(skin: str, voice: str, trick: str) -> list[float]:
    return _render_trick_at(pet_pitch(skin, voice), trick)


def play_trick(folder: Path, skin: str, voice: str, trick: str, enabled: bool) -> None:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / trick_filename(skin, trick)
        if not path.exists() or path.stat().st_size < 44:
            _write_samples(path, render_trick(skin, voice, trick))
    except OSError:
        return
    play(folder, trick_filename(skin, trick), enabled)
