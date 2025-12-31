#!/bin/bash
# Build script for Winterfell STARK extension
#
# Prerequisites:
#   - Rust toolchain (rustup.rs)
#   - maturin: pip install maturin
#
# Usage:
#   ./build.sh          # Development build
#   ./build.sh release  # Release build
#   ./build.sh install  # Build and install

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check prerequisites
if ! command -v cargo &> /dev/null; then
    echo "Error: Rust toolchain not found"
    echo "Install from: https://rustup.rs"
    exit 1
fi

if ! command -v maturin &> /dev/null; then
    echo "Installing maturin..."
    pip install maturin
fi

# Build mode
MODE="${1:-develop}"

case "$MODE" in
    develop|dev)
        echo "Building development version..."
        maturin develop
        ;;
    release|rel)
        echo "Building release version..."
        maturin develop --release
        ;;
    install)
        echo "Building and installing release version..."
        maturin build --release
        pip install target/wheels/*.whl --force-reinstall
        ;;
    wheel)
        echo "Building wheel..."
        maturin build --release
        echo "Wheel available at: target/wheels/"
        ;;
    clean)
        echo "Cleaning build artifacts..."
        cargo clean
        rm -rf target/
        ;;
    test)
        echo "Running Rust tests..."
        cargo test
        ;;
    *)
        echo "Usage: $0 [develop|release|install|wheel|clean|test]"
        exit 1
        ;;
esac

echo "Done!"
