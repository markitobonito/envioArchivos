@echo off
REM ============================================================
REM  run-docker-windows.bat - Windows Setup Script
REM  Works on Windows 10/11 Home, Pro, Enterprise (with WSL2)
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Create log file
set LOG_FILE=%TEMP%\setup-debug.log
set WSL_INSTALL_MARKER=%TEMP%\wsl-install-marker.txt
echo. > "%LOG_FILE%"
echo [%date% %time%] ===== SCRIPT START ===== >> "%LOG_FILE%"

echo.
echo ============================================================
echo  QUIC File Transfer System - Windows Setup
echo ============================================================
echo.
echo Log file: %LOG_FILE%
echo.

REM Detect current script directory
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

echo [*] Script directory: %SCRIPT_DIR%
echo [%date% %time%] Script DIR: %SCRIPT_DIR% >> "%LOG_FILE%"
echo.

REM Check if WSL2 is installed
echo [*] Checking WSL2 installation status...
echo [%date% %time%] === WSL2 CHECK START === >> "%LOG_FILE%"

REM Check if we previously installed WSL features (marker file)
if exist "%WSL_INSTALL_MARKER%" (
    echo [*] Found WSL installation marker - attempting to verify WSL2 is now working...
    echo [%date% %time%] WSL marker exists, verifying installation >> "%LOG_FILE%"
) else (
    echo [*] First time running or marker cleaned
    echo [%date% %time%] No WSL marker found >> "%LOG_FILE%"
)

REM Test 1: Try wsl --version (most reliable test after restart)
echo [*] Test 1: Running 'wsl --version' to verify WSL2...
echo [%date% %time%] Test 1: wsl --version >> "%LOG_FILE%"
wsl --version >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [!] wsl --version failed
    echo [%date% %time%] wsl --version FAILED >> "%LOG_FILE%"
    
    REM If marker exists, we already tried to install - something is wrong
    if exist "%WSL_INSTALL_MARKER%" (
        echo.
        echo ============================================================
        echo  ERROR: WSL2 Installation Failed
        echo ============================================================
        echo.
        echo [X] WSL2 features should be active but aren't working
        echo.
        echo Possible causes:
        echo  1. Virtualization not enabled in BIOS (most likely)
        echo  2. Hyper-V conflicting with WSL2
        echo  3. Windows needs another restart
        echo.
        echo Try these steps:
        echo  1. Restart your computer again manually
        echo  2. Check BIOS: enable CPU virtualization (VT-x or AMD-V)
        echo  3. Run Windows Update and restart
        echo  4. If still failing, install Hyper-V and try again
        echo.
        echo For manual help, visit:
        echo  https://docs.microsoft.com/en-us/windows/wsl/install
        echo.
        del "%WSL_INSTALL_MARKER%"
        pause
        exit /b 1
    )
    
    REM First time - need to enable WSL features
    echo.
    echo ============================================================
    echo  WSL2 INSTALLATION REQUIRED
    echo ============================================================
    echo.
    echo [*] WSL2 features are NOT activated
    echo.
    echo This will:
    echo  1. Enable Windows Subsystem for Linux (WSL)
    echo  2. Enable Virtual Machine Platform
    echo  3. Restart your computer (you will lose unsaved work!)
    echo.
    echo Before continuing:
    echo  [!] SAVE YOUR WORK
    echo  [!] CLOSE ALL APPLICATIONS
    echo.
    echo After restart:
    echo  [!] Run this script again
    echo.
    echo Press any key to proceed with enablement...
    pause
    
    REM Mark that we're attempting installation
    echo WSL installation attempted at %date% %time% > "%WSL_INSTALL_MARKER%"
    
    REM Enable WSL2 features with DISM
    echo.
    echo [*] Enabling Windows Subsystem for Linux feature...
    echo [%date% %time%] Running DISM for WSL >> "%LOG_FILE%"
    powershell -Command "Start-Process 'cmd' -ArgumentList '/c dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart ^>^> ^"%LOG_FILE%^" 2^>^&1' -Verb RunAs -Wait"
    
    echo [*] Enabling Virtual Machine Platform feature...
    echo [%date% %time%] Running DISM for Virtual Machine Platform >> "%LOG_FILE%"
    powershell -Command "Start-Process 'cmd' -ArgumentList '/c dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart ^>^> ^"%LOG_FILE%^" 2^>^&1' -Verb RunAs -Wait"
    
    echo.
    echo [OK] WSL2 features have been enabled
    echo [%date% %time%] DISM features enabled, preparing restart >> "%LOG_FILE%"
    echo.
    echo ============================================================
    echo  RESTART REQUIRED
    echo ============================================================
    echo.
    echo [!] Your computer MUST restart for the changes to take effect
    echo.
    echo [*] Restarting in 10 seconds...
    echo [*] Press Ctrl+C if you need to cancel
    echo.
    echo [%date% %time%] Initiating restart >> "%LOG_FILE%"
    timeout /t 10 /nobreak
    shutdown /r /t 0 /c "WSL2 features activated. Restarting system."
    exit /b 0
)

