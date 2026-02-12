#!/bin/bash
# Build Montana v2.11.0 menu bar app
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$DIR/Montana.app"

echo "Building Montana v2.11.0..."

# Clean
rm -rf "$APP"
rm -rf "$DIR/MontanaPresence.app"

# Compile all Swift files
swiftc \
    -o "$DIR/MontanaPresence" \
    -framework SwiftUI \
    -framework AVFoundation \
    -framework Security \
    -framework ServiceManagement \
    -framework CoreImage \
    -framework CoreLocation \
    -framework CoreBluetooth \
    -framework ApplicationServices \
    -target arm64-apple-macos14.0 \
    -parse-as-library \
    "$DIR/MontanaAPIClient.swift" \
    "$DIR/CameraManager.swift" \
    "$DIR/PresenceEngine.swift" \
    "$DIR/VPNManager.swift" \
    "$DIR/SendView.swift" \
    "$DIR/ReceiveView.swift" \
    "$DIR/UpdateManager.swift" \
    "$DIR/MenuBarView.swift" \
    "$DIR/SettingsView.swift" \
    "$DIR/MontanaPresenceApp.swift"

# Create .app bundle
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"
mv "$DIR/MontanaPresence" "$APP/Contents/MacOS/"
cp "$DIR/Info.plist" "$APP/Contents/"
cp "$DIR/Montana.icns" "$APP/Contents/Resources/" 2>/dev/null || true

# Sign with entitlements (ad-hoc)
codesign --force --sign - --entitlements "$DIR/Entitlements.plist" "$APP"

# Create zip for distribution
cd "$DIR"
rm -f Montana.app.zip
zip -r -q Montana.app.zip Montana.app

echo "Built: $APP"
echo "Package: $DIR/Montana.app.zip"
echo "Run: open \"$APP\""
