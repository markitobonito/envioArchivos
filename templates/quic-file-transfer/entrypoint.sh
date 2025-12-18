#!/bin/sh
set -e

# Entrypoint: try multiple ways to get tailscale status available to the app.
# 1) If TAILSCALE_STATUS_PATH file exists, keep it (it will be read by the app).
# 2) If TAILSCALE_AUTHKEY env is provided, start tailscaled and run `tailscale up`.
# 3) If /var/run/tailscale exists (host socket mounted), rely on host daemon.
# Finally, generate /app/tailscale_status.json if possible, then exec the app.

STATUS_PATH=${TAILSCALE_STATUS_PATH:-/app/tailscale_status.json}

# helper to write status.json if tailscale available
write_status() {
  if command -v tailscale >/dev/null 2>&1; then
    echo "Attempting to write tailscale status to $STATUS_PATH"
    if tailscale status --json > "$STATUS_PATH" 2>/tmp/tailscale.err; then
      echo "Wrote tailscale status"
      return 0
    else
      echo "tailscale status failed, see /tmp/tailscale.err"
      cat /tmp/tailscale.err || true
      return 1
    fi
  fi
  return 1
}

# 1) if file already exists, keep it
if [ -f "$STATUS_PATH" ]; then
  echo "Status file $STATUS_PATH already present, skipping generation"
else
  # 3) if host socket mounted (common when /var/run/tailscale is mounted)
  if [ -d "/var/run/tailscale" ] || [ -d "/var/lib/tailscale" ]; then
    echo "Detected host tailscale state mount; attempting to use tailscale client"
    write_status || echo "Could not write status from mounted daemon"
  fi

  # 2) If authkey provided, try to start tailscaled and bring interface up
  if [ -n "$TAILSCALE_AUTHKEY" ]; then
    echo "TAILSCALE_AUTHKEY provided — starting tailscaled and running 'tailscale up'"
    # ensure state dir exists
    mkdir -p /var/lib/tailscale
    # start tailscaled in background
    tailscaled --state=/var/lib/tailscale/tailscaled.state >/var/log/tailscaled.log 2>&1 &
    TSD_PID=$!
    echo "tailscaled pid=$TSD_PID"
    # wait a bit
    sleep 2
    # run tailscale up
    if tailscale up --authkey="$TAILSCALE_AUTHKEY" --accept-routes --accept-dns 2>/tmp/tailscale.up.err; then
      echo "tailscale up succeeded"
      write_status || echo "Could not write status after 'tailscale up'"
    else
      echo "tailscale up failed; see /tmp/tailscale.up.err"
      cat /tmp/tailscale.up.err || true
    fi
  fi
fi

# final: show status file content for debug
if [ -f "$STATUS_PATH" ]; then
  echo "--- tailscale_status.json (start) ---"
  cat "$STATUS_PATH" || true
  echo "--- tailscale_status.json (end) ---"
else
  echo "No tailscale status available inside container"
fi

# Exec the original command (run.py)
exec python3 /run.py
