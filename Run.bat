@echo off
setlocal
cd /d "%~dp0"

if exist "dist\BrowserTaskAutomation.exe" (
  start "" "dist\BrowserTaskAutomation.exe"
  exit /b 0
)

if exist "run.py" (
  python run.py
  if errorlevel 1 pause
  exit /b
)

echo Could not find BrowserTaskAutomation.exe or run.py
pause
