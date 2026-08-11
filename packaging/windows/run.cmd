@echo off
set "BAY300DA=%LOCALAPPDATA%\Bay300\DevicesAdmin\venv\Scripts\bay300da.exe"
if not exist "%BAY300DA%" (
  echo Run install.cmd first.
  pause
  exit /b 1
)
"%BAY300DA%"
