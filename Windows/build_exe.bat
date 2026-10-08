@echo off
rem Builds the single-file installer EXE into this folder. Needs the project .venv (see ..\install.bat).
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" call install.bat
".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name TechnoLabKids_Setup --icon "%CD%\Windows\panther.ico" ^
  --paths "%CD%" --hidden-import setup_wizard ^
  --distpath "Windows" --workpath "Windows\_build" --specpath "Windows\_build" ^
  main.py
echo DONE
pause
