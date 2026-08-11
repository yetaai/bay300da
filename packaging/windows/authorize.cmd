@echo off
set "BAY300DA=%LOCALAPPDATA%\Bay300\DevicesAdmin\venv\Scripts\bay300da.exe"
if not exist "%BAY300DA%" (
  echo Run install.cmd first.
  exit /b 1
)
"%BAY300DA%" authorize --url https://bay300.com
pause
