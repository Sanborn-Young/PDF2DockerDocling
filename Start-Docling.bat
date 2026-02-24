@echo off
REM Launch Docling PDF processor with Docker via Python GUI

setlocal enabledelayedexpansion

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.x and add it to your system PATH
    pause
    exit /b 1
)

REM Check if rundocling-fixed.py exists
if not exist "rundocling-fixed.py" (
    echo Error: rundocling-fixed.py not found in current directory
    echo Current directory: %cd%
    pause
    exit /b 1
)

REM Check if pull-updated.ps1 exists
if not exist "pull-updated.ps1" (
    echo Error: pull-updated.ps1 not found in current directory
    pause
    exit /b 1
)

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed or not running
    echo Please ensure Docker Desktop is installed and running
    pause
    exit /b 1
)

echo.
echo ============================================
echo Docling PDF Processor Launcher (START)
echo ============================================
echo.

REM Run the Python script with unbuffered output for real-time streaming
python -u rundocling-fixed.py

set exitcode=%errorlevel%
if %exitcode% neq 0 (
    echo.
    echo Error: Script failed with exit code %exitcode%
    echo.
    pause
    exit /b %exitcode%
)

echo.
echo Docling run finished.
echo.
pause
endlocal
