#!/bin/bash
# bosectl Linux Installer
#
# pybmap uses only the Python standard library on Linux, so there is
# nothing to pip install: this checks the prerequisites and symlinks the
# repo's bosectl script onto PATH.

set -e
cd "$(dirname "$0")"

echo "=== bosectl Linux Installer ==="
echo ""

# 1. Python with Bluetooth socket support
if ! command -v python3 >/dev/null; then
    echo "python3 not found. Install Python 3 with your package manager first."
    exit 1
fi
if ! python3 -c 'import socket; socket.AF_BLUETOOTH; socket.BTPROTO_RFCOMM' 2>/dev/null; then
    echo "This python3 was built without Bluetooth socket support (AF_BLUETOOTH)."
    echo "Use your distribution's python3 package rather than a custom build."
    exit 1
fi

# 2. BlueZ, for pairing
if ! command -v bluetoothctl >/dev/null; then
    echo "Warning: bluetoothctl not found. Install BlueZ (package 'bluez') to pair headphones."
fi

# 3. Make bosectl script executable
echo "Configuring executable permissions..."
chmod +x bosectl

# 4. Create symlink in /usr/local/bin
echo ""
echo "To make 'bosectl' accessible from anywhere on your system,"
echo "we will create a symlink in /usr/local/bin/bosectl."
echo "This requires administrator privileges."
echo ""

if sudo ln -sf "$(pwd)/bosectl" /usr/local/bin/bosectl; then
    echo ""
    echo "=== Installation Successful! ==="
    echo "Pair your headphones with bluetoothctl, then run 'bosectl status'."
else
    echo ""
    echo "=== Symlink Failed ==="
    echo "Could not create symlink in /usr/local/bin."
    echo "You can still run it locally using: $(pwd)/bosectl"
fi
