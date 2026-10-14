@echo off
rem Double-click this file to open the interactive simulation in your browser.
rem
rem The first run builds a private Python environment in .venv: a few minutes,
rem and it needs an internet connection that once. After that it starts in a
rem few seconds. Close the window, or press Ctrl+C, to stop.

setlocal
cd /d "%~dp0"
title NYC Title I Funding Simulation

set "VENV_PY=.venv\Scripts\python.exe"

rem Already set up? Go straight to the simulation.
if exist "%VENV_PY%" "%VENV_PY%" -c "import titlei, streamlit" >nul 2>&1 && goto launch

echo Setting up the simulation. This takes a few minutes the first time
echo and needs an internet connection; later runs start in seconds.
echo.

rem An environment whose Python has since been removed cannot be repaired.
if exist "%VENV_PY%" "%VENV_PY%" -c "pass" >nul 2>&1 || rmdir /s /q .venv

if exist "%VENV_PY%" goto install

rem Prefer the py launcher: a bare "python" may be the Microsoft Store stub.
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

%PY% -m venv .venv || goto failed

:install
"%VENV_PY%" -m pip install --quiet --disable-pip-version-check --upgrade pip || goto failed
"%VENV_PY%" -m pip install --disable-pip-version-check -e ".[dashboard]" || goto failed
echo.

:launch
"%VENV_PY%" -m titlei dashboard %*
if errorlevel 1 goto failed
exit /b 0

:nopython
echo Python 3.9 or newer is needed. Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer. Then double-click this
echo file again.
pause
exit /b 1

:failed
echo.
echo Something went wrong; the details are above.
pause
exit /b 1
