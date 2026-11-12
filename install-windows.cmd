@echo off
setlocal
cd /d "%~dp0"
set "MUSICCAST_PYTHON_CHECK=import struct, sys; sys.exit(0 if sys.implementation.name == 'cpython' and sys.version_info[:2] in ((3, 12), (3, 13)) and struct.calcsize('P') == 8 else 1)"
if exist ".venv-win\Scripts\python.exe" goto check_environment

set "MUSICCAST_PYTHON=py -3.13"
%MUSICCAST_PYTHON% -c "%MUSICCAST_PYTHON_CHECK%" >nul 2>nul
if not errorlevel 1 goto create_environment
set "MUSICCAST_PYTHON=py -3.12"
%MUSICCAST_PYTHON% -c "%MUSICCAST_PYTHON_CHECK%" >nul 2>nul
if not errorlevel 1 goto create_environment
set "MUSICCAST_PYTHON=python"
%MUSICCAST_PYTHON% -c "%MUSICCAST_PYTHON_CHECK%" >nul 2>nul
if not errorlevel 1 goto create_environment

echo Nie znaleziono Pythona 3.13 lub 3.12 w wersji 64-bit.
echo Sprawdz polecenia: py -0p oraz python --version.
echo Przy instalacji z python.org wlacz Python Launcher lub dodaj Python do PATH.
pause
exit /b 1

:create_environment
echo Tworzenie srodowiska za pomoca: %MUSICCAST_PYTHON%
%MUSICCAST_PYTHON% -m venv .venv-win
if errorlevel 1 goto failed

:check_environment
".venv-win\Scripts\python.exe" -c "%MUSICCAST_PYTHON_CHECK%" >nul 2>nul
if errorlevel 1 (
  echo Istniejacy folder .venv-win nie zawiera dzialajacego Pythona 3.12 lub 3.13 64-bit.
  echo Zmien nazwe tego folderu i ponownie uruchom instalator.
  pause
  exit /b 1
)
".venv-win\Scripts\python.exe" --version
".venv-win\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv-win\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
echo.
echo Gotowe. Uruchom start-windows.cmd.
pause
exit /b 0
:failed
echo Instalacja nie powiodla sie. Sprawdz komunikat powyzej i polaczenie z internetem.
pause
exit /b 1
