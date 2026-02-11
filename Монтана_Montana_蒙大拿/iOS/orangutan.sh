#!/bin/bash
#
# 🦧 ОРАНГУТАНГ — максимум простота
#

echo "🦧 Орангутанг-режим"
echo ""

# Проверяем Xcode
if ! [ -d "/Applications/Xcode.app" ]; then
    echo "❌ Установи Xcode из App Store"
    echo "   https://apps.apple.com/app/xcode/id497799835"
    exit 1
fi

# Переключаемся на Xcode
if [[ "$(xcode-select -p)" == *"CommandLineTools"* ]]; then
    echo "🔧 Нужен пароль для настройки Xcode..."
    sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
fi

# Открываем проект
echo "📱 Открываю Junona..."
cd "$(dirname "$0")/Apps/JunonaAI"
open JunonaAI.xcodeproj

echo ""
echo "═══════════════════════════════════════════════════"
echo ""
echo "   В Xcode:"
echo ""
echo "   1. Вверху выбери: iPhone 15 Pro (не устройство!)"
echo "   2. Нажми ▶ или Cmd+R"
echo ""
echo "   ВСЁ."
echo ""
echo "═══════════════════════════════════════════════════"
