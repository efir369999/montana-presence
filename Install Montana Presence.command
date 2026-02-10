#!/bin/bash
# ╔══════════════════════════════════════════════════╗
# ║     Montana Presence — Installing...             ║
# ╚══════════════════════════════════════════════════╝
clear
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║                                          ║"
echo "  ║     Montana Presence                     ║"
echo "  ║     Proof of Presence · macOS            ║"
echo "  ║                                          ║"
echo "  ║     Installing...                        ║"
echo "  ║                                          ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Check macOS
SW_VER=$(sw_vers -productVersion | cut -d. -f1)
if [ "$SW_VER" -lt 14 ]; then
    echo "  ✗ macOS 14 (Sonoma) or later required"
    echo "    You have: $(sw_vers -productVersion)"
    echo ""
    read -p "  Press Enter to close..."
    exit 1
fi

# Check arch
if [ "$(uname -m)" != "arm64" ]; then
    echo "  ✗ Apple Silicon required (M1/M2/M3/M4)"
    echo ""
    read -p "  Press Enter to close..."
    exit 1
fi

echo "  [1/4] Downloading..."
TMPDIR=$(mktemp -d)
curl -fsSL "https://github.com/efir369999/montana-presence/releases/latest/download/MontanaPresence.zip" -o "$TMPDIR/app.zip"

echo "  [2/4] Unpacking..."
cd "$TMPDIR"
unzip -q app.zip

echo "  [3/4] Installing to /Applications..."
xattr -cr MontanaPresence.app 2>/dev/null
cp -r MontanaPresence.app /Applications/
xattr -cr /Applications/MontanaPresence.app 2>/dev/null

echo "  [4/4] Launching..."
open /Applications/MontanaPresence.app

rm -rf "$TMPDIR"

echo ""
echo "  ✓ Montana Presence installed!"
echo ""
echo "  Look for the eye icon in your menu bar."
echo "  Open Settings → paste your Montana address → Start"
echo ""
echo "  This window will close in 5 seconds..."
sleep 5
osascript -e 'tell application "Terminal" to close front window' 2>/dev/null &
exit 0
