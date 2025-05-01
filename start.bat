@echo off
setlocal enabledelayedexpansion

echo Starting Screenshot Service...

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python environment not detected. Please install Python 3.6+
    pause
    exit /b 1
)

:: Check and install dependencies
echo Checking and installing dependencies...
python -m pip install --upgrade pip
pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
pip install -r requirements.txt

:: Start the application
echo Starting the screenshot service...
python -m app.main

:: Keep window open if application closes unexpectedly
pause 
