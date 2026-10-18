@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto fail
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" download_model.py
if errorlevel 1 goto fail
echo Setup complete. Double-click start.cmd to launch the application.
pause
exit /b 0
:fail
echo Setup failed. Check the error above.
pause
exit /b 1