REM If we get here, wsl --version worked!
echo [OK] WSL2 is now active and working!
echo [%date% %time%] WSL is working >> "%LOG_FILE%"

REM Clean up marker file since WSL is now working
if exist "%WSL_INSTALL_MARKER%" (
    del "%WSL_INSTALL_MARKER%"
    echo [OK] Removing installation marker - WSL2 confirmed working
    echo [%date% %time%] Cleaned WSL marker >> "%LOG_FILE%"
)

REM Now check if Ubuntu is installed
echo [*] Checking if Ubuntu is installed...
echo [%date% %time%] Checking Ubuntu distribution >> "%LOG_FILE%"
wsl -d Ubuntu -e echo "test" >nul 2>>"%LOG_FILE%"
if errorlevel 1 (
    echo [*] Ubuntu not installed, installing now...
    echo [%date% %time%] Ubuntu not found, installing >> "%LOG_FILE%"
    wsl --install -d Ubuntu --no-launch >>"%LOG_FILE%" 2>&1
    
    if errorlevel 1 (
        echo [!] Could not auto-install Ubuntu
        echo [*] No worries - Docker will handle this
        echo [%date% %time%] Ubuntu auto-install failed >> "%LOG_FILE%"
    ) else (
        echo [OK] Ubuntu installed successfully
        echo [%date% %time%] Ubuntu installed >> "%LOG_FILE%"
    )
) else (
    echo [OK] Ubuntu is already installed
    echo [%date% %time%] Ubuntu already installed >> "%LOG_FILE%"
)

echo [OK] WSL2 verification complete
echo [%date% %time%] WSL2 CHECK PASSED >> "%LOG_FILE%"
timeout /t 2 /nobreak >nul

REM Check if Docker is installed
where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo [X] Docker Desktop not found, installing...
    echo [%date% %time%] Docker not found - starting installation >> "%LOG_FILE%"
    
    echo [*] Downloading Docker Desktop...
    echo [%date% %time%] Downloading Docker Desktop installer >> "%LOG_FILE%"
    powershell -NoProfile -Command ^
        "$ProgressPreference='SilentlyContinue'; ^
        Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' ^
        -OutFile '%TEMP%\DockerInstaller.exe'; ^
        Write-Host '[OK] Docker Desktop downloaded'"
    
    if exist "%TEMP%\DockerInstaller.exe" (
        echo [OK] Docker installer downloaded successfully
        echo [%date% %time%] Docker installer downloaded >> "%LOG_FILE%"
        echo [*] Running Docker Desktop installer...
        echo [%date% %time%] Running installer /install --accept-license --wsl2 >> "%LOG_FILE%"
        start /wait "%TEMP%\DockerInstaller.exe" install --accept-license --wsl2 >>"%LOG_FILE%" 2>&1
        
        timeout /t 5 /nobreak >nul
        echo [OK] Docker Desktop installed
        echo [%date% %time%] Docker Desktop installation completed >> "%LOG_FILE%"
    ) else (
        echo [X] Failed to download Docker Desktop
        echo [%date% %time%] ERROR: Failed to download Docker installer >> "%LOG_FILE%"
        echo Please download manually from: https://www.docker.com/products/docker-desktop
        pause
        exit /b 1
    )
) else (
    echo [OK] Docker Desktop is already installed
    echo [%date% %time%] Docker already installed >> "%LOG_FILE%"
)

