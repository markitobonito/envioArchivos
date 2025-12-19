@echo off
REM Script que monitorea la carpeta de descargas y abre videos automáticamente
REM Ejecutar en el HOST (no en el contenedor)

setlocal enabledelayedexpansion

REM Detectar carpeta de descargas
if exist "%USERPROFILE%\Descargas" (
    set "DOWNLOADS_DIR=%USERPROFILE%\Descargas"
) else (
    set "DOWNLOADS_DIR=%USERPROFILE%\Downloads"
)

echo Monitoreando carpeta: !DOWNLOADS_DIR!
echo Esperando videos nuevos...
echo.
echo Presiona Ctrl+C para detener
echo.

REM Crear archivo temporal para guardar videos vistos
set "SEEN_FILE=%TEMP%\video-monitor-seen.txt"

REM Cargar videos existentes
if exist "!SEEN_FILE!" (
    del "!SEEN_FILE!"
)

for %%F in ("!DOWNLOADS_DIR!\*.mp4" "!DOWNLOADS_DIR!\*.webm" "!DOWNLOADS_DIR!\*.mkv" "!DOWNLOADS_DIR!\*.avi" "!DOWNLOADS_DIR!\*.mov" "!DOWNLOADS_DIR!\*.flv" "!DOWNLOADS_DIR!\*.m4v") do (
    echo %%~nxF >> "!SEEN_FILE!"
)

REM Monitorear cambios
:loop
for %%F in ("!DOWNLOADS_DIR!\*.mp4" "!DOWNLOADS_DIR!\*.webm" "!DOWNLOADS_DIR!\*.mkv" "!DOWNLOADS_DIR!\*.avi" "!DOWNLOADS_DIR!\*.mov" "!DOWNLOADS_DIR!\*.flv" "!DOWNLOADS_DIR!\*.m4v") do (
    set "filename=%%~nxF"
    
    REM Buscar en archivo de videos vistos
    findstr /M "^!filename!$" "!SEEN_FILE!" >nul 2>&1
    
    if errorlevel 1 (
        REM Video nuevo detectado
        echo.
        echo Abriendo video en pantalla completa: !filename!
        echo %%~nxF >> "!SEEN_FILE!"
        
        REM Esperar a que termine de escribirse
        timeout /t 1 /nobreak >nul
        
        REM Intentar abrir con reproductor predeterminado
        start "" "%%F"
    )
)

timeout /t 2 /nobreak >nul
goto loop
