#!/bin/bash
# bosectl Linux Installer
# Installs bosectl with all dependencies and configures Bluetooth access

set -e
cd "$(dirname "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           bosectl Linux Installer (v0.4.0)                 ║"
    echo "║      Control Bose headphones from Linux via Bluetooth      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

install_bluez_dependencies() {
    local distro="$1"
    
    log_info "Detecting Linux distribution..."
    
    case "$distro" in
        ubuntu|debian)
            log_info "Debian/Ubuntu detected. Installing BlueZ dependencies..."
            if ! sudo apt-get update; then
                log_error "Failed to update package list"
                return 1
            fi
            if ! sudo apt-get install -y libbluetooth-dev bluez python3-dev python3-venv python3-pip; then
                log_error "Failed to install BlueZ dependencies"
                return 1
            fi
            log_success "BlueZ dependencies installed"
            ;;
        fedora|rhel|centos)
            log_info "Fedora/RHEL/CentOS detected. Installing BlueZ dependencies..."
            if ! sudo dnf install -y bluez-libs-devel bluez python3-devel python3-pip; then
                log_error "Failed to install BlueZ dependencies"
                return 1
            fi
            log_success "BlueZ dependencies installed"
            ;;
        arch|manjaro)
            log_info "Arch/Manjaro detected. Installing BlueZ dependencies..."
            if ! sudo pacman -Sy bluez bluez-libs python3 base-devel; then
                log_error "Failed to install BlueZ dependencies"
                return 1
            fi
            log_success "BlueZ dependencies installed"
            ;;
        opensuse*)
            log_info "openSUSE detected. Installing BlueZ dependencies..."
            if ! sudo zypper install -y bluez bluez-devel python3-devel python3-pip; then
                log_error "Failed to install BlueZ dependencies"
                return 1
            fi
            log_success "BlueZ dependencies installed"
            ;;
        *)
            log_warn "Unknown distribution: $distro"
            log_warn "Please install the following packages manually:"
            log_warn "  - libbluetooth-dev (or bluez-libs-devel / bluez-devel)"
            log_warn "  - bluez"
            log_warn "  - python3 (>= 3.6) with dev headers"
            log_warn "  - python3-venv and python3-pip"
            return 0
            ;;
    esac
}

setup_python_venv() {
    log_info "Setting up Python virtual environment..."
    
    if [ -d "python/.venv" ]; then
        log_warn "Virtual environment already exists. Skipping creation."
    else
        python3 -m venv python/.venv || {
            log_error "Failed to create virtual environment"
            return 1
        }
        log_success "Virtual environment created"
    fi
    
    # Activate venv and install pybmap
    source python/.venv/bin/activate
    
    log_info "Installing pybmap package..."
    pip install --quiet --upgrade pip || {
        log_error "Failed to upgrade pip"
        return 1
    }
    pip install --quiet -e python || {
        log_error "Failed to install pybmap"
        return 1
    }
    log_success "pybmap installed successfully"
    
    deactivate
}

create_wrapper_script() {
    log_info "Creating wrapper script for global bosectl command..."
    
    local venv_path="$(cd "$(pwd)/python/.venv" && pwd)"
    local repo_path="$(pwd)"
    
    cat > /tmp/bosectl_wrapper << 'EOF'
#!/bin/bash
# bosectl wrapper — activates venv and runs bosectl
REPO_DIR="@REPO_PATH@"
VENV_DIR="@VENV_PATH@"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Python virtual environment not found at $VENV_DIR" >&2
    exit 1
fi

# Activate venv and run bosectl
source "$VENV_DIR/bin/activate"
exec "$VENV_DIR/bin/bosectl" "$@"
EOF
    
    sed "s|@REPO_PATH@|$repo_path|g; s|@VENV_PATH@|$venv_path|g" /tmp/bosectl_wrapper > /tmp/bosectl_wrapper.tmp
    mv /tmp/bosectl_wrapper.tmp /tmp/bosectl_wrapper
    
    chmod +x /tmp/bosectl_wrapper
    log_success "Wrapper script created"
}

setup_bluetooth_group() {
    log_info "Configuring Bluetooth permissions..."
    
    # Check if current user is in bluetooth group
    if id -nG "$USER" | grep -qw "bluetooth"; then
        log_success "User is already in 'bluetooth' group"
        return 0
    fi
    
    # Try to add user to bluetooth group
    if ! getent group bluetooth > /dev/null 2>&1; then
        log_warn "Bluetooth group does not exist. Attempting to create it..."
        if ! sudo groupadd bluetooth 2>/dev/null; then
            log_error "Failed to create bluetooth group"
            log_warn "You may need to run bosectl with 'sudo'"
            return 0
        fi
    fi
    
    log_info "Adding $USER to 'bluetooth' group..."
    if ! sudo usermod -a -G bluetooth "$USER"; then
        log_error "Failed to add user to bluetooth group"
        log_warn "You may need to run bosectl with 'sudo', or manually run:"
        log_warn "  sudo usermod -a -G bluetooth $USER"
        return 0
    fi
    
    log_success "User added to bluetooth group"
    log_warn "⚠️  You may need to log out and log back in for group changes to take effect"
    log_warn "    Or run: newgrp bluetooth"
}

