@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto fail
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment is missing. Run setup.cmd first.
  goto fail
)
echo Starting Manufacturing Method Advisor...
echo Errors will be saved to startup.log in this folder.
".venv\Scripts\python.exe" -u advisor.py >"startup.log" 2>&1
if errorlevel 1 goto fail
exit /b 0
:fail
echo.
echo Application could not start. Error details:
if exist "%~dp0startup.log" type "%~dp0startup.log"
echo.
echo Log: %~dp0startup.log
pause
exit /b 1
