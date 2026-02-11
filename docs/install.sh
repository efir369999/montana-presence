#!/bin/bash
# Montana Ɉ — One-click installer
# curl -sL https://efir.org/install.sh | bash
set -e

REPO="efir369999/-_Nothing_-"

echo ""
echo "  ▲ Montana Ɉ — Installing..."
echo ""

OS=$(uname -s)
ARCH=$(uname -m)
echo "  Platform: $OS $ARCH"

TMP_DIR="/tmp/montana-install"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

# ════════════════════════════════════════════
# macOS: Menu bar app + CLI
# ════════════════════════════════════════════
if [[ "$OS" == "Darwin" ]]; then
    echo "  Downloading Montana.app from GitHub..."

    DOWNLOAD_URL=$(curl -sL "https://api.github.com/repos/$REPO/releases/latest" \
        | grep '"browser_download_url"' \
        | grep 'Montana.app.zip' \
        | head -1 \
        | sed 's/.*"browser_download_url": *"//;s/".*//')

    if [ -z "$DOWNLOAD_URL" ]; then
        echo "  GitHub release not found, fallback to efir.org..."
        DOWNLOAD_URL="https://efir.org/downloads/Montana_2.5.0.zip"
    fi

    curl -sL "$DOWNLOAD_URL" -o "$TMP_DIR/Montana.app.zip"
    cd "$TMP_DIR"
    unzip -q Montana.app.zip

    # Kill old
    pkill -9 -f Montana 2>/dev/null || true
    sleep 1

    # Install
    rm -rf /Applications/Montana.app
    cp -R "$TMP_DIR/Montana.app" /Applications/Montana.app

    # Remove quarantine (Gatekeeper bypass for ad-hoc signed)
    xattr -cr /Applications/Montana.app 2>/dev/null || true

    # CLI binary
    if [ -f "$TMP_DIR/montana" ]; then
        chmod +x "$TMP_DIR/montana"
        sudo mv "$TMP_DIR/montana" /usr/local/bin/montana 2>/dev/null || true
    fi

    # Config dir
    mkdir -p ~/.montana/keys

    # Launch
    open /Applications/Montana.app

    VERSION=$(defaults read /Applications/Montana.app/Contents/Info CFBundleShortVersionString 2>/dev/null || echo "2.5.0")
    BUILD=$(defaults read /Applications/Montana.app/Contents/Info CFBundleVersion 2>/dev/null || echo "22")

    echo ""
    echo "  ▲ Montana v${VERSION} (build ${BUILD}) installed!"
    echo ""
    echo "  App:  /Applications/Montana.app (running)"
    echo "  Auto-start: enabled (launch at login)"
    echo "  Camera: will request on first launch"
    echo ""
    echo "  Time is the only real currency."
    echo "  @junomoneta"
    echo ""
fi

# ════════════════════════════════════════════
# Linux: CLI + systemd
# ════════════════════════════════════════════
if [[ "$OS" == "Linux" ]]; then
    echo "  Downloading Montana CLI from GitHub..."

    DOWNLOAD_URL=$(curl -sL "https://api.github.com/repos/$REPO/releases/latest" \
        | grep '"browser_download_url"' \
        | grep 'montana-linux' \
        | head -1 \
        | sed 's/.*"browser_download_url": *"//;s/".*//')

    if [ -z "$DOWNLOAD_URL" ]; then
        echo "  GitHub release not found, fallback to efir.org..."
        DOWNLOAD_URL="https://efir.org/downloads/montana-linux-amd64"
    fi

    curl -sL "$DOWNLOAD_URL" -o /tmp/montana
    chmod +x /tmp/montana
    sudo mv /tmp/montana /usr/local/bin/montana

    mkdir -p ~/.montana/keys

    echo ""
    echo "  ▲ Montana CLI installed!"
    echo ""
    echo "  montana init     # Create wallet"
    echo "  montana balance  # Check balance"
    echo "  montana status   # Network status"
    echo ""
    echo "  @junomoneta"
    echo ""
fi

rm -rf "$TMP_DIR"
