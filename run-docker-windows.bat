@echo off
REM ============================================================
REM  run-docker.bat - Windows version of run-docker.sh
REM  Works on Windows 10/11 Home, Pro, Enterprise (with WSL2)
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ════════════════════════════════════════════════════════════
echo  QUIC File Transfer System - Windows Setup
echo ════════════════════════════════════════════════════════════
echo.

REM Detect current script directory
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM ============================================================
REM  WSL2 AND DOCKER INSTALLATION (AUTOMATIC)
REM ============================================================

echo [*] Checking prerequisites...
echo.

REM Check if WSL2 is installed
echo [*] Checking WSL2...
wsl --list --verbose >nul 2>&1
if errorlevel 1 (
    echo [×] WSL2 not found, installing...
    echo [!] This will enable virtualization features (requires restart)
    echo.
    
    REM Enable WSL2 with automatic restart
    echo [*] Enabling WSL2 and Ubuntu...
    powershell -Command "Start-Process 'powershell' -ArgumentList 'wsl --install -d Ubuntu' -Wait -Verb RunAs"
    
    echo.
    echo [✓] WSL2 installation initiated
    echo [!] System will restart in 30 seconds...
    echo [!] After restart, please run this script again
    echo.
    
    REM Restart Windows (60 second delay gives user time to save)
    shutdown /r /t 60 /c "WSL2 installation complete. Restarting to apply changes..."
    pause
    exit /b 0
) else (
    echo [✓] WSL2 is installed
)

REM Check if Docker is installed
where docker >nul 2>&1
if errorlevel 1 (
    echo [×] Docker Desktop not found, installing...
    
    echo [*] Downloading Docker Desktop...
    powershell -NoProfile -Command ^
        "$ProgressPreference='SilentlyContinue'; ^
        Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' ^
        -OutFile '%TEMP%\DockerInstaller.exe'; ^
        Write-Host '[✓] Docker Desktop downloaded'"
    
    if exist "%TEMP%\DockerInstaller.exe" (
        echo [*] Running Docker Desktop installer...
        start /wait "%TEMP%\DockerInstaller.exe" install --accept-license --wsl2
        
        timeout /t 5 /nobreak >nul
        echo [✓] Docker Desktop installed
    ) else (
        echo [✗] Failed to download Docker Desktop
        echo Please download manually from: https://www.docker.com/products/docker-desktop
        pause
        exit /b 1
    )
) else (
    echo [✓] Docker Desktop is installed
)

echo.

REM Wait for Docker to be ready
echo [*] Waiting for Docker to be ready (this may take a minute on first run)...
set TIMEOUT=60
set ELAPSED=0

:wait_docker
docker ps >nul 2>&1
if errorlevel 1 (
    if !ELAPSED! lss !TIMEOUT! (
        timeout /t 3 /nobreak >nul
        set /a ELAPSED=!ELAPSED!+3
        goto wait_docker
    )
    echo [!] Docker not responding after !TIMEOUT! seconds, but continuing...
) else (
    echo [✓] Docker is ready
)

echo.

REM ============================================================
REM  LOAD CREDENTIALS
REM ============================================================

set TAILSCALE_AUTHKEY=
set TAILSCALE_API_KEY=
set TAILNET=
set FLASK_ENV=production

if exist "%SCRIPT_DIR%\templates\quic-file-transfer\.env" (
    echo [✓] Loading credentials from .env...
    for /f "usebackq tokens=* delims=" %%a in ("%SCRIPT_DIR%\templates\quic-file-transfer\.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" (
            set "%%a"
        )
    )
) else (
    echo [✗] .env file not found at templates\quic-file-transfer\.env
    echo Please create it with your TAILSCALE_AUTHKEY
    pause
    exit /b 1
)

REM Validate TAILSCALE_AUTHKEY
if "!TAILSCALE_AUTHKEY!"=="" (
    echo [✗] Error: TAILSCALE_AUTHKEY not defined in .env
    echo Please edit templates\quic-file-transfer\.env and add:
    echo   TAILSCALE_AUTHKEY=tskey-auth-...
    pause
    exit /b 1
)

