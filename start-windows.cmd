@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-win\Scripts\python.exe" (
  echo Najpierw uruchom install-windows.cmd.
  pause
  exit /b 1
)
".venv-win\Scripts\python.exe" -m musiccast_bridge %*
if errorlevel 1 pause
