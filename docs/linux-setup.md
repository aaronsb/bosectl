# Linux Installation & Setup Guide

This guide covers installing bosectl on Linux systems and configuring Bluetooth access.

## Quick Start

The easiest way to install bosectl on Linux is to use the automated installer:

```bash
git clone https://github.com/aaronsb/bosectl.git
cd bosectl
chmod +x linux_install.sh
./linux_install.sh
```

The installer will:
1. ✓ Detect your Linux distribution
2. ✓ Install BlueZ and Bluetooth development libraries
3. ✓ Set up a Python virtual environment
4. ✓ Install the pybmap library
5. ✓ Configure Bluetooth group permissions
6. ✓ Create a global `bosectl` command
7. ✓ Verify the installation

## Supported Distributions

| Distribution | Package Manager | BlueZ Package |
|--------------|-----------------|---------------|
| **Ubuntu / Debian** | apt | `libbluetooth-dev`, `bluez` |
| **Fedora / RHEL / CentOS** | dnf | `bluez-libs-devel`, `bluez` |
| **Arch / Manjaro** | pacman | `bluez`, `bluez-libs` |
| **openSUSE** | zypper | `bluez`, `bluez-devel` |
| **Alpine Linux** | apk | `bluez`, `bluez-dev` |

Other distributions can install BlueZ manually. See [Manual Installation](#manual-installation).

## Detailed Installation Steps

### Step 1: Clone the Repository

```bash
git clone https://github.com/aaronsb/bosectl.git
cd bosectl
```

### Step 2: Run the Installer

```bash
chmod +x linux_install.sh
./linux_install.sh
```

The installer requires `sudo` access for:
- Installing system packages (`apt`, `dnf`, `pacman`, `zypper`)
- Adding your user to the `bluetooth` group
- Creating a symlink in `/usr/local/bin/`

### Step 3: Activate Group Membership

After the installer completes, group membership changes require a new login session:

```bash
newgrp bluetooth
```

Or log out and log back in.

### Step 4: Pair Your Headphones

If your headphones aren't already paired:

```bash
bluetoothctl
[bluetooth]# scan on
# Wait for your device to appear
[bluetooth]# pair XX:XX:XX:XX:XX:XX  # Replace with your device's MAC
[bluetooth]# trust XX:XX:XX:XX:XX:XX
[bluetooth]# connect XX:XX:XX:XX:XX:XX
[bluetooth]# exit
```

### Step 5: Test the Installation

```bash
bosectl status
```

You should see your headphone's name, battery level, and current settings.

## Manual Installation

If the automated installer doesn't work for your system, you can install manually:

### 1. Install BlueZ

**Ubuntu / Debian:**
```bash
sudo apt-get update
sudo apt-get install -y bluez libbluetooth-dev python3-dev python3-venv python3-pip
```

**Fedora / RHEL / CentOS:**
```bash
sudo dnf install -y bluez bluez-libs-devel python3-devel python3-pip
```

**Arch / Manjaro:**
```bash
sudo pacman -Sy bluez bluez-libs python3 base-devel
```

**openSUSE:**
```bash
sudo zypper install -y bluez bluez-devel python3-devel python3-pip
```

### 2. Create Python Virtual Environment

```bash
python3 -m venv python/.venv
source python/.venv/bin/activate
pip install --quiet -e python
```

### 3. Configure Bluetooth Permissions

Add your user to the `bluetooth` group:

```bash
sudo usermod -a -G bluetooth $USER
newgrp bluetooth
```

You can verify the group membership with:
```bash
id -nG | grep bluetooth
```

### 4. Create Global Command

Create `/usr/local/bin/bosectl`:

```bash
#!/bin/bash
REPO_DIR="$(dirname "$(readlink -f "$0")")/path/to/bosectl"
VENV_DIR="$REPO_DIR/python/.venv"
source "$VENV_DIR/bin/activate"
exec "$VENV_DIR/bin/bosectl" "$@"
```

Replace `path/to/bosectl` with the actual path to your bosectl directory.

Then:
```bash
sudo chmod +x /usr/local/bin/bosectl
```

## Usage

### Basic Commands

```bash
# Show device status
bosectl status

# Get battery level
bosectl battery

# Show current noise cancellation mode
bosectl current

# Set noise cancellation level (0-10, where 0 = max ANC)
bosectl cnc 5

# Switch audio modes
bosectl quiet      # Full noise cancellation
bosectl aware      # Transparency / passthrough
bosectl immersion  # Spatial audio immersive
bosectl cinema     # Spatial audio cinema

# Set EQ (bass mid treble, range -10 to +10)
bosectl eq 2 0 -3

# Show all available commands
bosectl --help
```

### Environment Variables

You can override device detection with environment variables:

```bash
# Connect to a specific MAC address
BMAP_MAC=68:F2:1F:XX:XX:XX bosectl status

# Specify device type (for advanced debugging)
BMAP_DEVICE=qc_ultra2 bosectl status
```

## Troubleshooting

### ✗ "Permission denied" When Running bosectl

**Problem:** You get `Permission denied` or socket errors when running bosectl.

**Solution:**
1. Ensure you're in the `bluetooth` group:
   ```bash
   id -nG | grep bluetooth
   ```
2. If not present, add yourself:
   ```bash
   sudo usermod -a -G bluetooth $USER
   ```
3. Start a new login session:
   ```bash
   newgrp bluetooth
   ```
4. Or log out and log back in completely.

### ✗ "bluetoothctl: command not found"

**Problem:** The `bluetoothctl` command is not available.

**Solution:** BlueZ is not installed. Install it:

```bash
# Ubuntu / Debian
sudo apt-get install bluez

# Fedora / RHEL
sudo dnf install bluez

# Arch
sudo pacman -S bluez bluez-libs

# openSUSE
sudo zypper install bluez
```

### ✗ "Device not found" or "No response from device"

**Problem:** bosectl can't find or connect to your headphones.

**Solutions:**
1. Ensure headphones are powered on
2. Check if they're paired:
   ```bash
   bluetoothctl devices
   ```
3. Verify the device is connected:
   ```bash
   bluetoothctl info [MAC_ADDRESS]
   ```
4. If disconnected, reconnect:
   ```bash
   bluetoothctl connect [MAC_ADDRESS]
   ```
5. If still not working, re-pair the device:
   ```bash
   bluetoothctl remove [MAC_ADDRESS]
   bluetoothctl scan on
   # Wait for device to appear
   bluetoothctl pair [MAC_ADDRESS]
   bluetoothctl trust [MAC_ADDRESS]
   bluetoothctl connect [MAC_ADDRESS]
   ```

### ✗ "No such file or directory" in Virtual Environment

**Problem:** The virtual environment is broken or moved.

**Solution:** Recreate it:
```bash
rm -rf python/.venv
python3 -m venv python/.venv
source python/.venv/bin/activate
pip install -e python
```

### ✗ Python Socket Module Doesn't Support AF_BLUETOOTH

**Problem:** `socket.AF_BLUETOOTH` is not available on your system.

**Solution:** This usually indicates BlueZ headers weren't installed before Python was compiled. Ensure you have:
- `libbluetooth-dev` (Ubuntu/Debian) or equivalent
- `python3-dev` installed

Then reinstall the venv:
```bash
rm -rf python/.venv
python3 -m venv python/.venv
source python/.venv/bin/activate
pip install -e python
```

## Uninstallation

To remove bosectl:

```bash
# Remove global command
sudo rm /usr/local/bin/bosectl

# Remove the cloned repository
cd ..
rm -rf bosectl/
```

To remove BlueZ (if you don't need Bluetooth for anything else):

```bash
# Ubuntu / Debian
sudo apt-get remove bluez libbluetooth-dev

# Fedora / RHEL
sudo dnf remove bluez bluez-libs-devel

# Arch
sudo pacman -R bluez bluez-libs

# openSUSE
sudo zypper remove bluez bluez-devel
```

## Advanced Usage

### Using from Source Without Installation

If you prefer not to install globally:

```bash
cd /path/to/bosectl
source python/.venv/bin/activate
bosectl status
deactivate
```

Or create an alias:

```bash
alias bosectl='source /path/to/bosectl/python/.venv/bin/activate && bosectl'
```

### Using the Rust Binary

For better performance, you can build and use the Rust CLI instead:

```bash
cd /path/to/bosectl
make rust-build
sudo cp rust/target/release/bmapctl /usr/local/bin/bmapctl
```

The Rust binary requires the same Bluetooth setup but runs without Python overhead.

## Getting Help

- **GitHub Issues:** https://github.com/aaronsb/bosectl/issues
- **Documentation:** https://github.com/aaronsb/bosectl/blob/main/README.md
- **Architecture Guide:** https://github.com/aaronsb/bosectl/blob/main/docs/architecture.md

## Related Resources

- [BlueZ Documentation](http://www.bluez.org/)
- [Linux Bluetooth HOWTO](https://tldp.org/HOWTO/Bluetooth-HOWTO/)
- [BMAP Protocol Reference](NOTES.md)

