#!/usr/bin/env bash

set -e

APP_NAME="biggusratus-server"
ENTRY="server/server.py"

echo "Detecting OS..."
OS="$(uname -s)"

case "$OS" in
    Linux*)
        PLATFORM="linux"
        EXT=""
        ;;
    Darwin*)
        PLATFORM="macos"
        EXT=""
        ;;
    CYGWIN*|MINGW*|MSYS*)
        PLATFORM="windows"
        EXT=".exe"
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac

echo "OS detected: $PLATFORM"

echo "Cleaning previous builds..."
rm -rf build dist/${APP_NAME} *.spec

echo "Building executable..."

poetry run pyinstaller "$ENTRY" \
    --name "$APP_NAME" \
    --onefile \
    --clean \
    --noconfirm \
    --hidden-import=common \
    --hidden-import=common.constants \
    --hidden-import=server \
    --hidden-import=server.core \
    --hidden-import=server.output \
    --hidden-import=server.web \
    --hidden-import=cryptography \
    --hidden-import=json \
    --hidden-import=base64 \
    --hidden-import=uuid \
    --hidden-import=datetime \
    --hidden-import=time \
    --hidden-import=threading \
    --hidden-import=queue \
    --hidden-import=select \
    --hidden-import=socket \
    --hidden-import=sys \
    --hidden-import=logging \
    --hidden-import=logging.handlers \
    --hidden-import=logging.config \
    --hidden-import=argparse \
    --hidden-import=signal \
    --hidden-import=http.server \
    --hidden-import=socketserver \
    --collect-data server

echo "✅ Build complete!"

OUTPUT="dist/${APP_NAME}${EXT}"

if [ -f "$OUTPUT" ]; then
    echo "Executable available at: $OUTPUT"
else
    echo "⚠️ Build finished but executable not found"
fi
