#!/bin/bash
# Montana Release Signing Script
# For Alejandro Montana only
#
# Creates signed release binaries with ML-DSA-65 signatures

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
MONTANA_SRC="$PROJECT_ROOT/montana"
RELEASE_DIR="$PROJECT_ROOT/release"

VERSION="${1:-dev}"
TARGET="${2:-x86_64-unknown-linux-gnu}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

echo "======================================"
echo "  Montana Release Signing"
echo "======================================"
echo ""
echo "Version: $VERSION"
echo "Target:  $TARGET"
echo ""

# Check if we're in the right directory
if [ ! -f "$MONTANA_SRC/Cargo.toml" ]; then
    log_error "Cannot find Montana source. Run from Montana ACP/scripts/"
    exit 1
fi

# Step 1: Build release binary
log_step "Building release binary..."
cd "$MONTANA_SRC"
cargo build --release --target "$TARGET"

BINARY_PATH="$MONTANA_SRC/target/$TARGET/release/montana"

if [ ! -f "$BINARY_PATH" ]; then
    log_error "Binary not found at $BINARY_PATH"
    exit 1
fi

log_info "Binary built: $(du -h "$BINARY_PATH" | cut -f1)"

# Step 2: Create release directory
log_step "Creating release directory..."
mkdir -p "$RELEASE_DIR"
RELEASE_NAME="montana-$VERSION-$TARGET"
RELEASE_PATH="$RELEASE_DIR/$RELEASE_NAME"

cp "$BINARY_PATH" "$RELEASE_PATH"
strip "$RELEASE_PATH"  # Remove debug symbols

log_info "Stripped binary: $(du -h "$RELEASE_PATH" | cut -f1)"

# Step 3: Generate SHA3-256 hash
log_step "Generating SHA3-256 hash..."

# Montana uses SHA3-256, not SHA2-256
# We need to use a tool that supports SHA3
# For now, use sha256sum (SHA2) as placeholder
# TODO: Replace with SHA3-256 when available in coreutils

if command -v b3sum > /dev/null 2>&1; then
    # BLAKE3 (better than SHA2, but Montana uses SHA3)
    b3sum "$RELEASE_PATH" > "$RELEASE_PATH.blake3"
    HASH=$(cat "$RELEASE_PATH.blake3" | cut -d' ' -f1)
    log_info "BLAKE3: $HASH"
elif command -v sha256sum > /dev/null 2>&1; then
    # SHA2-256 (not SHA3, but widely available)
    sha256sum "$RELEASE_PATH" > "$RELEASE_PATH.sha256"
    HASH=$(cat "$RELEASE_PATH.sha256" | cut -d' ' -f1)
    log_warn "Using SHA2-256 (Montana uses SHA3-256 in protocol)"
    log_info "SHA2-256: $HASH"
else
    log_error "No hash tool found (need sha256sum or b3sum)"
    exit 1
fi

# Step 4: Sign with ML-DSA-65 (using Montana keygen tool)
log_step "Signing with ML-DSA-65..."

# Check if keygen binary exists
KEYGEN_PATH="$MONTANA_SRC/target/$TARGET/release/keygen"
if [ ! -f "$KEYGEN_PATH" ]; then
    log_warn "keygen binary not found, building..."
    cd "$MONTANA_SRC"
    cargo build --release --bin keygen --target "$TARGET"
fi

# Generate release signing keypair (or use existing)
KEYDIR="$HOME/.montana/release-keys"
mkdir -p "$KEYDIR"

if [ ! -f "$KEYDIR/release-signing.key" ]; then
    log_warn "No release signing key found. Generating new keypair..."
    log_warn "IMPORTANT: Back up $KEYDIR securely!"
    "$KEYGEN_PATH" > "$KEYDIR/release-signing.key"
fi

# TODO: Implement signing with keygen tool
# For now, create placeholder signature file
log_warn "ML-DSA-65 signing not yet implemented in keygen tool"
log_warn "Creating placeholder signature..."

echo "PLACEHOLDER_ML-DSA-65_SIGNATURE" > "$RELEASE_PATH.sig"
echo "Binary: $RELEASE_NAME" >> "$RELEASE_PATH.sig"
echo "Hash: $HASH" >> "$RELEASE_PATH.sig"
echo "Signer: Alejandro Montana" >> "$RELEASE_PATH.sig"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RELEASE_PATH.sig"

# Step 5: Create release manifest
log_step "Creating release manifest..."

cat > "$RELEASE_DIR/manifest.json" <<EOF
{
  "version": "$VERSION",
  "target": "$TARGET",
  "binary": "$RELEASE_NAME",
  "hash_algo": "SHA2-256",
  "hash": "$HASH",
  "signature_algo": "ML-DSA-65",
  "signer": "Alejandro Montana",
  "released_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Step 6: Create tarball
log_step "Creating release tarball..."
cd "$RELEASE_DIR"
tar -czf "$RELEASE_NAME.tar.gz" \
    "$RELEASE_NAME" \
    "$RELEASE_NAME.sha256" \
    "$RELEASE_NAME.sig" \
    "manifest.json"

TARBALL_SIZE=$(du -h "$RELEASE_NAME.tar.gz" | cut -f1)

log_info "Release tarball: $RELEASE_NAME.tar.gz ($TARBALL_SIZE)"

# Summary
echo ""
echo "======================================"
echo "  Release Created"
echo "======================================"
echo ""
echo "Version:    $VERSION"
echo "Target:     $TARGET"
echo "Binary:     $RELEASE_NAME"
echo "Hash:       $HASH"
echo "Tarball:    $RELEASE_NAME.tar.gz ($TARBALL_SIZE)"
echo ""
echo "Files in $RELEASE_DIR:"
ls -lh "$RELEASE_DIR"
echo ""
echo "Next steps:"
echo "  1. Verify signature: ./verify-release.sh $VERSION $TARGET"
echo "  2. Upload to GitHub Releases"
echo "  3. Tag release: git tag v$VERSION"
echo ""
echo "lim(evidence → ∞) 1 Ɉ → 1 секунда"
