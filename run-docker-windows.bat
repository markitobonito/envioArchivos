@echo off
REM ============================================================
REM  run-docker-windows.bat - Windows Setup Script (SIMPLIFIED)
REM  Works on Windows 10/11 Home, Pro, Enterprise (with WSL2)
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================
REM  ELEVATE TO ADMIN IF NEEDED
REM ============================================================

REM Check if running as administrator
net session >nul 2>&1
if errorlevel 1 (
    echo [*] Requesting administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs" 
    exit /b 0
)

REM Create log file
set LOG_FILE=%TEMP%\setup-debug.log
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

echo [%date% %time%] ===== SCRIPT START ===== >> "%LOG_FILE%"

echo.
echo ============================================================
echo  QUIC File Transfer System - Windows Setup
echo ============================================================
echo.
echo Log file: %LOG_FILE%
echo [*] Script directory: %SCRIPT_DIR%
echo.

REM ============================================================
REM  STEP 1: CHECK AND INSTALL WSL2
REM ============================================================

echo [*] Step 1: Checking WSL2...

REM Simple test - does wsl --version work?
wsl --version >nul 2>>"%LOG_FILE%"
if errorlevel 1 (
    REM WSL2 is NOT installed - install it
    echo [!] WSL2 not detected - will install
    echo.
    echo ============================================================
    echo  INSTALLING WSL2
    echo ============================================================
    echo.
    echo This script will enable WSL2 features.
    echo Your computer WILL RESTART after installation.
    echo.
    echo SAVE YOUR WORK NOW!
    echo.
    echo After restart, run this script again.
    echo.
    echo Press any key to proceed...
    pause
    
    echo.
    echo [*] Installing WSL feature...
    echo [%date% %time%] Running: dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart >> "%LOG_FILE%"
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart >>"%LOG_FILE%" 2>&1
    
    echo [*] Installing Virtual Machine Platform...
    echo [%date% %time%] Running: dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart >> "%LOG_FILE%"
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart >>"%LOG_FILE%" 2>&1
    
    echo.
    echo [OK] WSL2 features enabled successfully
    echo [%date% %time%] DISM commands completed >> "%LOG_FILE%"
    echo.
    echo [*] Restarting in 10 seconds...
    echo [*] Press Ctrl+C to cancel
    timeout /t 10 /nobreak
    echo [%date% %time%] Initiating restart >> "%LOG_FILE%"
    shutdown /r /t 0 /c "WSL2 installation complete. Restarting."
    exit /b 0
)

echo [OK] WSL2 is installed
echo [%date% %time%] WSL2 verified >> "%LOG_FILE%"

REM ============================================================
REM  STEP 2: CHECK AND INSTALL DOCKER
REM ============================================================

echo.
echo [*] Step 2: Checking Docker...

where docker >nul 2>&1
if errorlevel 1 (
    echo [!] Docker not found - installing
    echo [*] Downloading Docker Desktop...
    
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile '%TEMP%\DockerInstaller.exe'"
    
    if exist "%TEMP%\DockerInstaller.exe" (
        echo [*] Running Docker installer...
        start /wait "%TEMP%\DockerInstaller.exe" install --accept-license --wsl2 >>"%LOG_FILE%" 2>&1
        echo [*] Docker installed - waiting for daemon...
        timeout /t 5
    ) else (
        echo [X] Failed to download Docker
        echo Please install manually: https://www.docker.com/products/docker-desktop
        pause
        exit /b 1
    )
) else (
    echo [OK] Docker is installed
)

echo [*] Waiting for Docker to be ready (up to 2 minutes)...
set TIMEOUT=120
set ELAPSED=0

:wait_docker
docker ps >nul 2>>"%LOG_FILE%"
if errorlevel 1 (
    if !ELAPSED! lss !TIMEOUT! (
        timeout /t 3 /nobreak >nul
        set /a ELAPSED=!ELAPSED!+3
        goto wait_docker
    )
    echo [!] Docker not responding, but continuing...
) else (
    echo [OK] Docker is ready
)

REM ============================================================
REM  STEP 3: LOAD CREDENTIALS AND PREPARE
REM ============================================================

echo.
echo [*] Step 3: Loading credentials...

set TAILSCALE_AUTHKEY=
set TAILSCALE_API_KEY=
set TAILNET=
set FLASK_ENV=production

