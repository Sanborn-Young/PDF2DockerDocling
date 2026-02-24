@echo off
REM Stop any running Docling containers

echo.
echo ============================================
echo Docling Shutdown (STOP)
echo ============================================
echo.

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed or not running
    echo Please ensure Docker Desktop is installed and running
    pause
    exit /b 1
)

REM Find containers based on the image name
for /f "tokens=1" %%i in ('docker ps -q --filter "ancestor=aimilefth/docling:latest"') do (
    echo Stopping Docling container %%i ...
    docker stop %%i
)

REM Also stop any containers publishing ports in the 8080-8095 range as a fallback
for /f "tokens=1" %%p in ('docker ps --format "{{.ID}} {{.Ports}}"') do (
    for /f "tokens=2 delims=:>" %%q in ("%%p") do (
        for /l %%r in (8080,1,8095) do (
            if "%%q"=="%%r" (
                echo Stopping container %%p using port %%r ...
                docker stop %%p
            )
        )
    )
)

echo.
echo Done. Any running Docling containers should now be stopped.
echo.
pause
