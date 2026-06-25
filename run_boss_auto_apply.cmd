@echo off
setlocal
title Boss Auto Apply
cd /d "%~dp0"
echo ============================================================
echo Boss Auto Apply
echo Time: %date% %time%
echo CWD:  %cd%
echo Command: python boss_auto_apply.py
echo ============================================================
python boss_auto_apply.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo ============================================================
echo boss_auto_apply.py exited with code %EXIT_CODE%
echo Time: %date% %time%
echo ============================================================
exit /b %EXIT_CODE%
