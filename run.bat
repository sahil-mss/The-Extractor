@echo off
title The Extractor - Video, Audio, Tags & Transcripts
echo ======================================================================
echo   Starting The Extractor Server (Golden Ratio UI)
echo   Dashboard URL: http://localhost:8000
echo ======================================================================
echo.
timeout /t 2 /nobreak >nul
start http://localhost:8000
.venv\Scripts\python.exe server.py
pause
