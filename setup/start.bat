@echo off
chcp 65001 > nul
title YTIMP4
cd /d "%~dp0"

echo Starting YTIMP4...
python bootstrap.py

timeout /t 2 /nobreak > nul
start http://localhost:8080
pause