echo [✓] Credentials loaded successfully
echo.

REM ============================================================
REM  DETECT DOWNLOADS FOLDER
REM ============================================================

set DOWNLOADS_PATH=
if exist "%USERPROFILE%\Descargas" (
    set DOWNLOADS_PATH=%USERPROFILE%\Descargas
    echo [✓] Spanish Downloads folder detected: !DOWNLOADS_PATH!
) else if exist "%USERPROFILE%\Downloads" (
    set DOWNLOADS_PATH=%USERPROFILE%\Downloads
    echo [✓] English Downloads folder detected: !DOWNLOADS_PATH!
) else (
    set DOWNLOADS_PATH=%USERPROFILE%\Downloads
    mkdir "!DOWNLOADS_PATH!" 2>nul
    echo [✓] Downloads folder created: !DOWNLOADS_PATH!
)

if not exist "!DOWNLOADS_PATH!" (
    echo [✗] Error: Could not establish DOWNLOADS_PATH
    pause
    exit /b 1
)

echo.

REM ============================================================
REM  TAILSCALE INSTALLATION AND CONNECTION
REM ============================================================

echo ════════════════════════════════════════════════════════════
echo  TAILSCALE CONFIGURATION (HOST)
echo ════════════════════════════════════════════════════════════
echo.

REM Check if Tailscale is installed
where tailscale >nul 2>&1
if errorlevel 1 (
    echo [×] Tailscale not installed, attempting to install...
    echo.
    
    REM Try winget first (Windows 11+)
    where winget >nul 2>&1
    if errorlevel 1 (
        echo [!] winget not found. Trying alternative installation...
        
        REM Download and run MSI installer
        echo [*] Downloading Tailscale installer...
        powershell -NoProfile -Command ^
            "$ProgressPreference='SilentlyContinue'; ^
            Invoke-WebRequest -Uri 'https://pkgs.tailscale.com/windows/Tailscale-Setup.exe' ^
            -OutFile '%TEMP%\Tailscale-Setup.exe'; ^
            Start-Process '%TEMP%\Tailscale-Setup.exe' -Wait"
        
        if errorlevel 1 (
            echo [✗] Failed to install Tailscale
            echo Please install manually from: https://tailscale.com/download/windows
            pause
            exit /b 1
        )
    ) else (
        echo [*] Installing Tailscale with winget...
        call winget install Tailscale.Tailscale -e --silent
        
        if errorlevel 1 (
            echo [!] winget installation had issues, trying MSI installer...
            powershell -NoProfile -Command ^
                "$ProgressPreference='SilentlyContinue'; ^
                Invoke-WebRequest -Uri 'https://pkgs.tailscale.com/windows/Tailscale-Setup.exe' ^
                -OutFile '%TEMP%\Tailscale-Setup.exe'; ^
                Start-Process '%TEMP%\Tailscale-Setup.exe' -Wait"
        )
    )
    
    REM Verify installation
    timeout /t 3 /nobreak >nul
    where tailscale >nul 2>&1
    if errorlevel 1 (
        echo [✗] Tailscale still not found after installation attempt
        echo Please install manually: https://tailscale.com/download/windows
        pause
        exit /b 1
    )
    
    echo [✓] Tailscale installed successfully
) else (
    echo [✓] Tailscale already installed
)

echo.

REM Check if tailscaled daemon is running
tasklist /FI "IMAGENAME eq tailscaled.exe" 2>nul | find /I /N "tailscaled.exe" >nul
if errorlevel 1 (
    echo [×] Tailscale daemon not running, starting...
    
    REM Windows doesn't have "services start" like macOS, just run the exe
    net start Tailscale 2>nul || (
        REM If net start fails, try launching the GUI which starts daemon
        start "" Tailscale.exe
        timeout /t 3 /nobreak >nul
    )
    
    REM Wait for daemon to start
    set TIMEOUT=15
    set ELAPSED=0
    :wait_daemon
    tasklist /FI "IMAGENAME eq tailscaled.exe" 2>nul | find /I /N "tailscaled.exe" >nul
    if errorlevel 1 (
        if !ELAPSED! lss !TIMEOUT! (
            timeout /t 1 /nobreak >nul
            set /a ELAPSED=!ELAPSED!+1
            goto wait_daemon
        )
        echo [✗] tailscaled did not start within !TIMEOUT! seconds
        pause
        exit /b 1
    )
    echo [✓] Tailscale daemon started
) else (
    echo [✓] Tailscale daemon already running
)

