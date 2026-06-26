@echo off
setlocal
title Boss Auto Apply
cd /d "%~dp0"
set "PYTHON_EXE=python"
where python >nul 2>nul
if errorlevel 1 (
    set "PYTHON_EXE=C:\Users\86136\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)
if not exist "%PYTHON_EXE%" if not "%PYTHON_EXE%"=="python" (
    echo Python was not found.
    echo Please install Python 3 or update PYTHON_EXE in this file.
    exit /b 9009
)
echo ============================================================
echo Boss Auto Apply
echo Time: %date% %time%
echo CWD:  %cd%
echo Command: "%PYTHON_EXE%" boss_auto_apply.py
echo ============================================================
"%PYTHON_EXE%" boss_auto_apply.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo ============================================================
echo boss_auto_apply.py exited with code %EXIT_CODE%
echo Time: %date% %time%
echo ============================================================
exit /b %EXIT_CODE%
