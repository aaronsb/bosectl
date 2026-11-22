#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HOME/.local/share/applications"
sed "s|@APP_DIR@|$HERE|g" "$HERE/bose-control.desktop.in" > "$HOME/.local/share/applications/bose-control.desktop"
chmod +x "$HOME/.local/share/applications/bose-control.desktop"
echo "Bose Control se ha añadido al menú de aplicaciones."
