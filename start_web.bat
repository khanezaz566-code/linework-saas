@echo off
title VectorCraft Web Studio Server
cd /d "%~dp0"
echo ============================================================
echo   Starting VectorCraft AI Vector Studio (Web Edition)...
echo   Opening in your web browser: http://localhost:8000
echo ============================================================
python run_web.py
pause
