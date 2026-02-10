#!/bin/bash
# Montana Presence — One-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/efir369999/montana-presence/main/install.sh | bash
set -e

echo ""
echo "  Montana Presence — Proof of Presence"
echo "  Earn Ɉ time coins while on camera"
echo ""

# Check macOS version
SW_VER=$(sw_vers -productVersion | cut -d. -f1)
if [ "$SW_VER" -lt 14 ]; then
    echo "Error: macOS 14 (Sonoma) or later required."
    exit 1
fi

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo "Error: Apple Silicon (M1/M2/M3/M4) required."
    exit 1
fi

TMPDIR=$(mktemp -d)
APP_NAME="MontanaPresence.app"
INSTALL_DIR="/Applications"

echo "[1/3] Downloading..."
curl -fsSL "https://github.com/efir369999/montana-presence/releases/latest/download/MontanaPresence.zip" -o "$TMPDIR/MontanaPresence.zip"

echo "[2/3] Installing..."
cd "$TMPDIR"
unzip -q MontanaPresence.zip

# Remove quarantine
xattr -cr "$APP_NAME" 2>/dev/null || true

# Remove Gatekeeper quarantine from inside the app too
xattr -cr "$APP_NAME" 2>/dev/null || true

# Copy to Applications
cp -r "$APP_NAME" "$INSTALL_DIR/"

# Remove quarantine on installed copy
xattr -cr "$INSTALL_DIR/$APP_NAME" 2>/dev/null || true

# Allow in Gatekeeper
spctl --add "$INSTALL_DIR/$APP_NAME" 2>/dev/null || true

echo "[3/3] Cleaning up..."
rm -rf "$TMPDIR"

echo ""
echo "Installed to $INSTALL_DIR/$APP_NAME"
echo ""

# Auto-launch
open "$INSTALL_DIR/$APP_NAME"

echo "Launched! Look for the eye icon in the menu bar."
echo ""
echo "First time:"
echo "  1. Click the eye icon in the menu bar"
echo "  2. Go to Settings, paste your Montana address (mt...)"
echo "  3. Click Start — earn Ɉ while you're on camera"
echo ""
