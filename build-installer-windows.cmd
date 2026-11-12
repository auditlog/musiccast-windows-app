@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-win\Scripts\python.exe" (
  echo Najpierw uruchom install-windows.cmd.
  pause
  exit /b 1
)
".venv-win\Scripts\python.exe" scripts\build_installer.py %*
set "bridge_result=%errorlevel%"
if not "%bridge_result%"=="0" echo Budowanie instalatora nie powiodlo sie. Sprawdz komunikat powyzej.
pause
exit /b %bridge_result%
