import os
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

os.environ["KIDS_NO_PROMPT"] = "1"

from games import GAME_NAMES, MiniGame
from lesson import GAME_LESSONS, SPOTS
from logic import MSG_BREAK, MSG_START, tooltip_for
from main import HERE_LINES, LAUGH_LINES, PLAY_LINES, STAY_LINE, STATE_LABELS, Agent
from petdraw import SKIN_DEFS


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _agent(self, folder):
        locks = []
        agent = Agent(
            self.app,
            Path(folder),
            locker=lambda: locks.append(True) or False,
            idle_provider=lambda: 0,
            now_provider=lambda: datetime(2026, 10, 5, 15, 0, 0),
        )
        agent.timer.stop()
        agent.anim.stop()
        agent._locks = locks
        return agent

    def test_startup_tray_hide_and_exit_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            self.assertEqual(agent.companion.bubble.text(), MSG_START)
            self.assertIn(MSG_START, agent._last_tip)
            self.assertTrue(agent.companion.isVisible())
            self.assertEqual(agent.companion._hide_timer.interval(), 30000)
            self.assertTrue(agent.companion._hide_timer.isActive())
            self.assertEqual(len(HERE_LINES), 5)
            self.assertEqual(len(PLAY_LINES), 5)
            self.assertEqual(len(LAUGH_LINES), 5)
            self.assertFalse(self.app.quitOnLastWindowClosed())
            agent.companion.close()
            self.assertFalse(agent.companion.isVisible())
            self.assertTrue(agent.engine.state.ACTIVE_SECONDS_TODAY == 0)
            if agent.tray is not None:
                labels = [action.text() for action in agent.tray.contextMenu().actions()]
                self.assertEqual(labels[0], "Открыть")
                self.assertEqual(labels[1], "Показать питомца")
                self.assertEqual(labels[2], "Мини-игры")
                self.assertEqual(labels[3], "Что я умею")
                self.assertEqual(labels[4], "Parent Mode")
                self.assertIn("Выход", labels)
                self.assertEqual(agent.tray.toolTip(), tooltip_for(MSG_START))
            else:
                self.assertTrue(agent.dashboard.isVisible())
                log = Path(folder, "logs", "agent.log").read_text(encoding="utf-8")
                self.assertIn("tray initialization error", log)
            flags = []
            agent.shutdown = lambda: flags.append("quit")
            self.assertFalse(agent.request_exit_with_pin("9999"))
            self.assertEqual(flags, [])
            self.assertTrue(agent.request_exit_with_pin("0000"))
            self.assertEqual(flags, ["quit"])

    def test_break_message_matches_bubble_and_tooltip(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            agent.engine.state.CONTINUOUS_ACTIVE_SECONDS = agent.engine.break_after_seconds - 1
            agent.on_tick()
            self.assertEqual(agent.companion.bubble.text(), MSG_BREAK)
            self.assertEqual(agent._last_tip, tooltip_for(MSG_BREAK))
            if agent.tray is not None:
                self.assertEqual(agent.tray.toolTip(), tooltip_for(MSG_BREAK))
            self.assertIn("Активное время сегодня", agent.dashboard.active_label.text())
            self.assertIn("Текущая непрерывная сессия", agent.dashboard.session_label.text())
            self.assertIn("До дневного лимита", agent.dashboard.remain_label.text())
            self.assertIn("Следующий распорядок", agent.dashboard.routine_label.text())
            self.assertIn("Перерыв", agent.dashboard.break_label.text())

    def test_countdown_uses_fake_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            agent.engine.state.child_locked = True
            agent.engine.state.ACTIVE_SECONDS_TODAY = agent.engine.daily_limit_seconds - 29
            agent.on_tick()
            self.assertTrue(agent.overlay.isVisible())
            self.assertIn("00:30", agent.overlay.label.text())
            self.assertEqual(agent._locks, [])
            agent.apply_override()
            self.assertFalse(agent.overlay.isVisible())
            self.assertEqual(agent._locks, [])

    def test_all_skins_and_states_draw(self):
        from main import PixelPet

        pet = PixelPet()
        pet.show()
        images = []
        for name, _kind, *_colors in SKIN_DEFS:
            pet.skin = name
            pet.state_name = "HAPPY"
            image = pet.grab().toImage()
            images.append(tuple(image.pixel(x, y) for x in range(8, 112, 12) for y in range(8, 112, 12)))
        self.assertEqual(len(images), 10)
        self.assertNotEqual(images[0], images[9])
        for state in STATE_LABELS:
            pet.state_name = state
            pet.grab()

    def test_pet_click_talks_and_lock_tab_hides_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            agent.dashboard.hide()
            agent.on_pet_clicked()
            self.assertFalse(agent.dashboard.isVisible())
            self.assertIn(agent.companion.bubble.text(), HERE_LINES)
            agent.companion.decline("here")
            self.assertIn(agent.companion.bubble.text(), LAUGH_LINES)
            agent.companion.decline("laugh")
            self.assertEqual(agent.companion.bubble.text(), STAY_LINE)
            self.assertTrue(agent.companion.isVisible())
            agent.companion.retreat()
            self.assertFalse(agent.companion.isVisible())
            agent.set_child_locked(True)
            self.assertEqual(agent.dashboard.tabs.tabText(2), "Разблокировать")
            self.assertFalse(agent.dashboard.tabs.isTabEnabled(0))
            self.assertFalse(agent.dashboard.tabs.isTabEnabled(1))
            self.assertFalse(agent.engine.pin_ok("9999"))
            agent.dashboard.lock_page.pin.setText("0000")
            agent.dashboard.lock_page._act()
            self.assertFalse(agent.engine.state.child_locked)
            self.assertEqual(agent.dashboard.tabs.tabText(2), "Заблокировать")
            self.assertTrue(agent.dashboard.tabs.isTabEnabled(0))

    def test_lesson_shows_skills_games_and_spots(self):
        self.assertEqual(set(GAME_LESSONS), set(GAME_NAMES))
        self.assertEqual({item[1] for item in SKIN_DEFS}, set(SPOTS))
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            agent.engine.state.SOUND_ENABLED = False
            agent.dashboard.hide()
            agent.companion.pet.on_right()
            self.assertTrue(agent.lesson.isVisible())
            self.assertFalse(agent.dashboard.isVisible())
            self.assertEqual(agent.lesson.title.text(), "Я умею вот что")
            agent.lesson._demo(0)
            self.assertIn("игра", agent.lesson.caption.text().casefold())
            self.assertEqual(agent.lesson.pet.state_name, "PLAY")
            agent.lesson._go(1)
            self.assertEqual(agent.lesson.game_count, 10)
            self.assertEqual(agent.lesson.title.text(), "Игры")
            agent.lesson._go(2)
            cat = [button.text() for button in agent.lesson.spot_buttons]
            self.assertIn("Пощекотать ухо", cat)
            agent.lesson.spot_buttons[0].click()
            self.assertIn("уш", agent.lesson.caption.text().casefold())
            agent.engine.state.SELECTED_SKIN = "Робот"
            agent.lesson.sync_pet()
            robot = [button.text() for button in agent.lesson.spot_buttons]
            self.assertNotEqual(cat, robot)
            self.assertIn("антен", robot[0].casefold())
            agent.lesson.close()
            self.assertFalse(agent.lesson.isVisible())

    def test_pet_placement_modes(self):
        from PySide6.QtWidgets import QApplication
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            area = QApplication.primaryScreen().availableGeometry()
            window = agent.companion
            agent.engine.config["pet_position"] = "bottom_left"
            window.apply_placement()
            self.assertLessEqual(window.frameGeometry().left(), area.left() + 20)
            self.assertFalse(window.pet.can_drag())
            agent.engine.config["pet_position"] = "bottom_right"
            window.apply_placement()
            self.assertGreaterEqual(window.frameGeometry().right(), area.right() - 20)
            agent.engine.config["pet_position"] = "free"
            agent.engine.config["pet_x"], agent.engine.config["pet_y"] = area.left() + 500, area.top() + 600
            window.apply_placement()
            self.assertTrue(window.pet.can_drag())
            self.assertEqual(window.frameGeometry().right() + 1, area.left() + 500)
            window.move(area.left() + 100, area.top() + 100)
            window._on_drag(False)
            self.assertEqual(agent.engine.config["pet_x"], window.frameGeometry().right() + 1)

    def test_care_window_counts_only_touch_time(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            agent.engine.state.SOUND_ENABLED = False
            agent.engine.config["care_minutes"] = 1
            agent.engine.state.care_due = True
            agent.open_care()
            agent.care._second()
            self.assertEqual(agent.engine.state.care_seconds, 0)
            agent.care._act("feed")
            for _ in range(60):
                agent.care._second()
            self.assertFalse(agent.engine.state.care_due)
            self.assertEqual(agent.engine.state.care_done_today, 1)
            agent.care.hide()

    def test_profile_applies_to_speech_and_games(self):
        import logic
        with tempfile.TemporaryDirectory() as folder:
            agent = self._agent(folder)
            try:
                agent.apply_profile("two", "лишнее имя")
                self.assertEqual(agent.engine.config["child_gender"], "two")
                self.assertEqual(agent.engine.config["child_name"], "")
                agent.companion.show_system(logic.MSG_START)
                self.assertTrue(agent.companion.bubble.text().startswith("Привет, ребята!"))
                game = MiniGame("Arkanoid", sound_enabled=lambda: False, gender=lambda: "two")
                game.timer.stop()
                game.level = 3
                game.reset_round()
                game.win("Все блоки разбиты! " + logic.praise("two"))
                self.assertIn("Вы молодцы", game.over_text)
                game.close()
                agent.apply_profile("boy", "Ваня")
                agent.companion.show_system(logic.MSG_START)
                self.assertTrue(agent.companion.bubble.text().startswith("Привет, Ваня!"))
                self.assertTrue(agent.ensure_profile())
            finally:
                logic.set_profile({})

    def test_games_step_without_crashing(self):
        for name in GAME_NAMES:
            game = MiniGame(name, sound_enabled=lambda: False)
            game.timer.stop()
            game.show()
            for _ in range(8):
                if game.over:
                    break
                game.step()
                game.frame += 1
            game.grab()
            game.close()
            self.assertIn(name, GAME_NAMES)
        self.assertEqual(len(GAME_NAMES), 10)


if __name__ == "__main__":
    unittest.main()
