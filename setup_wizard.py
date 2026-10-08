"""First-run installer built into the single EXE.

Run the EXE from anywhere: it asks for the install folder and the parent PIN,
copies itself there, writes the settings and starts the installed program.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

import logic

APP_TITLE = "TechnoLab Kids Companion"
INSTALLED_EXE = "TechnoLabKids.exe"
INSTALLED_FLAG = "installed.flag"

STYLE = """
QWidget { background:#1C2128; color:#F4F7FB; font-family:"Segoe UI"; font-size:13px; }
QPushButton { background:#3A4250; color:white; border:none; border-radius:8px; padding:8px 14px; }
QPushButton:hover { background:#4C5666; }
QPushButton#primary { background:#F6C453; color:#1C2128; font-weight:bold; }
QLineEdit { background:#12161C; color:white; border:1px solid #3A4250; border-radius:6px; padding:6px; }
"""


def default_install_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return str(Path(base) / "Programs" / APP_TITLE)


def _powershell(script: str) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def create_desktop_shortcut(exe: Path) -> None:
    exe = Path(str(exe).replace("'", "''"))
    script = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '" + APP_TITLE + ".lnk'));"
        f"$s.TargetPath='{exe}';$s.WorkingDirectory='{exe.parent}';$s.Save()"
    )
    _powershell(script)


def install(target: Path, pin: str, desktop: bool, autostart: bool) -> Path:
    """Copy the program, write PIN and settings. Returns the installed EXE path."""
    target = target.resolve()
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise ValueError("Выберите отдельную папку для программы.")
    if target.exists() and any(target.iterdir()):
        if not (target / INSTALLED_FLAG).is_file() or not (target / INSTALLED_EXE).is_file():
            raise ValueError("Выберите пустую папку или папку установленной программы.")
        old_pin = logic.read_pin_file(target / "PIN.txt")
        if pin != old_pin:
            raise ValueError("Для обновления введите действующий родительский PIN.")
    target.mkdir(parents=True, exist_ok=True)
    dest = target / INSTALLED_EXE
    source = Path(sys.executable).resolve()
    if source != dest.resolve():
        shutil.copy2(source, dest)
    cfg = logic.load_config(target / "config.json", None) if (target / "config.json").exists() else logic.default_config()
    cfg["parent_pin_hash"] = logic.hash_pin(pin)
    cfg["autostart"] = bool(autostart)
    logic.save_config(target / "config.json", cfg)
    logic.write_pin_file(target / "PIN.txt", pin)
    (target / INSTALLED_FLAG).write_text("installed\n", encoding="utf-8")
    ok, error = logic.set_autostart(autostart, command=f'"{dest}"')
    if not ok:
        raise OSError(error)
    register_uninstaller(dest)
    if desktop:
        create_desktop_shortcut(dest)
    return dest


UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TechnoLabKidsCompanion"


def register_uninstaller(exe: Path) -> None:
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE) as key:
        for name, value in {
            "DisplayName": APP_TITLE,
            "DisplayVersion": "0.3.0",
            "Publisher": "GEC Engineering / TechnoLab",
            "InstallLocation": str(exe.parent),
            "DisplayIcon": str(exe),
            "UninstallString": f'"{exe}" --uninstall',
        }.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1)


def uninstall_script(root: Path, pid: int) -> str:
    root = root.resolve()
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise ValueError("Небезопасная папка удаления.")
    if not (root / INSTALLED_FLAG).is_file() or not (root / INSTALLED_EXE).is_file():
        raise ValueError("Удаление доступно в установленной EXE-версии. Исходники не удаляются.")
    quoted = str(root).replace("'", "''")
    # Only files created by this application; never recursively remove the install root.
    return f"""$ErrorActionPreference = 'Stop'
$root = '{quoted}'
Wait-Process -Id {int(pid)} -ErrorAction SilentlyContinue
try {{
    if (-not (Test-Path -LiteralPath (Join-Path $root 'installed.flag'))) {{ throw 'Missing installation marker' }}
    foreach ($name in @('data','logs','sounds','skins')) {{
        $item = Join-Path $root $name
        if (Test-Path -LiteralPath $item) {{
            $resolved = [IO.Path]::GetFullPath($item)
            if ([IO.Path]::GetDirectoryName($resolved) -ne $root) {{ throw 'Unsafe path' }}
            if ((Get-Item -LiteralPath $item).Attributes -band [IO.FileAttributes]::ReparsePoint) {{ throw 'Linked directory' }}
            Remove-Item -LiteralPath $item -Recurse -Force
        }}
    }}
    foreach ($name in @('TechnoLabKids.exe','config.json','PIN.txt','installed.flag')) {{
        $item = Join-Path $root $name
        for ($attempt=0; $attempt -lt 30; $attempt++) {{
            try {{
                if (Test-Path -LiteralPath $item) {{ Remove-Item -LiteralPath $item -Force }}
                break
            }} catch {{ if ($attempt -eq 29) {{ throw }}; Start-Sleep -Milliseconds 500 }}
        }}
    }}
    foreach ($name in @('games','Doc')) {{
        $item = Join-Path $root $name
        if ((Test-Path -LiteralPath $item) -and -not (Get-ChildItem -LiteralPath $item -Force)) {{
            Remove-Item -LiteralPath $item
        }}
    }}
    $shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) '{APP_TITLE}.lnk'
    if (Test-Path -LiteralPath $shortcut) {{
        $link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
        if ($link.TargetPath -eq (Join-Path $root 'TechnoLabKids.exe')) {{ Remove-Item -LiteralPath $shortcut -Force }}
    }}
    $reg = 'HKCU:\{UNINSTALL_KEY}'
    if ((Get-ItemProperty -LiteralPath $reg -ErrorAction SilentlyContinue).InstallLocation -eq $root) {{
        Remove-Item -LiteralPath $reg -Force
    }}
    if (-not (Get-ChildItem -LiteralPath $root -Force)) {{ Remove-Item -LiteralPath $root }}
}} catch {{
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(('Не удалось удалить все файлы: ' + $_.Exception.Message), 'Kids Companion')
}} finally {{ Remove-Item -LiteralPath $PSCommandPath -Force }}
"""


def schedule_uninstall(root: Path) -> None:
    if not getattr(sys, "frozen", False) or Path(sys.executable).resolve() != (root / INSTALLED_EXE).resolve():
        raise ValueError("Удаление доступно только из установленной программы.")
    script = uninstall_script(root, os.getpid())
    ok, error = logic.set_autostart(False)
    if not ok:
        raise OSError(error)
    handle, filename = tempfile.mkstemp(prefix="kids-uninstall-", suffix=".ps1")
    try:
        with os.fdopen(handle, "w", encoding="utf-8-sig") as stream:
            stream.write(script)
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", filename],
                         cwd=tempfile.gettempdir(), creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        Path(filename).unlink(missing_ok=True)
        raise


class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} — установка")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>{APP_TITLE}</h2>Питомец-напоминалка с играми и родительским контролем.")
        title.setWordWrap(True)
        layout.addWidget(title)

        layout.addWidget(QLabel("Папка установки:"))
        row = QHBoxLayout()
        self.path = QLineEdit(default_install_dir())
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        layout.addWidget(QLabel("Родительский PIN (по умолчанию 0000):"))
        self.pin = QLineEdit(logic.DEFAULT_PIN)
        self.pin.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pin)
        layout.addWidget(QLabel("Повторите PIN:"))
        self.confirm = QLineEdit(logic.DEFAULT_PIN)
        self.confirm.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.confirm)

        self.desktop = QCheckBox("Ярлык на рабочем столе")
        self.desktop.setChecked(True)
        self.autostart = QCheckBox("Запускать вместе с Windows")
        self.autostart.setChecked(True)
        self.launch = QCheckBox("Запустить сразу после установки")
        self.launch.setChecked(True)
        for box in (self.desktop, self.autostart, self.launch):
            layout.addWidget(box)
        note = QLabel(
            "После установки программа только напоминает. Экран блокируется лишь тогда, "
            "когда вы нажмёте «Заблокировать» в программе (время блокировки по умолчанию — 23:00)."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        go = QPushButton("Установить")
        go.setObjectName("primary")
        go.clicked.connect(self._install)
        buttons.addWidget(cancel)
        buttons.addWidget(go)
        layout.addLayout(buttons)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Папка установки", self.path.text())
        if chosen:
            self.path.setText(str(Path(chosen)))

    def _install(self):
        error = logic.validate_new_pin(self.pin.text(), self.confirm.text())
        if error:
            QMessageBox.warning(self, "PIN", error)
            return
        text = self.path.text().strip()
        if not text:
            QMessageBox.warning(self, "Установка", "Укажите папку установки.")
            return
        target = Path(text)
        try:
            exe = install(target, self.pin.text().strip(), self.desktop.isChecked(), self.autostart.isChecked())
        except Exception as exc:  # permissions, busy file: tell the parent, keep the dialog open
            QMessageBox.warning(self, "Установка", f"Не удалось установить:\n{exc}")
            return
        if self.launch.isChecked():
            subprocess.Popen(
                [str(exe)],
                cwd=str(target),
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        QMessageBox.information(self, "Готово", f"Установлено в:\n{target}")
        self.accept()


def run_setup(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    dialog = SetupDialog()
    dialog.exec()
    return 0