echo.

REM Wait for Docker to be ready
echo [*] Waiting for Docker to be ready (this may take up to 2 minutes on first run after WSL2 install)...
echo [%date% %time%] === DOCKER READINESS CHECK === >> "%LOG_FILE%"
set TIMEOUT=120
set ELAPSED=0

:wait_docker
echo [%date% %time%] Docker check attempt (!ELAPSED!s/!TIMEOUT!s) >> "%LOG_FILE%"
docker ps >nul 2>>"%LOG_FILE%"
if errorlevel 1 (
    if !ELAPSED! lss !TIMEOUT! (
        timeout /t 3 /nobreak >nul
        set /a ELAPSED=!ELAPSED!+3
        goto wait_docker
    )
    echo [!] Docker not responding after !TIMEOUT! seconds
    echo [%date% %time%] Docker timeout after !TIMEOUT!s >> "%LOG_FILE%"
    echo [!] This may be normal on first run - Docker is initializing WSL2
    echo [*] Continuing anyway...
) else (
    echo [OK] Docker is ready
    echo [%date% %time%] Docker is READY >> "%LOG_FILE%"
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
    echo [OK] Loading credentials from .env...
    for /f "usebackq tokens=* delims=" %%a in ("%SCRIPT_DIR%\templates\quic-file-transfer\.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" (
            set "%%a"
        )
    )
) else (
    echo [X] .env file not found at templates\quic-file-transfer\.env
    echo Please create it with your TAILSCALE_AUTHKEY
    pause
    exit /b 1
)

REM Validate TAILSCALE_AUTHKEY
if "!TAILSCALE_AUTHKEY!"=="" (
    echo [X] Error: TAILSCALE_AUTHKEY not defined in .env
    echo Please edit templates\quic-file-transfer\.env and add:
    echo   TAILSCALE_AUTHKEY=tskey-auth-...
    pause
    exit /b 1
)

echo [OK] Credentials loaded successfully
echo.

REM ============================================================
REM  DETECT DOWNLOADS FOLDER
REM ============================================================

set DOWNLOADS_PATH=
if exist "%USERPROFILE%\Descargas" (
    set DOWNLOADS_PATH=%USERPROFILE%\Descargas
    echo [OK] Spanish Downloads folder detected: !DOWNLOADS_PATH!
) else if exist "%USERPROFILE%\Downloads" (
    set DOWNLOADS_PATH=%USERPROFILE%\Downloads
    echo [OK] English Downloads folder detected: !DOWNLOADS_PATH!
) else (
    set DOWNLOADS_PATH=%USERPROFILE%\Downloads
    mkdir "!DOWNLOADS_PATH!" 2>nul
    echo [OK] Downloads folder created: !DOWNLOADS_PATH!
)

if not exist "!DOWNLOADS_PATH!" (
    echo [X] Error: Could not establish DOWNLOADS_PATH
    pause
    exit /b 1
)

echo.

REM ============================================================
REM  TAILSCALE INSTALLATION AND CONNECTION
REM ============================================================

echo ============================================================
echo  TAILSCALE CONFIGURATION (HOST)
echo ============================================================
echo.

REM Check if Tailscale is installed
where tailscale >nul 2>&1
if errorlevel 1 (
    echo [X] Tailscale not installed, attempting to install...
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
            echo [X] Failed to install Tailscale
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
        echo [X] Tailscale still not found after installation attempt
        echo Please install manually: https://tailscale.com/download/windows
        pause
        exit /b 1
    )
    
    echo [OK] Tailscale installed successfully
) else (
    echo [OK] Tailscale already installed
)

echo.

REM Check if tailscaled daemon is running
tasklist /FI "IMAGENAME eq tailscaled.exe" 2>nul | find /I /N "tailscaled.exe" >nul
if errorlevel 1 (
    echo [X] Tailscale daemon not running, starting...
    
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
        echo [X] tailscaled did not start within !TIMEOUT! seconds
        pause
        exit /b 1
    )
    echo [OK] Tailscale daemon started
) else (
    echo [OK] Tailscale daemon already running
)

echo.

