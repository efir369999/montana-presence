# Montana iOS App

Нативное iOS приложение для Montana Protocol.

## Функции

- **Чаты** — P2P мессенджер между контактами
- **Кошелёк Ɉ** — баланс и присутствие (1 сек = 1 Ɉ)
- **Контакты** — полный импорт из iOS телефонной книги
- **Переводы** — отправка Ɉ по номеру телефона
- **Юнона AI** — чат с AI ассистентом
- **Авторизация** — через Telegram бот @junomontanaagibot

## Структура

```
MontanaApp/
├── Montana/
│   ├── Sources/
│   │   ├── App.swift              # Точка входа + AppState
│   │   ├── Models.swift           # Модели данных (User, Contact, P2PMessage)
│   │   ├── API.swift              # API клиент
│   │   ├── ContentView.swift      # Главный view + TabView
│   │   └── Views/
│   │       ├── LoginView.swift    # Экран входа через Telegram
│   │       ├── ChatsView.swift    # Список чатов (P2P мессенджер)
│   │       ├── WalletView.swift   # Кошелёк + присутствие
│   │       ├── ContactsView.swift # Контакты + импорт
│   │       ├── ChatView.swift     # Чат с Юноной AI
│   │       └── SettingsView.swift # Настройки
│   ├── Assets.xcassets/           # Цвета и иконки
│   └── Info.plist                 # Конфигурация (com.montana.app)
├── server_p2p_api.py              # API endpoints для P2P (добавить на сервер)
└── README.md
```

## Создание Xcode проекта

### 1. Создать проект в Xcode

```
File → New → Project → iOS → App
- Product Name: Montana
- Team: [Ваш аккаунт]
- Organization Identifier: com.montana
- Interface: SwiftUI
- Language: Swift
- Storage: None
- Убрать все галочки (Tests, Core Data)
```

### 2. Заменить файлы

1. Удалить автосгенерированные файлы (`ContentView.swift`, `MontanaApp.swift`)
2. Скопировать содержимое `Sources/` в проект
3. Заменить `Assets.xcassets`
4. Заменить `Info.plist`

### 3. Добавить Contacts Framework

```
Project → Target → Build Phases → Link Binary With Libraries
→ + → Contacts.framework
```

### 4. Настроить Signing

```
Project → Target → Signing & Capabilities
- Team: [Выбрать]
- Bundle Identifier: com.montana.app
```

### 5. Запуск

```
⌘ + R — Simulator
⌘ + R с подключённым iPhone — на устройстве
```

## API

Приложение использует API на `http://72.56.102.240`:

### Пользователь
- `GET /api/user` — данные пользователя
- `GET /api/login-status` — статус входа

### Контакты
- `GET /api/contacts` — список контактов
- `POST /api/contacts` — сохранить контакт

### P2P Мессенджер
- `GET /api/conversations` — список чатов с последним сообщением
- `GET /api/messages?with={phone}` — сообщения с контактом
- `POST /api/messages` — отправить сообщение (body: `{to_phone, content}`)

### Кошелёк
- `POST /api/presence` — синхронизация присутствия
- `POST /api/transfer` — перевод Ɉ

### Юнона AI
- `POST /api/chat` — сообщение Юноне

## App Store

### Требования
- Apple Developer Account ($99/год)
- Иконка 1024x1024
- Скриншоты всех размеров

### Публикация
```
Product → Archive → Distribute App → App Store Connect
```

## Лицензия

Montana Protocol © 2026
