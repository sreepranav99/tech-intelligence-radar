@echo off
title Tech Intelligence Radar
setlocal enabledelayedexpansion
set "PROJECT_DIR=%~dp0"
set "PYTHONPATH=%PROJECT_DIR%src;%PYTHONPATH%"

echo ==============================================================
echo 📡  Autonomous Market & Tech Intelligence Radar
echo ==============================================================
echo 🚀  Starting Radar Server...
echo 🌐  Opening browser at http://127.0.0.1:8844
echo.
echo Tip: Press Ctrl+C at any time in this window to stop.
echo ==============================================================
echo.

"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m radar.cli ui %*

endlocal