REM Check Tailscale status and connect if needed
echo [*] Checking Tailscale connection status...
for /f "usebackq delims=" %%i in (`tailscale ip -4 2^>nul`) do set TS_IP=%%i

if not "!TS_IP!"=="" (
    echo [OK] Tailscale already connected
    echo     IP: !TS_IP!
) else (
    echo [X] Tailscale not connected, connecting with authkey...
    
    REM Try to logout first (clean state)
    tailscale logout 2>nul
    timeout /t 2 /nobreak >nul
    
    REM Connect with retry logic
    set RETRY_COUNT=0
    :tailscale_connect_retry
    
    if !RETRY_COUNT! gtr 5 (
        echo [X] Failed to connect after 5 attempts
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
    
    echo [OK] Tailscale connected successfully
    echo     IP: !TS_IP!
)

timeout /t 2 /nobreak >nul
set HOST_TAILSCALE_IP=!TS_IP!

echo.

REM ============================================================
REM  DOCKER COMPOSE SETUP
REM ============================================================

echo ============================================================
echo  STARTING DOCKER
echo ============================================================
echo.

REM Check Docker availability
where docker >nul 2>&1
if errorlevel 1 (
    echo [X] Docker not found. Please install Docker Desktop from:
    echo    https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo [OK] Docker found
echo.

REM Determine compose command
docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo [X] docker compose not found
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
echo [%date% %time%] Starting Tailscale monitor >> "%LOG_FILE%"
start "Tailscale Monitor" /min python "%SCRIPT_DIR%\tailscale-monitor.py"
timeout /t 2 /nobreak >nul
echo [✓] Tailscale monitor started
echo.

REM Start Tailscale API service
echo [*] Starting Tailscale API service (port 5001)...
echo [%date% %time%] Starting Tailscale API service >> "%LOG_FILE%"
start "Tailscale API" /min python "%SCRIPT_DIR%\tailscale-api.py"
timeout /t 2 /nobreak >nul
echo [✓] Tailscale API service started
echo.

REM Start message monitor (.msg alerts)
echo [*] Starting message monitor (.msg alerts)...
echo [%date% %time%] Starting message monitor >> "%LOG_FILE%"
start "Monitor de Alertas" /min python "%SCRIPT_DIR%\msg-monitor.py"
timeout /t 2 /nobreak >nul
echo [✓] Message monitor started
echo.

REM Start video monitor
echo [*] Starting video monitor...
echo [%date% %time%] Starting video monitor >> "%LOG_FILE%"
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
    echo [X] Error: docker compose failed
    echo Run for more details:
    echo   !COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml logs
    pause
    exit /b 1
)

echo [OK] Containers started successfully
echo.

timeout /t 3 /nobreak >nul

REM ============================================================
REM  SUCCESS MESSAGE AND NEXT STEPS
REM ============================================================

echo ============================================================
echo  OK SYSTEM READY
echo ============================================================
echo.
echo [%date% %time%] === SYSTEM READY === >> "%LOG_FILE%"
echo [OK] Host Tailscale IP: %HOST_TAILSCALE_IP%
echo [OK] Web Interface:     http://localhost:8080
echo [OK] Downloads:        %DOWNLOADS_PATH%
echo [OK] DEBUG LOG:         %LOG_FILE%
echo.
echo Next Steps:
echo  1. Open http://localhost:8080 in your browser
echo  2. Upload files - they'll be sent to all connected peers
echo  3. Videos will open automatically when received
echo  4. Alerts will play with notifications and TTS
echo.
echo Logs and Debug Info:
echo  - Setup Debug Log:  %LOG_FILE%
echo  - Docker:           !COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml logs -f
echo  - Tailscale:        type ^"%TEMP%\tailscale-monitor.log^"
echo  - Alerts:           type ^"%TEMP%\msg-monitor.log^"
echo  - Videos:           type ^"%TEMP%\video-monitor.log^"
echo.
echo To stop containers:
echo  !COMPOSE_CMD! -f templates\quic-file-transfer\docker-compose.yml down
echo.

REM Try to open browser
start http://localhost:8080 2>nul

echo OK Ready to transfer files through Tailscale!
echo [%date% %time%] === SCRIPT COMPLETED SUCCESSFULLY === >> "%LOG_FILE%"
echo.

pause
