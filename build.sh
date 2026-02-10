#!/bin/bash
# Build Montana Presence — macOS menu bar app
# Usage: ./build.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$DIR/src"
APP="$DIR/MontanaPresence.app"

echo "=== Montana Presence Build ==="
echo ""

# Clean previous build
rm -rf "$APP"

# Compile
echo "[1/3] Compiling..."
swiftc \
    -o "$DIR/MontanaPresence" \
    -framework SwiftUI \
    -framework AVFoundation \
    -framework Vision \
    -framework Security \
    -framework ServiceManagement \
    -target arm64-apple-macos14.0 \
    -parse-as-library \
    "$SRC/MontanaAPIClient.swift" \
    "$SRC/CameraManager.swift" \
    "$SRC/PresenceEngine.swift" \
    "$SRC/MenuBarView.swift" \
    "$SRC/SettingsView.swift" \
    "$SRC/MontanaPresenceApp.swift"

# Create .app bundle
echo "[2/3] Creating app bundle..."
mkdir -p "$APP/Contents/MacOS"
mv "$DIR/MontanaPresence" "$APP/Contents/MacOS/"
cp "$SRC/Info.plist" "$APP/Contents/"

# Sign (ad-hoc)
echo "[3/3] Signing..."
codesign --force --sign - --entitlements "$SRC/Entitlements.plist" "$APP"

echo ""
echo "Done! Built: $APP"
echo ""
echo "To run:"
echo "  open \"$APP\""
echo ""
echo "To install to Applications:"
echo "  cp -r \"$APP\" /Applications/"
