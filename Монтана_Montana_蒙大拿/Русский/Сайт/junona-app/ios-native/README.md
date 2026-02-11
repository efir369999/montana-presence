# Юнона iOS — Нативная обёртка

## Быстрый старт

### 1. Создание Xcode проекта

```bash
# Открыть Xcode
# File → New → Project
# iOS → App
# Product Name: Junona
# Team: [Выбрать аккаунт]
# Organization Identifier: com.montana
# Interface: Storyboard
# Language: Swift
# Убрать галочки: Use Core Data, Include Tests
```

### 2. Замена файлов

После создания проекта заменить файлы:

```bash
# Скопировать наши файлы в проект
cp AppDelegate.swift [путь к проекту]/Junona/
cp ViewController.swift [путь к проекту]/Junona/
cp Info.plist [путь к проекту]/Junona/
cp LaunchScreen.storyboard [путь к проекту]/Junona/
cp -r Assets.xcassets [путь к проекту]/Junona/
```

### 3. Настройка проекта в Xcode

1. **Удалить лишнее:**
   - Удалить Main.storyboard
   - Удалить SceneDelegate.swift (если есть)

2. **Info.plist:**
   - Удалить `UISceneManifest` (если есть)
   - Удалить `UIMainStoryboardFile`

3. **Build Settings:**
   - iOS Deployment Target: 15.0
   - Swift Language Version: 5.0

4. **Signing & Capabilities:**
   - Добавить App Groups
   - Добавить Associated Domains

### 4. App Icon

Создать иконку 1024x1024 с:
- Фон: #0F0F1A
- Символ: Ɉ золотой (#FFD700)

### 5. Сборка

```bash
# Simulator
⌘ + R

# Device
# Подключить iPhone → выбрать в Xcode → ⌘ + R

# Archive для App Store
Product → Archive
```

## Структура

```
ios-native/
├── AppDelegate.swift      # Точка входа + deep links
├── ViewController.swift   # WKWebView + нативные функции
├── Info.plist            # Разрешения + ATS
├── LaunchScreen.storyboard # Splash screen
└── Assets.xcassets/      # Иконки и цвета
    ├── AppIcon.appiconset/
    └── AccentColor.colorset/
```

## Функции

### JavaScript → Native Bridge

```javascript
// Запросить контакты
window.webkit.messageHandlers.contacts.postMessage({});

// Haptic feedback
window.webkit.messageHandlers.haptic.postMessage({style: 'medium'});

// Поделиться
window.webkit.messageHandlers.share.postMessage({
    title: 'Montana Protocol',
    text: 'Приглашаю в Montana Protocol',
    url: 'https://t.me/junomontanaagibot'
});
```

### URL Schemes

```
junona://        — открывает приложение
montana://pay    — открывает страницу оплаты
```

## App Store

### Требования:
1. Apple Developer Account ($99/год)
2. Certificates + Provisioning Profiles
3. App Store Connect

### Ключевые поля:
- Bundle ID: com.montana.junona
- SKU: junona-montana-001
- Категория: Finance
- Возраст: 4+

### Скриншоты:
- 6.5" (iPhone 14 Pro Max): 1290 x 2796
- 5.5" (iPhone 8 Plus): 1242 x 2208
- iPad Pro 12.9": 2048 x 2732
