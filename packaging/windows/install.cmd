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
"%INSTALL_ROOT%\venv\Scripts\python.exe" -c "import tkinter" >nul 2>nul || (
  echo.
  echo Tkinter is not installed, so the GUI cannot start yet.
  echo Open the official Python installer, choose Modify, and enable "tcl/tk and IDLE".
  echo Then reinstall bay300da and run bay300da gui again.
  echo https://www.python.org/downloads/windows/
  echo Administrator access is normally not required for a per-user Python installation.
  echo Ask Bay300 Help: How do I install Tkinter for bay300da on Windows?
  echo CLI commands are already available without Tkinter.
)
