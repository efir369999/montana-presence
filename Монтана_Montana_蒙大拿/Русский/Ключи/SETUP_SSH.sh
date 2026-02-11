#!/bin/bash
# Montana Protocol — Восстановить SSH из Keychain
# Выполни: bash SETUP_SSH.sh

echo "=== ВОССТАНОВЛЕНИЕ SSH ==="

# Создать папку
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Ключ id_ed25519 (GitHub)
echo "Восстанавливаю id_ed25519..."
security find-generic-password -a "montana" -s "SSH_KEY_ED25519_PRIVATE" -w | base64 -d > ~/.ssh/id_ed25519
security find-generic-password -a "montana" -s "SSH_KEY_ED25519_PUBLIC" -w > ~/.ssh/id_ed25519.pub
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub

# Ключ jn_srv (серверы)
echo "Восстанавливаю jn_srv..."
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PRIVATE" -w | base64 -d > ~/.ssh/jn_srv
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PUBLIC" -w > ~/.ssh/jn_srv.pub
chmod 600 ~/.ssh/jn_srv
chmod 644 ~/.ssh/jn_srv.pub

# Config
echo "Восстанавливаю config..."
security find-generic-password -a "montana" -s "SSH_CONFIG" -w | base64 -d > ~/.ssh/config
chmod 644 ~/.ssh/config

# Passphrase
echo ""
echo "Passphrase для jn_srv:"
security find-generic-password -a "montana" -s "SSH_KEY_JN_SRV_PASSPHRASE" -w

echo ""
echo "✓ SSH восстановлен"
echo ""
echo "Подключение:"
echo "  ssh my-timeweb     # Timeweb (нужен passphrase)"
echo "  ssh montana-ams    # Amsterdam"
