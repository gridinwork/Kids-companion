import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import logic
from logic import (
    MSG_30,
    MSG_5,
    MSG_BREAK,
    MSG_BEDTIME_UP,
    MSG_BREAK_DONE,
    MSG_START,
    SKIN_NAMES,
    canonical_skin,
    CentralState,
    PolicyEngine,
    autostart_command,
    change_pin,
    configure_paths,
    countdown_message,
    default_config,
    empty_stats,
    hash_pin,
    load_config,
    load_persistence,
    pin_matches,
    public_config,
    read_pin_file,
    schedule_blocked,
    seconds_until_block,
    set_autostart,
    tooltip_for,
    write_pin_file,
    ensure_pin_file,
    voice_for,
)


def at(hour, minute=0, second=0, day=5):
    return datetime(2026, 10, day, hour, minute, second)


def make_engine(now=None, **overrides):
    now = now or at(15)
    config = default_config()
    config.update({"allowed_until": "21:30", "bedtime_start": "21:30"})
    config.update(overrides)
    state = CentralState(day=now.date().isoformat())
    state.child_locked = True
    return PolicyEngine(config, state, empty_stats())


class PolicyTests(unittest.TestCase):
    def test_default_pin_and_tooltip_text(self):
        cfg = default_config()
        self.assertTrue(pin_matches(cfg, "0000"))
        self.assertFalse(pin_matches(cfg, "2468"))
        self.assertFalse(pin_matches(cfg, ""))
        self.assertEqual(
            tooltip_for(MSG_BREAK),
            "TechnoLab Kids Companion — Я немного устал. Давай вместе отдохнём и разомнёмся?",
        )
        self.assertEqual(tooltip_for(MSG_START).split("— ", 1)[1], MSG_START)
        self.assertEqual(len(SKIN_NAMES), 10)
        self.assertEqual(canonical_skin("Pixel Cat"), "Кот")
        self.assertTrue(all("Pixel" not in name for name in SKIN_NAMES))
        self.assertEqual(countdown_message(30), "Мне пора спать, я засыпаю через 00:30. Давай сохраним игру.")
        self.assertIn("друг", MSG_START)
        self.assertNotIn("слежу за тобой", MSG_START)

    def test_plaintext_pin_is_replaced_by_default_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = configure_paths(Path(folder))
            paths["config"].write_text(json.dumps({"parent_pin": "2468", "daily_limit_minutes": 90}), encoding="utf-8")
            cfg = load_config(paths["config"], paths["log"])
            saved = json.loads(paths["config"].read_text(encoding="utf-8"))
            self.assertNotIn("parent_pin", saved)
            self.assertEqual(saved["parent_pin_hash"], hash_pin("0000"))
            self.assertEqual(cfg["daily_limit_minutes"], 90)
            self.assertTrue(pin_matches(cfg, "0000"))

    def test_existing_pin_hash_is_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = configure_paths(Path(folder))
            paths["config"].write_text(
                json.dumps({"parent_pin_hash": hash_pin("4321"), "version": "0.2"}),
                encoding="utf-8",
            )
            cfg = load_config(paths["config"], paths["log"])
            self.assertTrue(pin_matches(cfg, "4321"))
            self.assertFalse(pin_matches(cfg, "0000"))

    def test_change_pin_stores_hash_only(self):
        cfg = default_config()
        self.assertEqual(change_pin(cfg, "1111", "2222"), "PIN не совпадает.")
        self.assertEqual(change_pin(cfg, "12", "12"), "PIN должен состоять из 4–8 цифр.")
        self.assertEqual(change_pin(cfg, "4321", "4321"), "")
        self.assertTrue(pin_matches(cfg, "4321"))
        self.assertNotIn("4321", public_config(cfg).values())

    def test_idle_does_not_increase_active_time(self):
        now = at(15)
        engine = make_engine(now)
        engine.tick(now, 500)
        self.assertEqual(engine.state.ACTIVE_SECONDS_TODAY, 0)
        self.assertEqual(engine.state.CONTINUOUS_ACTIVE_SECONDS, 0)
        engine.tick(now, 0)
        engine.tick(now, 10)
        self.assertEqual(engine.state.ACTIVE_SECONDS_TODAY, 2)
        self.assertEqual(engine.state.CONTINUOUS_ACTIVE_SECONDS, 2)

    def test_short_idle_pauses_session_and_long_idle_resets_it(self):
        now = at(15)
        engine = make_engine(now, break_after_minutes=50, break_duration_minutes=10)
        engine.state.CONTINUOUS_ACTIVE_SECONDS = 100
        engine.state.ACTIVE_SECONDS_TODAY = 100
        engine.tick(now, 180)
        self.assertEqual(engine.state.CONTINUOUS_ACTIVE_SECONDS, 100)
        self.assertEqual(engine.state.ACTIVE_SECONDS_TODAY, 100)
        engine.tick(now, 0)
        self.assertEqual(engine.state.CONTINUOUS_ACTIVE_SECONDS, 101)
        engine.state.CONTINUOUS_ACTIVE_SECONDS = 100
        engine.tick(now, 600)
        self.assertEqual(engine.state.CONTINUOUS_ACTIVE_SECONDS, 0)
        self.assertEqual(engine.state.breaks, 0)
        short_break = make_engine(now, break_duration_minutes=1, idle_threshold_seconds=120)
        short_break.state.CONTINUOUS_ACTIVE_SECONDS = 40
        short_break.state.ACTIVE_SECONDS_TODAY = 40
        short_break.tick(now, 90)
        self.assertEqual(short_break.state.ACTIVE_SECONDS_TODAY, 41)
        self.assertEqual(short_break.state.CONTINUOUS_ACTIVE_SECONDS, 41)

    def test_break_reminder_and_completed_break(self):
        now = at(15)
        engine = make_engine(now, break_after_minutes=1, break_duration_minutes=10, reminder_repeat_minutes=5)
        engine.state.CONTINUOUS_ACTIVE_SECONDS = 59
        effects = engine.tick(now, 0)
        self.assertTrue(engine.state.break_due)
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, MSG_BREAK)
        self.assertEqual(engine.state.CURRENT_PET_STATE, "TIRED")
        self.assertTrue(any(effect.kind == "message" for effect in effects))
        engine.tick(now.replace(second=30), 0)
        self.assertEqual(engine.state.breaks, 0)
        done = engine.tick(at(15, 20), 600)
        self.assertEqual(engine.state.breaks, 1)
        self.assertEqual(engine.state.CONTINUOUS_ACTIVE_SECONDS, 0)
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, MSG_BREAK_DONE)
        self.assertTrue(any(effect.kind == "message" and effect.data["sound"] == "celebration" for effect in done))

    def test_longest_session(self):
        now = at(15)
        engine = make_engine(now)
        for second in range(5):
            engine.tick(now.replace(second=second), 0)
        self.assertEqual(engine.state.longest_session_seconds, 5)

    def test_staged_warnings_countdown_and_lock(self):
        now = at(15)
        engine = make_engine(now, daily_limit_minutes=180, final_warning_seconds=30)
        limit = 180 * 60
        engine.state.ACTIVE_SECONDS_TODAY = limit - 30 * 60
        engine.tick(now, 0)
        self.assertIn("30", engine.state.warned)
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, MSG_30)
        self.assertEqual(engine.state.CURRENT_PET_STATE, "WARNING")
        engine.state.ACTIVE_SECONDS_TODAY = limit - 5 * 60
        engine.tick(now, 0)
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, MSG_5)
        engine.state.ACTIVE_SECONDS_TODAY = limit - 30
        started = engine.tick(now, 0)
        self.assertTrue(any(effect.kind == "countdown_start" for effect in started))
        self.assertEqual(engine.state.countdown_left, 30)
        self.assertIn("00:30", engine.state.CURRENT_PET_MESSAGE)
        locked = None
        for second in range(1, 40):
            effects = engine.tick(now.replace(second=min(second, 59)), 0)
            if any(effect.kind == "lock" for effect in effects):
                locked = effects
                break
        self.assertIsNotNone(locked)
        self.assertTrue(engine.state.locked)
        self.assertEqual(engine.state.LOCK_STATE, "locked")

    def test_override_prevents_lock(self):
        now = at(15)
        engine = make_engine(now, daily_limit_minutes=1, final_warning_seconds=30)
        engine.state.ACTIVE_SECONDS_TODAY = 60
        engine.tick(now, 0)
        self.assertTrue(engine.state.countdown_started)
        engine.grant_override(now, 15)
        self.assertFalse(engine.state.countdown_started)
        for minute in range(10):
            effects = engine.tick(now.replace(minute=minute), 0)
            self.assertFalse(any(effect.kind == "lock" for effect in effects))
        self.assertFalse(engine.state.locked)

    def test_wrong_schedule_blocks_and_allowed_hour_does_not(self):
        engine = make_engine(at(21), daily_limit_minutes=180)
        self.assertEqual(seconds_until_block(at(21), engine.config), 30 * 60)
        engine.tick(at(21), 0)
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, MSG_30)
        night = make_engine(at(22))
        self.assertTrue(schedule_blocked(at(22), night.config))
        self.assertTrue(schedule_blocked(at(6, 30), night.config))
        self.assertFalse(schedule_blocked(at(7), night.config))
        effects = night.tick(at(22), 0)
        self.assertTrue(any(effect.kind == "countdown_start" for effect in effects))
        open_hours = make_engine(at(22), schedule_enforcement=False)
        self.assertFalse(schedule_blocked(at(22), open_hours.config))

    def test_unlocked_mode_only_notifies_and_never_locks(self):
        engine = make_engine(at(22))
        engine.state.child_locked = False
        kinds = []
        for second in range(0, 120):
            kinds += [effect.kind for effect in engine.tick(at(22, second // 60, second % 60), 0)]
        self.assertNotIn("lock", kinds)
        self.assertNotIn("countdown_start", kinds)
        self.assertFalse(engine.state.locked)
        self.assertIn("message", kinds)
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, MSG_BEDTIME_UP)

    def test_pet_speech_adapts_to_one_or_two_children(self):
        from logic import normalize_gender, praise, say, set_profile
        try:
            set_profile({})
            self.assertEqual(say(MSG_START), MSG_START)
            self.assertEqual(praise("boy"), "Ты молодец!")
            self.assertEqual(praise("girl"), "Ты умница!")
            set_profile({"child_gender": "girl", "child_name": "Маша"})
            self.assertTrue(say(MSG_START).startswith("Привет, Маша!"))
            self.assertEqual(praise("girl"), "Ты умница, Маша!")
            self.assertEqual(say("Мне скучно без тебя."), "Маша, мне скучно без тебя.")
            set_profile({"child_gender": "two", "child_name": "Игнор"})
            self.assertEqual(say(MSG_START), "Привет, ребята! Я ваш питомец и друг. Присмотрите за мной сегодня?")
            self.assertEqual(say(MSG_BEDTIME_UP), "Ребята, мне уже пора спать. Давайте закончим, спокойной ночи!")
            self.assertEqual(say("Хочешь, я тебя рассмешу?"), "Хотите, я вас рассмешу?")
            self.assertEqual(say("Поиграй со мной"), "Поиграйте со мной")
            self.assertEqual(praise("two"), "Вы молодцы!")
            self.assertNotIn("Игнор", say(MSG_START))
            self.assertEqual(normalize_gender("two"), "two")
            self.assertEqual(normalize_gender("x"), "")
        finally:
            set_profile({})

    def test_bonus_is_capped_per_day(self):
        engine = make_engine(at(15))
        engine.state.ACTIVE_SECONDS_TODAY = 3600
        for expected in (5, 5, 5, 0):
            engine.grant_bonus(5)
            self.assertEqual(engine.last_bonus, expected)
        self.assertEqual(engine.state.bonus_today_seconds, 15 * 60)
        self.assertEqual(engine.state.ACTIVE_SECONDS_TODAY, 3600 - 15 * 60)
        engine.config["bonus_daily_cap_minutes"] = 20
        engine.grant_bonus(10)
        self.assertEqual(engine.last_bonus, 5)

    def test_care_request_and_completion(self):
        engine = make_engine(at(15), care_after_minutes=1, care_minutes=1, reminder_repeat_minutes=5)
        engine.state.child_locked = False
        kinds = []
        for second in range(70):
            kinds += [e.kind for e in engine.tick(at(15, second // 60, second % 60), 0)]
        self.assertTrue(engine.state.care_due)
        self.assertIn("Поиграй со мной", engine.state.CURRENT_PET_MESSAGE)
        self.assertEqual(engine.add_care_seconds(30, at(15, 5)), [])
        engine.config["child_gender"] = "girl"
        effects = engine.add_care_seconds(30, at(15, 6))
        self.assertTrue(effects)
        self.assertFalse(engine.state.care_due)
        self.assertEqual(engine.state.care_done_today, 1)
        self.assertIn("поиграла", engine.state.CURRENT_PET_MESSAGE)

    def test_routine_repeats_until_acknowledged(self):
        engine = make_engine(at(18))
        engine.tick(at(18), 0)
        self.assertEqual(engine.state.pending_routine_title, "Зарядка")
        self.assertEqual(engine.state.CURRENT_PET_STATE, "EXERCISE")
        self.assertEqual(engine.state.CURRENT_PET_MESSAGE, "Давай немного разомнёмся вместе!")
        engine.tick(at(18, 0, 30), 0)
        self.assertEqual(engine.state.routine_last_notify["Зарядка"][:16], "2026-10-05T18:00")
        engine.tick(at(18, 5), 0)
        self.assertTrue(engine.state.routine_last_notify["Зарядка"].startswith("2026-10-05T18:05"))
        engine.acknowledge(at(18, 5, 1))
        self.assertIn("Зарядка", engine.state.routines_completed)
        self.assertEqual(engine.state.CURRENT_PET_STATE, "CELEBRATION")
        engine.tick(at(18, 10), 0)
        self.assertNotEqual(engine.state.pending_routine_title, "Зарядка")

    def test_missed_routine_is_not_fired_hours_later(self):
        engine = make_engine(at(21))
        engine.tick(at(21), 500)
        self.assertEqual(engine.state.pending_routine_title, "")
        self.assertEqual(engine.state.routine_last_notify.get("Зарядка"), "skipped")

    def test_shower_visual_and_bedtime_state(self):
        shower = make_engine(at(20))
        shower.tick(at(20), 0)
        self.assertEqual(shower.state.visual, "shower")
        self.assertEqual(shower.state.CURRENT_PET_STATE, "REMINDER")
        bedtime = make_engine(at(21, 30), schedule_enforcement=False)
        bedtime.tick(at(21, 30), 0)
        self.assertEqual(bedtime.state.pending_routine_title, "Сон")
        self.assertEqual(bedtime.state.CURRENT_PET_STATE, "SLEEP")

    def test_day_rollover_keeps_history_and_resets_counters(self):
        engine = make_engine(at(23, day=4))
        engine.state.day = "2026-10-04"
        engine.state.ACTIVE_SECONDS_TODAY = 80
        engine.state.longest_session_seconds = 40
        engine.state.breaks = 2
        engine.state.routines_completed = ["Зарядка"]
        engine.tick(at(0, 1, day=5), 0)
        self.assertEqual(engine.state.day, "2026-10-05")
        self.assertEqual(engine.state.ACTIVE_SECONDS_TODAY, 1)
        self.assertEqual(engine.stats["days"]["2026-10-04"]["active_seconds"], 80)
        self.assertEqual(engine.stats["days"]["2026-10-04"]["breaks"], 2)

    def test_corrupt_statistics_are_backed_up(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = configure_paths(Path(folder))
            paths["stats"].write_text("{", encoding="utf-8")
            paths["state"].write_text("{", encoding="utf-8")
            _config, state, stats = load_persistence(paths, "2026-10-05")
            self.assertEqual(stats["days"], {})
            self.assertEqual(state.ACTIVE_SECONDS_TODAY, 0)
            backups = list(paths["stats"].parent.glob("statistics.json.corrupt-*.bak"))
            self.assertTrue(backups)
            self.assertTrue(paths["log"].read_text(encoding="utf-8"))

    def test_pin_file_is_the_saved_password(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "PIN.txt"
            self.assertEqual(ensure_pin_file(path), "0000")
            write_pin_file(path, "кот-пароль")
            self.assertEqual(read_pin_file(path), "кот-пароль")
            engine = make_engine()
            engine.pin_file = path
            self.assertTrue(engine.pin_ok("кот-пароль"))
            self.assertFalse(engine.pin_ok("0000"))

    def test_every_pet_has_a_voice_and_gags_differ(self):
        from sound import GAGS, VOICES, ensure_sounds, gag_filename

        self.assertEqual({voice_for(name) for name in SKIN_NAMES}, set(VOICES))
        self.assertEqual(voice_for("Кот"), "man")
        self.assertEqual(voice_for("Зайчик"), "boy")
        self.assertEqual(voice_for("Собака"), "girl")
        self.assertEqual(voice_for("Единорог"), "woman")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            ensure_sounds(path)
            boy = (path / gag_filename("boy", "fart")).read_bytes()
            man = (path / gag_filename("man", "fart")).read_bytes()
            self.assertNotEqual(boy, man)
            self.assertGreater(len(boy), 44)
            names = {gag_filename(voice, gag) for voice in VOICES for gag in GAGS}
            self.assertTrue(names <= {item.name for item in path.glob("*.wav")})

    def test_trick_sound_depends_on_pet(self):
        from sound import render_trick

        cat = render_trick("Кот", "man", "purr")
        owl = render_trick("Единорог", "woman", "purr")
        bunny = render_trick("Зайчик", "boy", "squeak")
        self.assertNotEqual(cat, owl)
        self.assertNotEqual(cat, bunny)
        self.assertGreater(len(cat), 100)

    def test_autostart_failure_is_reported(self):
        def explode(_enabled, _command):
            raise OSError("denied")

        ok, message = set_autostart(True, "cmd", writer=explode)
        self.assertFalse(ok)
        self.assertIn("автозапуск", message.casefold())
        self.assertEqual(autostart_command("py.exe", "main.py"), '"py.exe" "main.py"')


if __name__ == "__main__":
    unittest.main()
