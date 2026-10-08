@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (py -3.11 -m venv .venv 2>nul || python -m venv .venv)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
echo READY
pause
