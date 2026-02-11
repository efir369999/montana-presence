# Юнона iOS — Сборка для App Store

## Быстрый старт

```bash
cd junona-app
npm install
npx cap add ios
npx cap sync
npx cap open ios
```

## В Xcode

1. Открой `ios/App/App.xcworkspace`
2. Выбери Team в Signing & Capabilities
3. Измени Bundle Identifier на свой
4. Archive → Distribute App → App Store Connect

## Настройки Info.plist

Для доступа к контактам добавь:
```xml
<key>NSContactsUsageDescription</key>
<string>Юнона использует контакты для переводов Ɉ</string>
```

## Иконки

Замени иконки в `ios/App/App/Assets.xcassets/AppIcon.appiconset/`

## Особенности

- Приложение загружает сайт с http://72.56.102.240
- Для продакшна замени на HTTPS
- Capacitor даёт доступ к нативным API (контакты, камера)

## Хардфорк Telegram

Для полноценного клиента:
1. Форкни https://github.com/nicegram/Nicegram-iOS
2. Замени API credentials
3. Добавь Montana Protocol UI
