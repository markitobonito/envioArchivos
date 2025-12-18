#!/usr/bin/env bash
# Manual file send test script
# Usage: ./send-test-file.sh <filename>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <file_to_send>"
    echo "Example: $0 /path/to/myfile.zip"
    exit 1
fi

FILE_PATH="$1"
if [ ! -f "$FILE_PATH" ]; then
    echo "Error: File not found: $FILE_PATH"
    exit 1
fi

FILE_NAME=$(basename "$FILE_PATH")
UPLOAD_DIR="templates/quic-file-transfer/app/uploads"

# Copy file to uploads
mkdir -p "$UPLOAD_DIR"
cp "$FILE_PATH" "$UPLOAD_DIR/$FILE_NAME"

echo "[*] Copied '$FILE_NAME' to $UPLOAD_DIR"
echo "[*] Simulating form submission to http://localhost:5000"
echo ""

# Send via curl to Flask
curl -X POST -F "file=@$UPLOAD_DIR/$FILE_NAME" http://localhost:5000/

echo ""
echo "[✓] File sent! Check container logs: docker logs quic-file-transfer-quic-file-transfer-1"
