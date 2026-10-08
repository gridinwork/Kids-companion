import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['KIDS_NO_PROMPT'] = '1'
import logic
from main import Agent
from PySide6.QtWidgets import QApplication
from setup_wizard import uninstall_script

class SchoolTests(unittest.TestCase):
    def engine(self):
        cfg = logic.default_config()
        state = logic.CentralState('2026-10-05')
        state.child_locked = True
        return logic.PolicyEngine(cfg, state, logic.empty_stats())

    def test_boundaries_weekends_and_disable(self):
        cfg = logic.default_config()
        for day, hour, minute, expected in [(5,8,44,False),(5,8,45,True),(5,12,59,True),(5,13,0,False),(10,9,0,False),(11,9,0,False)]:
            with self.subTest(day=day, hour=hour, minute=minute):
                self.assertEqual(logic.school_active(datetime(2026,10,day,hour,minute),cfg), expected)
        cfg['school_enabled'] = False
        self.assertFalse(logic.school_active(datetime(2026,10,5,9),cfg))

    def test_school_cancels_countdown_excludes_usage_and_resumes(self):
        engine = self.engine()
        state = engine.state
        state.ACTIVE_SECONDS_TODAY = 120
        state.CONTINUOUS_ACTIVE_SECONDS = 500
        state.countdown_started = True
        state.countdown_left = 1
        effects = engine.tick(datetime(2026,10,5,8,45),0)
        self.assertEqual([e.kind for e in effects], ['countdown_cancel'])
        for hour in (9,10,11,12):
            self.assertEqual(engine.tick(datetime(2026,10,5,hour),0), [])
        self.assertEqual(state.ACTIVE_SECONDS_TODAY, 120)
        self.assertEqual(state.CONTINUOUS_ACTIVE_SECONDS, 0)
        self.assertFalse(state.locked)
        engine.tick(datetime(2026,10,5,13),0)
        self.assertEqual(state.ACTIVE_SECONDS_TODAY,121)
        self.assertEqual(state.CONTINUOUS_ACTIVE_SECONDS,1)

    def test_school_overrides_exhausted_limit_and_sleep_schedule(self):
        engine = self.engine()
        engine.state.ACTIVE_SECONDS_TODAY = 999999
        engine.config['allowed_from'] = '15:00'
        self.assertEqual(engine.tick(datetime(2026,10,5,9),0), [])
        self.assertFalse(engine.state.countdown_started)

    def test_migration_and_invalid_school_settings(self):
        cfg, _ = logic.normalize_config({'school_from':'bad','school_until':'03:00'})
        self.assertEqual((cfg['school_from'],cfg['school_until']),('08:45','13:00'))
        cfg['school_from'] = '14:00'
        self.assertTrue(logic.validate_settings(cfg))

class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def agent(self, folder, hour=15):
        return Agent(self.app,Path(folder),locker=lambda: self.fail('Real lock attempted'),
                     idle_provider=lambda:0,now_provider=lambda:datetime(2026,10,5,hour))

    def test_school_startup_hidden_no_notifications_or_locks(self):
        with tempfile.TemporaryDirectory() as folder, patch('main.set_autostart') as registry:
            agent = self.agent(folder,9)
            self.assertFalse(agent.companion.isVisible())
            agent.on_tick()
            agent._finish_startup()
            agent._do_lock()
            self.assertFalse(agent.companion.isVisible())
            self.assertFalse(agent.overlay.isVisible())
            self.assertEqual(agent.engine.state.ACTIVE_SECONDS_TODAY,0)
            registry.assert_not_called()
            agent.shutdown()

    def test_exit_stops_timers_preserves_startup_and_rejects_bad_pin(self):
        with tempfile.TemporaryDirectory() as folder, patch('main.set_autostart') as registry:
            agent = self.agent(folder)
            agent.engine.config['autostart'] = True
            self.assertFalse(agent.request_exit_with_pin('wrong'))
            self.assertTrue(agent.timer.isActive())
            self.assertTrue(agent.request_exit_with_pin('0000'))
            self.assertFalse(agent.timer.isActive())
            self.assertFalse(agent.anim.isActive())
            before = agent.engine.state.ACTIVE_SECONDS_TODAY
            agent.on_tick()
            self.assertEqual(agent.engine.state.ACTIVE_SECONDS_TODAY,before)
            self.assertTrue(agent.engine.config['autostart'])
            registry.assert_not_called()

    def test_autostart_pin_cancel_failure_and_success(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self.agent(folder)
            panel = agent.dashboard.settings_page
            with patch.object(agent,'_ask_pin',return_value=('0000',True)), patch('main.set_autostart',return_value=(True,'')) as registry:
                panel.autostart.setChecked(True)
                self.assertTrue(agent.engine.config['autostart'])
                registry.assert_called_once()
            with patch.object(agent,'_ask_pin',return_value=('',False)), patch('main.set_autostart') as registry:
                panel.autostart.setChecked(False)
                self.assertTrue(panel.autostart.isChecked())
                registry.assert_not_called()
            with patch.object(agent,'_ask_pin',return_value=('0000',True)), patch('main.set_autostart',return_value=(False,'denied')), patch('main.QMessageBox.warning'):
                panel.autostart.setChecked(False)
                self.assertTrue(panel.autostart.isChecked())
            with patch.object(agent,'_ask_pin',return_value=('0000',True)), patch('main.set_autostart',return_value=(True,'')):
                panel.autostart.setChecked(False)
                self.assertFalse(agent.engine.config['autostart'])
            agent.shutdown()

    def test_uninstall_wrong_pin_never_starts_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = self.agent(folder)
            with patch.object(agent,'_ask_pin',return_value=('wrong',True)), patch('main.QMessageBox.warning'), patch('setup_wizard.schedule_uninstall') as remove:
                agent.prompt_uninstall()
                remove.assert_not_called()
                self.assertFalse(agent._stopping)
            agent.shutdown()

    def test_uninstall_requires_install_marker_and_quotes_path(self):
        with tempfile.TemporaryDirectory(prefix="kids' test ") as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):
                uninstall_script(root,123)
            (root/'installed.flag').write_text('installed')
            (root/'TechnoLabKids.exe').touch()
            script=uninstall_script(root,123)
            self.assertIn("kids'' test",script)
            self.assertIn('Wait-Process -Id 123',script)
            self.assertNotIn('Remove-Item -LiteralPath $root -Recurse',script)

    @unittest.skipUnless(os.name == 'nt', 'Windows uninstaller')
    def test_uninstall_helper_removes_only_owned_files(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix="kids uninstall '") as folder:
            root = Path(folder).resolve()
            (root/'installed.flag').write_text('installed')
            (root/'TechnoLabKids.exe').touch()
            (root/'PIN.txt').write_text('0000')
            (root/'keep.txt').write_text('unrelated file')
            (root/'data').mkdir()
            (root/'data'/'state.json').write_text('{}')
            # Only this freshly created, resolved temporary installation is targeted.
            helper = root/'remove.ps1'
            helper.write_text(uninstall_script(root, 2147483647), encoding='utf-8-sig')
            result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive',
                '-ExecutionPolicy','Bypass','-File',str(helper)],capture_output=True,
                timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((root/'keep.txt').exists())
            self.assertFalse((root/'TechnoLabKids.exe').exists())
            self.assertFalse((root/'PIN.txt').exists())
            self.assertFalse((root/'data').exists())
            self.assertFalse(helper.exists())
