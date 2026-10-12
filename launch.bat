@echo off
setlocal
title The Extractor - Media Studio
cd /d "%~dp0"

echo =======================================================================
echo              THE EXTRACTOR - SMART LAUNCHER (WINDOWS)
echo =======================================================================
echo.

:: Check if Python is installed on system
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found on your computer!
    echo Please download and install Python from https://www.python.org/downloads/
    echo Remember to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Run launcher.py which automatically configures .venv, requirements, and launches app
python launcher.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [NOTICE] Launcher exited with error code %ERRORLEVEL%.
    pause
)
