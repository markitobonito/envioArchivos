#!/bin/bash
# get-downloads-path.sh
# Detecta la carpeta de descargas correcta (Descargas o Downloads) según el idioma del SO

HOME_DIR="${HOME:=$( cd ~ && pwd )}"

# Intentar Descargas primero (español)
if [ -d "$HOME_DIR/Descargas" ]; then
    echo "$HOME_DIR/Descargas"
    exit 0
fi

# Fallback a Downloads (inglés)
echo "$HOME_DIR/Downloads"
