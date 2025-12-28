@echo off
REM Inicia los monitores de HOST (Tailscale API, Alertas, Videos) en Windows
REM Este script se ejecuta automáticamente desde run-docker.bat

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Crear carpeta para logs si no existe
if not exist "%TEMP%\prr-logs" mkdir "%TEMP%\prr-logs"

echo.
echo ╔════════════════════════════════════════════╗
echo ║      Iniciando Monitores de HOST           ║
echo ╚════════════════════════════════════════════╝
echo.

REM Matar procesos anteriores si existen
echo Limpiando procesos anteriores...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *tailscale-api*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *msg-monitor*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *video-monitor*" 2>nul

timeout /t 2 /nobreak >nul

REM 1. Iniciar servicio API de Tailscale en background (sin ventana visible)
echo 🔌 Iniciando servicio API de Tailscale (puerto 5001)...
start "Tailscale API (5001)" /min python3 "%~dp0tailscale-api.py" 1>>"%TEMP%\prr-logs\tailscale-api.log" 2>&1
timeout /t 2 /nobreak >nul
echo    ✓ Servicio API activo en puerto 5001
echo    Logs: %TEMP%\prr-logs\tailscale-api.log
echo.

REM 2. Iniciar monitor de alertas .msg
echo 📢 Iniciando monitor de alertas .msg...
start "Monitor de Alertas MSG" /min python3 "%~dp0msg-monitor.py" 1>>"%TEMP%\prr-logs\msg-monitor.log" 2>&1
timeout /t 2 /nobreak >nul
echo    ✓ Monitor de alertas activo
echo    Logs: %TEMP%\prr-logs\msg-monitor.log
echo.

REM 3. Iniciar monitor de videos
echo 🎬 Iniciando monitor de videos automático...
start "Monitor de Videos" /min python3 "%~dp0video-monitor.py" 1>>"%TEMP%\prr-logs\video-monitor.log" 2>&1
timeout /t 2 /nobreak >nul
echo    ✓ Monitor de videos activo
echo    Logs: %TEMP%\prr-logs\video-monitor.log
echo    - Reproducir Ahora: abre inmediatamente
echo    - Programar: abre solo a la hora exacta
echo    - Solo Descargar: sin reproducción automática
echo.

echo ╔════════════════════════════════════════════╗
echo ║  ✅ Todos los monitores iniciados          ║
echo ║  📍 App Web: http://localhost:8080         ║
echo ║  🔌 API: http://localhost:5001/peers       ║
echo ╚════════════════════════════════════════════╝
echo.

timeout /t 3 /nobreak >nul
