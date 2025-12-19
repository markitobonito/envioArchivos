@echo off
REM Double-click to build and run the quic-file-transfer service via docker compose
REM On Windows with Docker Desktop, this will handle both UDP (QUIC) and TCP ports.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo Checking Docker availability...
where docker >nul 2>&1
if errorlevel 1 (
	echo Error: Docker is not installed or not in PATH.
	echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
	pause
	exit /b 1
)

REM Try to determine which docker-compose command to use (new: docker compose, old: docker-compose)
docker compose version >nul 2>&1
if errorlevel 1 (
	docker-compose --version >nul 2>&1
	if errorlevel 1 (
		echo Error: neither 'docker compose' nor 'docker-compose' found
		echo Please install Docker Compose from https://docs.docker.com/compose/install/
		pause
		exit /b 1
	)
	set COMPOSE_CMD=docker-compose
) else (
	set COMPOSE_CMD=docker compose
)

echo Using: %COMPOSE_CMD%

REM Load credentials from .env file if it exists; otherwise use defaults
if exist "templates\quic-file-transfer\.env" (
	echo Loading credentials from templates\quic-file-transfer\.env
	for /f "usebackq tokens=* delims=" %%a in ("templates\quic-file-transfer\.env") do (
		if not "%%a"=="" if not "%%a:~0,1%"=="#" (
			set "%%a"
		)
	)
) else (
	echo Warning: templates\quic-file-transfer\.env not found; using fallback values.
	REM These are just defaults (ideally you use the .env file)
	set TAILSCALE_AUTHKEY=
	set TAILSCALE_API_KEY=
	set TAILNET=
	set FLASK_ENV=production
)

REM Detect Downloads folder path (Windows systems)
REM First try common localized folders, then fallback to default
if exist "%USERPROFILE%\Descargas" (
	set DOWNLOADS_PATH=%USERPROFILE%\Descargas
	echo Detected Spanish Downloads folder: !DOWNLOADS_PATH!
) else if exist "%USERPROFILE%\Downloads" (
	set DOWNLOADS_PATH=%USERPROFILE%\Downloads
	echo Using English Downloads folder: !DOWNLOADS_PATH!
) else (
	set DOWNLOADS_PATH=%USERPROFILE%\Downloads
	mkdir "!DOWNLOADS_PATH!" 2>nul
	echo Created Downloads folder: !DOWNLOADS_PATH!
)

REM Attempt to generate tailscale_status.json from the host if tailscale CLI is available
where tailscale >nul 2>&1
if %ERRORLEVEL% EQU 0 (
	echo Found tailscale CLI on host — generating status JSON for container to read.
	tailscale status --json > "templates\quic-file-transfer\app\tailscale_status.json" 2> "templates\quic-file-transfer\app\tailscale_status.err"
	if %ERRORLEVEL% NEQ 0 (
		echo WARNING: tailscale status command failed; see templates\quic-file-transfer\app\tailscale_status.err
	) else (
		echo Wrote tailscale status to templates\quic-file-transfer\app\tailscale_status.json
	)
) else (
	echo tailscale CLI not found on host — container will attempt to use Tailscale if available inside container
)

echo.
echo Building and starting containers with %COMPOSE_CMD% (this may take a few minutes)...
echo.

%COMPOSE_CMD% -f templates\quic-file-transfer\docker-compose.yml --env-file templates\quic-file-transfer\.env -e DOWNLOADS_PATH=%DOWNLOADS_PATH% up --build --force-recreate -d

if %ERRORLEVEL% NEQ 0 (
	echo Error: %COMPOSE_CMD% failed with exit code %ERRORLEVEL%
	echo For more details, run: %COMPOSE_CMD% -f templates\quic-file-transfer\docker-compose.yml logs
	pause
	exit /b %ERRORLEVEL%
)

echo.
echo Waiting a few seconds for services to initialize...
timeout /t 3 /nobreak >nul

echo.
echo 🎬 Iniciando monitor de videos automático...
start "" python3 "%~dp0video-monitor.py"
timeout /t 2 /nobreak >nul
echo ✓ Monitor de videos activo
echo   - Reproducir Ahora: abre inmediatamente
echo   - Programar: abre solo a la hora exacta
echo   - Solo Descargar: sin reproducción automática
echo.

echo 📢 Iniciando monitor de notificaciones...
start "" python3 "%~dp0templates\quic-file-transfer\app\notification-monitor.py"
timeout /t 2 /nobreak >nul
echo ✓ Monitor de notificaciones activo
echo.

echo Done! Opening http://localhost:5000 in your browser (if available)...
echo.
start http://localhost:5000

echo.
echo ✅ Sistema listo. Los videos se abrirán automáticamente en pantalla completa
echo 📢 Las alertas se mostrarán con sonido y voz automáticamente
echo.
echo To view live logs, run:
echo   %COMPOSE_CMD% -f templates\quic-file-transfer\docker-compose.yml logs -f
echo.
echo To stop the containers, run:
echo   %COMPOSE_CMD% -f templates\quic-file-transfer\docker-compose.yml down
echo.
