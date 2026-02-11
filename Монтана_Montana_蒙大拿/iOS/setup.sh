#!/bin/bash
#
# Montana iOS — One-Click Setup
# Запусти и иди кушать, всё будет готово
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🏔 Montana iOS Setup"
echo ""

# 1. Check/Install XcodeGen
if ! command -v xcodegen &> /dev/null; then
    echo "📦 Installing XcodeGen..."
    brew install xcodegen
else
    echo "✅ XcodeGen installed"
fi

# 2. Generate all projects
echo ""
echo "🔨 Generating Xcode projects..."

cd "$SCRIPT_DIR/Apps/JunonaAI"
xcodegen generate
echo "   ✅ JunonaAI.xcodeproj"

cd "$SCRIPT_DIR/Apps/MontanaWallet"
xcodegen generate
echo "   ✅ MontanaWallet.xcodeproj"

cd "$SCRIPT_DIR/Apps/MontanaContracts"
xcodegen generate
echo "   ✅ MontanaContracts.xcodeproj"

# 3. Open main project
echo ""
echo "🚀 Opening Xcode..."
open "$SCRIPT_DIR/Apps/JunonaAI/JunonaAI.xcodeproj"

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ ГОТОВО!"
echo ""
echo "В Xcode:"
echo "  1. Выбери свой Team (Signing)"
echo "  2. Подключи iPhone"
echo "  3. Нажми ▶ Run"
echo ""
echo "4 вкладки: Контакты | Папки | Юнона | Настройки"
echo "═══════════════════════════════════════════════════"
