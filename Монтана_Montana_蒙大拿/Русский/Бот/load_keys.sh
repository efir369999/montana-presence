#!/bin/bash
# Montana Protocol — Load keys from macOS Keychain
# Usage: source load_keys.sh

# API Keys
export OPENAI_API_KEY=$(security find-generic-password -a "montana" -s "OPENAI_API_KEY" -w 2>/dev/null)
export ANTHROPIC_API_KEY=$(security find-generic-password -a "montana" -s "ANTHROPIC_API_KEY" -w 2>/dev/null)
export GITHUB_TOKEN=$(security find-generic-password -a "montana" -s "GITHUB_TOKEN" -w 2>/dev/null)

echo "✓ Keys loaded from Keychain"
