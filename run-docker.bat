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
REM But first, check if Tailscale is installed; if not, install it automatically
where tailscale >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
	echo.
	echo ⚠️  Tailscale not found. Attempting to install...
	echo Verificando winget...
	where winget >nul 2>&1
	if %ERRORLEVEL% NEQ 0 (
		echo ❌ Error: winget no encontrado. Necesitas Windows 11+ o instalar winget manualmente.
		echo Descarga desde: https://learn.microsoft.com/en-us/windows/package-manager/winget/
		pause
		exit /b 1
	)
	echo Instalando Tailscale con winget...
	winget install Tailscale.Tailscale -e --silent
	if %ERRORLEVEL% NEQ 0 (
		echo ⚠️  Error instalando Tailscale con winget. Continuando de todas formas...
	) else (
		echo ✅ Tailscale instalado correctamente
		timeout /t 3 /nobreak >nul
	)
) else (
	echo ✅ Tailscale ya está instalado
)

REM Conectar Tailscale con auth-key automáticamente CON REINTENTOS
echo.
echo 🔐 Conectando Tailscale con credenciales...
if "!TAILSCALE_AUTHKEY!" neq "" (
	echo Usando TAILSCALE_AUTHKEY del .env
	
	REM Intentar hasta 3 veces
	set RETRY_COUNT=0
	:tailscale_retry
	tailscale logout --accept-risk=lose-ssh-access >nul 2>&1
	timeout /t 2 /nobreak >nul
	
	tailscale up --authkey=!TAILSCALE_AUTHKEY! --accept-routes --accept-dns --quiet
	if %ERRORLEVEL% EQU 0 (
		echo ✅ Tailscale conectado exitosamente
		goto tailscale_done
	) else (
		set /a RETRY_COUNT=!RETRY_COUNT!+1
		if !RETRY_COUNT! LSS 3 (
			echo ⚠️  Intento !RETRY_COUNT!/3 fallido, reintentando...
			timeout /t 3 /nobreak >nul
			goto tailscale_retry
		) else (
			echo ❌ Error: No se pudo conectar a Tailscale después de 3 intentos
			echo    Verifica que tu TAILSCALE_AUTHKEY sea válido
			echo    Para generar uno nuevo: https://login.tailscale.com/admin/settings/keys
		)
	)
	:tailscale_done
	timeout /t 2 /nobreak >nul
) else (
	echo ❌ TAILSCALE_AUTHKEY no está definida en .env
	echo    Asegúrate de configurar .env correctamente
	pause
	exit /b 1
)

REM Generate tailscale_status.json from the host
echo Generando tailscale_status.json...
tailscale status --json > "templates\quic-file-transfer\app\tailscale_status.json" 2> "templates\quic-file-transfer\app\tailscale_status.err"
if %ERRORLEVEL% EQU 0 (
	echo ✅ Status JSON generado correctamente
) else (
	echo ⚠️  Error generando JSON (ver .err file)
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

REM Iniciar los monitores del HOST
echo.
echo 🔄 Iniciando monitor de Tailscale (reconexión automática)...
start "Tailscale Monitor" /min python3 "%~dp0tailscale-monitor.py"
timeout /t 2 /nobreak >nul
echo ✓ Monitor de Tailscale activo
echo.

echo 🔌 Iniciando servicio API de Tailscale (puerto 5001)...
start "Tailscale API" /min python3 "%~dp0tailscale-api.py"
timeout /t 2 /nobreak >nul
echo ✓ Servicio API activo
echo.

echo 📢 Iniciando monitor de alertas .msg...
start "Monitor de Alertas" /min python3 "%~dp0msg-monitor.py"
timeout /t 2 /nobreak >nul
echo ✓ Monitor de alertas activo
echo.

echo 🎬 Iniciando monitor de videos...
start "Monitor de Videos" /min python3 "%~dp0video-monitor.py"
timeout /t 2 /nobreak >nul
echo ✓ Monitor de videos activo
echo.

echo Done! Opening http://localhost:8080 in your browser (if available)...
echo.
start http://localhost:8080

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
