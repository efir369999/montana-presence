#!/bin/bash
# Montana Protocol — Получить ВСЕ ключи из Keychain
# Выполни: source GET_ALL_KEYS.sh

echo "=== MONTANA KEYCHAIN — ВСЕ КЛЮЧИ ==="
echo ""

# API KEYS
export TELEGRAM_TOKEN_JUNONA=$(security find-generic-password -a "montana" -s "TELEGRAM_TOKEN_JUNONA" -w 2>/dev/null)
export OPENAI_API_KEY=$(security find-generic-password -a "montana" -s "OPENAI_API_KEY" -w 2>/dev/null)
export ANTHROPIC_API_KEY=$(security find-generic-password -a "montana" -s "ANTHROPIC_API_KEY" -w 2>/dev/null)
export GITHUB_TOKEN=$(security find-generic-password -a "montana" -s "GITHUB_TOKEN" -w 2>/dev/null)
export ADMIN_TELEGRAM_ID=$(security find-generic-password -a "montana" -s "ADMIN_TELEGRAM_ID" -w 2>/dev/null)
export AI_PROVIDER=$(security find-generic-password -a "montana" -s "AI_PROVIDER" -w 2>/dev/null)

# ВСЕ 6 УЗЛОВ
export NODE_1_NAME=$(security find-generic-password -a "montana" -s "NODE_1_NAME" -w 2>/dev/null)
export NODE_1_IP=$(security find-generic-password -a "montana" -s "NODE_1_IP" -w 2>/dev/null)
export NODE_1_USER=$(security find-generic-password -a "montana" -s "NODE_1_USER" -w 2>/dev/null)

export NODE_2_NAME=$(security find-generic-password -a "montana" -s "NODE_2_NAME" -w 2>/dev/null)
export NODE_2_IP=$(security find-generic-password -a "montana" -s "NODE_2_IP" -w 2>/dev/null)
export NODE_2_USER=$(security find-generic-password -a "montana" -s "NODE_2_USER" -w 2>/dev/null)

export NODE_3_NAME=$(security find-generic-password -a "montana" -s "NODE_3_NAME" -w 2>/dev/null)
export NODE_3_IP=$(security find-generic-password -a "montana" -s "NODE_3_IP" -w 2>/dev/null)
export NODE_3_USER=$(security find-generic-password -a "montana" -s "NODE_3_USER" -w 2>/dev/null)

export NODE_4_NAME=$(security find-generic-password -a "montana" -s "NODE_4_NAME" -w 2>/dev/null)
export NODE_4_IP=$(security find-generic-password -a "montana" -s "NODE_4_IP" -w 2>/dev/null)
export NODE_4_USER=$(security find-generic-password -a "montana" -s "NODE_4_USER" -w 2>/dev/null)

export NODE_5_NAME=$(security find-generic-password -a "montana" -s "NODE_5_NAME" -w 2>/dev/null)
export NODE_5_IP=$(security find-generic-password -a "montana" -s "NODE_5_IP" -w 2>/dev/null)
export NODE_5_USER=$(security find-generic-password -a "montana" -s "NODE_5_USER" -w 2>/dev/null)

export NODE_6_NAME=$(security find-generic-password -a "montana" -s "NODE_6_NAME" -w 2>/dev/null)
export NODE_6_IP=$(security find-generic-password -a "montana" -s "NODE_6_IP" -w 2>/dev/null)
export NODE_6_USER=$(security find-generic-password -a "montana" -s "NODE_6_USER" -w 2>/dev/null)

# SSH PASSPHRASE
export SSH_PASSPHRASE=$(security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PASSPHRASE" -w 2>/dev/null)

echo "API KEYS:"
echo "  TELEGRAM_TOKEN = $TELEGRAM_TOKEN_JUNONA"
echo "  OPENAI_API_KEY = ${OPENAI_API_KEY:0:20}..."
echo "  GITHUB_TOKEN = ${GITHUB_TOKEN:0:20}..."
echo "  ADMIN_TELEGRAM_ID = $ADMIN_TELEGRAM_ID"
echo "  AI_PROVIDER = $AI_PROVIDER"
echo ""
echo "ВСЕ 6 УЗЛОВ:"
echo "  NODE 1: $NODE_1_NAME — $NODE_1_USER@$NODE_1_IP"
echo "  NODE 2: $NODE_2_NAME — $NODE_2_USER@$NODE_2_IP"
echo "  NODE 3: $NODE_3_NAME — $NODE_3_USER@$NODE_3_IP"
echo "  NODE 4: $NODE_4_NAME — $NODE_4_USER@$NODE_4_IP"
echo "  NODE 5: $NODE_5_NAME — $NODE_5_USER@$NODE_5_IP"
echo "  NODE 6: $NODE_6_NAME — $NODE_6_USER@$NODE_6_IP"
echo ""
echo "SSH PASSPHRASE: loaded (для jn_srv)"
echo ""
echo "✓ Все ключи загружены в env"
