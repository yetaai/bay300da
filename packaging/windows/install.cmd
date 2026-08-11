@echo off
setlocal
set "INSTALL_ROOT=%LOCALAPPDATA%\Bay300\DevicesAdmin"
where py >nul 2>nul || (
  echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/windows/
  exit /b 1
)
py -3 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>nul || (
  echo Python 3.11 or newer is required.
  exit /b 1
)
if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%"
py -3 -m venv "%INSTALL_ROOT%\venv" || exit /b 1
"%INSTALL_ROOT%\venv\Scripts\python.exe" -m pip install --upgrade "%~dp0agent" || exit /b 1
echo Bay300 Devices Admin installed.
echo Next run authorize.cmd, then run.cmd.