echo.

REM Check Tailscale status and connect if needed
echo [*] Checking Tailscale connection status...
for /f "usebackq delims=" %%i in (`tailscale ip -4 2^>nul`) do set TS_IP=%%i

if not "!TS_IP!"=="" (
    echo [✓] Tailscale already connected
    echo     IP: !TS_IP!
) else (
    echo [×] Tailscale not connected, connecting with authkey...
    
    REM Try to logout first (clean state)
    tailscale logout 2>nul
    timeout /t 2 /nobreak >nul
    
    REM Connect with retry logic
    set RETRY_COUNT=0
    :tailscale_connect_retry
    
    if !RETRY_COUNT! gtr 5 (
        echo [✗] Failed to connect after 5 attempts
        echo Please verify your TAILSCALE_AUTHKEY is valid and not expired
        echo Generate new key: https://login.tailscale.com/admin/settings/keys
        pause
        exit /b 1
    )
    
    set /a RETRY_COUNT=!RETRY_COUNT!+1
    echo [*] Connection attempt !RETRY_COUNT!/5...
    
    tailscale up --authkey=!TAILSCALE_AUTHKEY! --accept-routes --accept-dns 2>nul
    
    if errorlevel 1 (
        echo [!] Connection failed, waiting 5 seconds...
        timeout /t 5 /nobreak >nul
        goto tailscale_connect_retry
    )
    
    REM Verify connection
    timeout /t 2 /nobreak >nul
    for /f "usebackq delims=" %%i in (`tailscale ip -4 2^>nul`) do set TS_IP=%%i
    
    if "!TS_IP!"=="" (
        echo [!] Still not connected, retrying...
        timeout /t 3 /nobreak >nul
        goto tailscale_connect_retry
    )
    
    echo [✓] Tailscale connected successfully
    echo     IP: !TS_IP!
)

timeout /t 2 /nobreak >nul
set HOST_TAILSCALE_IP=!TS_IP!

echo.

REM ============================================================
REM  DOCKER COMPOSE SETUP
REM ============================================================

echo ════════════════════════════════════════════════════════════
echo  STARTING DOCKER
echo ════════════════════════════════════════════════════════════
echo.

REM Check Docker availability
where docker >nul 2>&1
if errorlevel 1 (
    echo [✗] Docker not found. Please install Docker Desktop from:
    echo    https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo [✓] Docker found
echo.

REM Determine compose command
docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo [✗] docker compose not found
        echo Please install Docker Compose: https://docs.docker.com/compose/install/
        pause
        exit /b 1
    )
    set COMPOSE_CMD=docker-compose
) else (
    set COMPOSE_CMD=docker compose
)

echo [*] Using: !COMPOSE_CMD!
echo.

REM Wait for Tailscale to sync peers (up to 45 seconds)
echo [*] Waiting for Tailscale to sync with peers (this may take a minute)...
set TIMEOUT=45
set ELAPSED=0
set PEER_COUNT=0

:wait_peers
if !ELAPSED! gtr !TIMEOUT! (
    echo [!] Timeout waiting for peers, but continuing...
    goto peers_done
)

REM Try to get peer count from tailscale status
for /f "usebackq delims=" %%i in (`tailscale status --json 2^>nul ^| find "HostName" 2^>nul ^| find /c "HostName"`) do set PEER_COUNT=%%i

if !PEER_COUNT! gtr 0 (
    echo [✓] Peers detected: !PEER_COUNT!
    goto peers_done
)