install_to_system() {
    log_info "Installing bosectl to system..."
    
    create_wrapper_script
    
    echo ""
    echo "Attempting to create symlink in /usr/local/bin/bosectl..."
    echo "This requires administrator privileges."
    echo ""
    
    if sudo cp /tmp/bosectl_wrapper /usr/local/bin/bosectl; then
        log_success "bosectl installed to /usr/local/bin/bosectl"
        return 0
    else
        log_error "Failed to install bosectl to /usr/local/bin"
        log_warn "You can still run it locally using: python/.venv/bin/bosectl"
        rm -f /tmp/bosectl_wrapper
        return 0
    fi
}

verify_installation() {
    log_info "Verifying installation..."
    
    # Test that Python dependencies are present
    source python/.venv/bin/activate
    
    if python3 -c "import pybmap; print('pybmap version:', pybmap.__version__)" 2>/dev/null; then
        log_success "Python pybmap library verified"
    else
        log_error "Failed to verify pybmap installation"
        deactivate
        return 1
    fi
    
    if python3 -c "import socket; socket.AF_BLUETOOTH" 2>/dev/null; then
        log_success "Bluetooth socket support verified"
    else
        log_warn "Bluetooth socket support not detected (this may be expected on non-Linux)"
    fi
    
    deactivate
    
    # Test that bosectl command works
    if command -v bosectl &> /dev/null; then
        log_success "bosectl command is available globally"
        echo ""
        echo "Quick test:"
        echo "  bosectl status    # Show device status (requires paired headphones)"
        echo "  bosectl --help    # Show all available commands"
    elif [ -x "python/.venv/bin/bosectl" ]; then
        log_success "bosectl is available in virtual environment"
        echo ""
        echo "To use it, run:"
        echo "  source python/.venv/bin/activate"
        echo "  bosectl status"
    fi
}

print_next_steps() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                 Next Steps                                  ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    if ! id -nG "$USER" | grep -qw "bluetooth" &>/dev/null; then
        echo "1. Apply group membership changes:"
        echo "   ${BLUE}newgrp bluetooth${NC}"
        echo "   (or log out and log back in)"
        echo ""
    fi
    
    echo "2. Pair your Bose headphones (if not already paired):"
    echo "   ${BLUE}bluetoothctl${NC}"
    echo "   > scan on"
    echo "   > pair XX:XX:XX:XX:XX:XX"
    echo "   > trust XX:XX:XX:XX:XX:XX"
    echo "   > connect XX:XX:XX:XX:XX:XX"
    echo "   > exit"
    echo ""
    
    echo "3. Test bosectl:"
    echo "   ${BLUE}bosectl status${NC}       # Show headphone status"
    echo "   ${BLUE}bosectl cnc 5${NC}        # Set noise cancellation to level 5"
    echo "   ${BLUE}bosectl --help${NC}       # Show all commands"
    echo ""
    
    echo "Documentation:"
    echo "   ${BLUE}https://github.com/aaronsb/bosectl${NC}"
    echo ""
}

print_troubleshooting() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                 Troubleshooting                             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "✗ \"Permission denied\" error:"
    echo "  • Make sure your user is in the 'bluetooth' group"
    echo "  • Run: ${BLUE}id -nG | grep bluetooth${NC}"
    echo "  • If missing, run: ${BLUE}sudo usermod -a -G bluetooth \$USER${NC}"
    echo "  • Then log out and back in (or: ${BLUE}newgrp bluetooth${NC})"
    echo ""
    
    echo "✗ \"bluetoothctl: command not found\":"
    echo "  • BlueZ is not installed. Re-run this script or install:"
    echo "  • Debian/Ubuntu: ${BLUE}sudo apt-get install bluez${NC}"
    echo "  • Fedora/RHEL: ${BLUE}sudo dnf install bluez${NC}"
    echo "  • Arch: ${BLUE}sudo pacman -S bluez bluez-libs${NC}"
    echo ""
    
    echo "✗ \"No response from device\":"
    echo "  • Ensure headphones are paired and connected"
    echo "  • Check: ${BLUE}bluetoothctl info [MAC_ADDRESS]${NC}"
    echo "  • Re-pair if necessary"
    echo ""
}

main() {
    print_header
    
    # Detect distro
    DISTRO=$(detect_distro)
    log_success "Detected: $DISTRO"
    echo ""
    
    # Install BlueZ dependencies
    if ! install_bluez_dependencies "$DISTRO"; then
        log_error "Installation failed during dependency installation"
        exit 1
    fi
    echo ""
    
    # Setup Python venv
    if ! setup_python_venv; then
        log_error "Installation failed during Python setup"
        exit 1
    fi
    echo ""
    
    # Setup Bluetooth permissions
    setup_bluetooth_group
    echo ""
    
    # Install to system
    if ! install_to_system; then
        log_warn "Could not install globally, but local installation is available"
    fi
    echo ""
    
    # Verify
    if ! verify_installation; then
        log_error "Installation verification failed"
        exit 1
    fi
    echo ""
    
    # Print next steps
    print_next_steps
    print_troubleshooting
    
    echo "=== Installation Complete ==="
    echo ""
}

# Run main
main
