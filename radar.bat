@echo off
setlocal
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONPATH=%PROJECT_DIR%src;%PYTHONPATH%"
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m radar.cli %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