set /a ATTEMPT=!ELAPSED!/3 + 1
echo [*] Attempt !ATTEMPT!/15: Waiting for peer sync...
timeout /t 3 /nobreak >nul
set /a ELAPSED=!ELAPSED!+3
goto wait_peers

:peers_done
echo.

REM Generate tailscale_status.json from host
echo [*] Generating tailscale_status.json...
tailscale status --json > "%SCRIPT_DIR%\templates\quic-file-transfer\app\tailscale_status.json" 2>nul
if errorlevel 1 (
    echo [!] Warning: Could not generate status JSON
) else (
    echo [✓] Status JSON generated
)

echo.

REM ============================================================
REM  START HOST MONITORS
REM ============================================================

REM Kill any existing monitors
taskkill /F /FI "WINDOWTITLE eq Tailscale Monitor*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Tailscale API*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Monitor de Alertas*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Monitor de Videos*" 2>nul

timeout /t 1 /nobreak >nul

REM Start Tailscale monitor
echo [*] Starting Tailscale monitor (automatic reconnection)...
start "Tailscale Monitor" /min python "%SCRIPT_DIR%\tailscale-monitor.py"
timeout /t 2 /nobreak >nul
echo [✓] Tailscale monitor started
echo.

REM Start Tailscale API service
echo [*] Starting Tailscale API service (port 5001)...
start "Tailscale API" /min python "%SCRIPT_DIR%\tailscale-api.py"
timeout /t 2 /nobreak >nul
echo [✓] Tailscale API service started
echo.

REM Start message monitor (.msg alerts)
echo [*] Starting message monitor (.msg alerts)...
start "Monitor de Alertas" /min python "%SCRIPT_DIR%\msg-monitor.py"
timeout /t 2 /nobreak >nul
echo [✓] Message monitor started
echo.

REM Start video monitor
echo [*] Starting video monitor...
start "Monitor de Videos" /min python "%SCRIPT_DIR%\video-monitor.py"
timeout /t 2 /nobreak >nul
echo [✓] Video monitor started
echo.

REM ============================================================
REM  START DOCKER CONTAINERS
REM ============================================================

echo [*] Building and starting Docker containers...
echo    (this may take a few minutes on first run)
echo.

!COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml ^
    --env-file templates\quic-file-transfer\.env ^
    -e DOWNLOADS_PATH=%DOWNLOADS_PATH% ^
    -e HOST_TAILSCALE_IP=%HOST_TAILSCALE_IP% ^
    up --build -d

if errorlevel 1 (
    echo [✗] Error: docker compose failed
    echo Run for more details:
    echo   !COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml logs
    pause
    exit /b 1
)

echo [✓] Containers started successfully
echo.

timeout /t 3 /nobreak >nul

REM ============================================================
REM  SUCCESS MESSAGE AND NEXT STEPS
REM ============================================================

echo ════════════════════════════════════════════════════════════
echo  ✅ SYSTEM READY
echo ════════════════════════════════════════════════════════════
echo.
echo [✓] Host Tailscale IP: %HOST_TAILSCALE_IP%
echo [✓] Web Interface:     http://localhost:8080
echo [✓] Downloads:        %DOWNLOADS_PATH%
echo.
echo Next Steps:
echo  1. Open http://localhost:8080 in your browser
echo  2. Upload files - they'll be sent to all connected peers
echo  3. Videos will open automatically when received
echo  4. Alerts will play with notifications and TTS
echo.
echo Logs:
echo  - Docker:     !COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml logs -f
echo  - Tailscale:  type ^"%TEMP%\tailscale-monitor.log^"
echo  - Alerts:     type ^"%TEMP%\msg-monitor.log^"
echo  - Videos:     type ^"%TEMP%\video-monitor.log^"
echo.
echo To stop containers:
echo  !COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml down
echo.

REM Try to open browser
start http://localhost:8080 2>nul

echo ✅ Ready to transfer files through Tailscale!
echo.

pause
