@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-win\Scripts\python.exe" (
  echo Najpierw uruchom install-windows.cmd.
  pause
  exit /b 1
)
".venv-win\Scripts\python.exe" -m pip install -e ".[build]"
if errorlevel 1 goto failed
".venv-win\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".venv-win\Scripts\python.exe" -m PyInstaller --noconfirm --clean MusicCastBridge.spec
if errorlevel 1 goto failed
".venv-win\Scripts\python.exe" -c "from scripts.installer_tools import collect_licenses; collect_licenses('dist/MusicCastBridge')"
if errorlevel 1 goto failed
echo Gotowe: dist\MusicCastBridge\MusicCastBridge.exe
echo Przenos caly folder MusicCastBridge, nie sam plik EXE.
pause
exit /b 0
:failed
echo Budowanie nie powiodlo sie. Sprawdz komunikat powyzej.
pause
exit /b 1