if exist "%SCRIPT_DIR%\templates\quic-file-transfer\.env" (
    for /f "usebackq tokens=* delims=" %%a in ("%SCRIPT_DIR%\templates\quic-file-transfer\.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" (
            set "%%a"
        )
    )
) else (
    echo [X] .env file not found
    pause
    exit /b 1
)

if "!TAILSCALE_AUTHKEY!"=="" (
    echo [X] TAILSCALE_AUTHKEY missing in .env
    pause
    exit /b 1
)

echo [OK] Credentials loaded

REM ============================================================
REM  STEP 4: SETUP DOWNLOADS FOLDER
REM ============================================================

echo.
echo [*] Step 4: Setting up downloads folder...

set DOWNLOADS_PATH=
if exist "%USERPROFILE%\Descargas" (
    set DOWNLOADS_PATH=%USERPROFILE%\Descargas
) else (
    set DOWNLOADS_PATH=%USERPROFILE%\Downloads
    mkdir "!DOWNLOADS_PATH!" 2>nul
)

echo [OK] Downloads: !DOWNLOADS_PATH!

REM ============================================================
REM  STEP 5: INSTALL AND CONNECT TAILSCALE
REM ============================================================

echo.
echo [*] Step 5: Setting up Tailscale...

where tailscale >nul 2>&1
if errorlevel 1 (
    echo [*] Installing Tailscale...
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://pkgs.tailscale.com/windows/Tailscale-Setup.exe' -OutFile '%TEMP%\Tailscale-Setup.exe'; Start-Process '%TEMP%\Tailscale-Setup.exe' -Wait"
    timeout /t 3
)

tasklist /FI "IMAGENAME eq tailscaled.exe" 2>nul | find /I "tailscaled.exe" >nul
if errorlevel 1 (
    echo [*] Starting Tailscale daemon...
    net start Tailscale 2>nul || start "" Tailscale.exe
    timeout /t 3
)

echo [*] Connecting to Tailscale...
tailscale logout 2>nul
timeout /t 2
tailscale up --authkey=!TAILSCALE_AUTHKEY! --accept-routes --accept-dns 2>nul
timeout /t 2

for /f "usebackq delims=" %%i in (`tailscale ip -4 2^>nul`) do set TS_IP=%%i

if "!TS_IP!"=="" (
    echo [!] Could not get Tailscale IP - continuing anyway
    set TS_IP=unknown
)

echo [OK] Tailscale IP: !TS_IP!

REM ============================================================
REM  STEP 6: START MONITORS
REM ============================================================

echo.
echo [*] Step 6: Starting monitors...

taskkill /F /FI "WINDOWTITLE eq *Monitor*" 2>nul
timeout /t 1

start "Tailscale Monitor" /min python "%SCRIPT_DIR%\tailscale-monitor.py"
timeout /t 1
start "Tailscale API" /min python "%SCRIPT_DIR%\tailscale-api.py"
timeout /t 1
start "Monitor de Alertas" /min python "%SCRIPT_DIR%\msg-monitor.py"
timeout /t 1
start "Monitor de Videos" /min python "%SCRIPT_DIR%\video-monitor.py"
timeout /t 1

echo [OK] Monitors started

REM ============================================================
REM  STEP 7: START DOCKER CONTAINERS
REM ============================================================

echo.
echo [*] Step 7: Starting Docker containers...

docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo [X] docker compose not found
        pause
        exit /b 1
    )
    set COMPOSE_CMD=docker-compose
) else (
    set COMPOSE_CMD=docker compose
)

echo [*] Building containers (this may take a few minutes)...

!COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml ^
    --env-file templates\quic-file-transfer\.env ^
    -e DOWNLOADS_PATH=%DOWNLOADS_PATH% ^
    -e HOST_TAILSCALE_IP=%TS_IP% ^
    up --build -d >>"%LOG_FILE%" 2>&1

if errorlevel 1 (
    echo [X] Docker compose failed
    echo Check log: %LOG_FILE%
    pause
    exit /b 1
)

echo [OK] Containers started

REM ============================================================
REM  SUCCESS
REM ============================================================

echo.
echo ============================================================
echo  OK SYSTEM READY
echo ============================================================
echo.
echo [OK] Tailscale IP: %TS_IP%
echo [OK] Web: http://localhost:8080
echo [OK] Downloads: %DOWNLOADS_PATH%
echo.
echo Next: Open http://localhost:8080 in your browser
echo.

start http://localhost:8080 2>nul

echo [%date% %time%] === SETUP COMPLETE === >> "%LOG_FILE%"
pause
