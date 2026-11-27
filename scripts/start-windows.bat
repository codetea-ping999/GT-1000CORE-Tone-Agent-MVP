@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [Tone Agent] Creating Python virtual environment...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto failed
)
echo [Tone Agent] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Open http://127.0.0.1:8765 in your browser.
echo Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" -m gtcore_agent.server
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo [Tone Agent] Setup or launch failed. Verify Python 3.11+ and the BOSS driver.
pause
exit /b 1
