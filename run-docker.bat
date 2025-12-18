@echo off
REM Double-click to build and run the quic-file-transfer service via docker-compose
cd /d "%~dp0templates\quic-file-transfer"

echo Checking Docker availability...
@echo off
if errorlevel 1 (
)

REM Set the Tailscale auth values here (provided by user). You can edit these or replace with prompts.
set TAILSCALE_AUTHKEY=tskey-auth-ktsHxZY1qZ11CNTRL-XSjjc4JNpEL9jnuB4nWGFLSV3ouK6xrR
set TAILSCALE_API_KEY=tskey-api-kHbb2N391v11CNTRL-zshXmfRoGn1G8s3YSs32o1r4gzopSSHC
set TAILNET=nash2207@hotmail.com

REM Export variables for docker-compose interpolation (Windows): compose uses environment variables from the shell session.
REM No extra action required beyond 'set' when calling docker-compose from this batch script.

REM Attempt to generate tailscale_status.json from the host if tailscale CLI is available.
where tailscale >nul 2>&1
if %ERRORLEVEL% EQU 0 (
	echo Found tailscale CLI on host — generating status JSON for container to read.
	REM We already cd'ed into the templates\quic-file-transfer directory above, so write to the local app folder.
	tailscale status --json > ".\app\tailscale_status.json" 2> ".\app\tailscale_status.err" || (
		echo "tailscale status failed; see .\app\tailscale_status.err"
	)
) else (
	echo "tailscale CLI not found on host — skipping host status generation"
)

echo Using TAILSCALE_AUTHKEY=%TAILSCALE_AUTHKEY%

echo Building and starting containers (this may take a few minutes)...
docker-compose up --build --force-recreate -d

if %ERRORLEVEL% NEQ 0 (
	echo docker-compose failed with error %ERRORLEVEL%
	pause
	exit /b %ERRORLEVEL%
)

echo Waiting a few seconds for services to start...
timeout /t 3 /nobreak >nul

echo Opening http://localhost:5000 in your default browser (may not work on Docker with host networking on Linux); if it fails, check docker logs.
start http://localhost:5000

echo Done.
