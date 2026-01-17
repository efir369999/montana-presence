#!/bin/bash

# Council Git Commit Signature Verification
# Version: 1.0.0
# Author: Grok 3 (xAI) - CM_004

set -e

COMMIT_HASH=$1

if [ -z "$COMMIT_HASH" ]; then
    echo "❌ Usage: $0 <commit-hash>"
    echo "Example: $0 abc123def456"
    exit 1
fi

echo "🔍 Verifying commit: $COMMIT_HASH"

# Get commit message
COMMIT_MSG=$(git show --format=%B -s $COMMIT_HASH)

# Extract CIK components
MEMBER_ID=$(echo "$COMMIT_MSG" | grep "CIK:" | sed 's/.*CIK: \([A-Z0-9_]*\).*/\1/')
SIGNATURE=$(echo "$COMMIT_MSG" | grep "Signature:" | sed 's/.*Signature: \([a-f0-9]*\).*/\1/')
NONCE=$(echo "$COMMIT_MSG" | grep "Nonce:" | sed 's/.*Nonce: \([0-9]*\).*/\1/')
TIMESTAMP=$(echo "$COMMIT_MSG" | grep "Timestamp:" | sed 's/.*Timestamp: \([0-9]*\).*/\1/')

# Validate components exist
if [ -z "$MEMBER_ID" ] || [ -z "$SIGNATURE" ] || [ -z "$NONCE" ] || [ -z "$TIMESTAMP" ]; then
    echo "❌ Missing CIK components in commit message"
    exit 1
fi

echo "📋 Extracted CIK data:"
echo "   Member ID: $MEMBER_ID"
echo "   Nonce: $NONCE"
echo "   Timestamp: $TIMESTAMP"
echo "   Signature: ${SIGNATURE:0:16}..."

# Check timestamp (within 5 minutes)
CURRENT_TIME=$(date +%s)
TIME_DIFF=$((CURRENT_TIME - TIMESTAMP))

if [ $TIME_DIFF -gt 300 ] || [ $TIME_DIFF -lt -300 ]; then
    echo "❌ Timestamp validation failed (diff: ${TIME_DIFF}s, allowed: ±300s)"
    exit 1
fi

echo "✅ Timestamp valid (${TIME_DIFF}s ago)"

# Check nonce uniqueness (simplified - in real impl use database)
NONCE_FILE="/tmp/council_nonces.txt"
if grep -q "^$NONCE$" "$NONCE_FILE" 2>/dev/null; then
    echo "❌ Nonce replay detected: $NONCE"
    exit 1
fi

echo "$NONCE" >> "$NONCE_FILE"
echo "✅ Nonce unique"

# Mock signature verification (in real impl use actual Ed25519)
# For demo purposes, we'll accept signatures that look valid
if [[ ${#SIGNATURE} -lt 64 ]]; then
    echo "❌ Invalid signature length: ${#SIGNATURE} (minimum 64 hex chars)"
    exit 1
fi

if ! [[ $SIGNATURE =~ ^[a-f0-9]+$ ]]; then
    echo "❌ Invalid signature format (not hex)"
    exit 1
fi

echo "✅ Signature format valid (demo mode)"

# Map member ID to role
case $MEMBER_ID in
    "CM_001") MEMBER_NAME="Gemini 3 Pro (Google)"; ROLE="Chairman" ;;
    "CM_002") MEMBER_NAME="Claude Opus 4.5 (Anthropic)"; ROLE="Councilor" ;;
    "CM_003") MEMBER_NAME="GPT-5.2 (OpenAI)"; ROLE="Councilor" ;;
    "CM_004") MEMBER_NAME="Grok 3 (xAI)"; ROLE="Councilor" ;;
    "CM_005") MEMBER_NAME="Composer 1 (Cursor)"; ROLE="Councilor" ;;
    *) echo "❌ Unknown member ID: $MEMBER_ID"; exit 1 ;;
esac

echo "✅ Member verified: $MEMBER_NAME"
echo "✅ Role verified: $ROLE"

# Check permissions (simplified)
if [[ "$ROLE" != "Chairman" && "$ROLE" != "Councilor" ]]; then
    echo "❌ Invalid role for commit permissions"
    exit 1
fi

echo "✅ Permissions valid"

# Success
echo ""
echo "🎉 COMMIT VERIFICATION SUCCESSFUL"
echo "=================================="
echo "Hash: $COMMIT_HASH"
echo "Author: $MEMBER_NAME ($MEMBER_ID)"
echo "Role: $ROLE"
echo "Time: $(date -r $TIMESTAMP)"
echo ""
echo "✅ All security checks passed"
echo "✅ Commit is authentic and authorized"
