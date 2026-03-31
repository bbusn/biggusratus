#!/usr/bin/env python3

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path

APP_NAME = "biggusratus-server"
ENTRY = "server/server.py"

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
# Clean previous binary
# -----------------------------
print("Cleaning previous binary...")

binary_path = Path("dist") / (APP_NAME + EXT)
if binary_path.exists():
    print(f"Deleting existing binary: {binary_path}")
    binary_path.unlink()
else:
    print("No previous binary found, skipping.")

# Remove .spec files
for file in Path(".").glob("*.spec"):
    file.unlink()

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
    "--hidden-import=common",
    "--hidden-import=common.constants",
    "--hidden-import=server",
    "--hidden-import=server.core",
    "--hidden-import=server.output",
    "--hidden-import=server.web",
    "--hidden-import=cryptography",
    "--hidden-import=json",
    "--hidden-import=base64",
    "--hidden-import=uuid",
    "--hidden-import=datetime",
    "--hidden-import=time",
    "--hidden-import=threading",
    "--hidden-import=queue",
    "--hidden-import=select",
    "--hidden-import=socket",
    "--hidden-import=sys",
    "--hidden-import=logging",
    "--hidden-import=logging.handlers",
    "--hidden-import=logging.config",
    "--hidden-import=argparse",
    "--hidden-import=signal",
    "--hidden-import=http.server",
    "--hidden-import=socketserver",
    "--collect-data", "server"
]

cmd = ["poetry", "run", "pyinstaller"] + pyinstaller_args

result = subprocess.run(cmd)
if result.returncode != 0:
    print("❌ Build failed")
    sys.exit(1)

print("✅ Build complete!")

# -----------------------------
# Check output
# -----------------------------
output = os.path.join("dist", APP_NAME + EXT)

if os.path.exists(output):
    size = os.path.getsize(output) / (1024 * 1024)
    print(f"Executable available at: {output}")
    print(f"Size: {size:.2f} MB")
else:
    print("⚠️ Build finished but executable not found")
    sys.exit(1)