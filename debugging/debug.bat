@echo off
title YTIMP4 Debug
cd /d "%~dp0"
echo Starting YTIMP4 in debug mode...
echo.
python ytimp4.py
echo.
echo [+] YTIMP4 has stopped. Press any key to exit.
pause