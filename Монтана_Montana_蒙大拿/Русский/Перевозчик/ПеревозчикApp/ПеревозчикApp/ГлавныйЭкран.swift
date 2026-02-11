//
//  ГлавныйЭкран.swift
//  Перевозчик — Морская Фрахтовая Платформа
//
//  Главный экран после авторизации
//

import SwiftUI

struct ГлавныйЭкран: View {
    @ObservedObject private var авторизация = СлужбаАвторизации.общий
    @State private var выбраннаяВкладка = 0

    var body: some View {
        TabView(selection: $выбраннаяВкладка) {
            // 1. Junona — AI assistant (FIRST TAB)
            ЭкранЮноны()
                .tabItem {
                    Image(systemName: "sparkles")
                    Text("Junona")
                }
                .tag(0)

            // 2. Ships map
            ЭкранКарты()
                .tabItem {
                    Image(systemName: "map.fill")
                    Text("Ships")
                }
                .tag(1)

            // 3. Cargo
            ЭкранГрузов()
                .tabItem {
                    Image(systemName: "shippingbox.fill")
                    Text("Cargo")
                }
                .tag(2)

            // 4. Deals
            ЭкранСделок()
                .tabItem {
                    Image(systemName: "doc.text.fill")
                    Text("Deals")
                }
                .tag(3)

            // 5. Profile
            ЭкранПрофиля()
                .tabItem {
                    Image(systemName: "person.fill")
                    Text("Profile")
                }
                .tag(4)
        }
        .tint(ПеревозчикТема.основной)
    }
}

// MARK: - Экран Юноны (AI Чат)

struct ЭкранЮноны: View {
    @ObservedObject private var авторизация = СлужбаАвторизации.общий
    @StateObject private var служба = СлужбаЧата()
    @State private var вводТекста = ""
    @State private var печатает = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Сообщения
                ScrollViewReader { прокси in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(служба.сообщения) { сообщение in
                                ПузырьСообщения(сообщение: сообщение)
                                    .id(сообщение.id)
                            }

                            if печатает {
                                ИндикаторПечати()
                            }
                        }
                        .padding()
                    }
                    .onChange(of: служба.сообщения.count) { _, _ in
                        if let последнее = служба.сообщения.last {
                            withAnimation {
                                прокси.scrollTo(последнее.id, anchor: .bottom)
                            }
                        }
                    }
                }

                // Ввод сообщения
                HStack(spacing: 12) {
                    TextField("Спросить Юнону...", text: $вводТекста)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        .background(ПеревозчикТема.карточка)
                        .cornerRadius(24)

                    Button {
                        отправитьСообщение()
                    } label: {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.title)
                            .foregroundColor(вводТекста.isEmpty ? .secondary : ПеревозчикТема.вторичный)
                    }
                    .disabled(вводТекста.isEmpty)
                }
                .padding()
                .background(ПеревозчикТема.фон)
            }
            .background(ПеревозчикТема.фон)
            .navigationTitle("Юнона")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Image(systemName: "sparkles")
                        .foregroundColor(ПеревозчикТема.вторичный)
                }
            }
        }
        .onAppear {
            if служба.сообщения.isEmpty {
                служба.добавитьПриветствие()
            }
            // Регистрируем активность
            служба.отправитьАктивность(userId: авторизация.пользователь?.телеграмИд)
        }
    }

    private func отправитьСообщение() {
        let текст = вводТекста.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !текст.isEmpty else { return }

        вводТекста = ""
        служба.сообщения.append(СообщениеЧата(роль: .пользователь, содержимое: текст))
        печатает = true

        Task {
            await служба.отправитьЮноне(
                сообщение: текст,
                userId: авторизация.пользователь?.телеграмИд
            )
            печатает = false
        }
    }
}

// MARK: - Служба чата

@MainActor
class СлужбаЧата: ObservableObject {
    @Published var сообщения: [СообщениеЧата] = []

    private let базовыйURL = "https://amsterdam.montana.network"

    func добавитьПриветствие() {
        сообщения.append(СообщениеЧата(
            роль: .ассистент,
            содержимое: "Я — Юнона, AI-проводник Montana Protocol.\n\n🚢 Seafare — B2B для морских перевозок.\n⏱️ Время — единственная реальная валюта.\n\nЧем могу помочь?"
        ))
    }

    func отправитьЮноне(сообщение: String, userId: Int64?) async {
        do {
            guard let url = URL(string: базовыйURL + "/api/v1/chat") else {
                добавитьОшибку("Ошибка URL")
                return
            }

            var запрос = URLRequest(url: url)
            запрос.httpMethod = "POST"
            запрос.setValue("application/json", forHTTPHeaderField: "Content-Type")
            запрос.timeoutInterval = 30

            let тело: [String: Any] = [
                "message": сообщение,
                "user_id": userId ?? 0,
                "app": "seafare"
            ]
            запрос.httpBody = try JSONSerialization.data(withJSONObject: тело)

            let (данные, _) = try await URLSession.shared.data(for: запрос)

            if let json = try JSONSerialization.jsonObject(with: данные) as? [String: Any],
               let ответ = json["response"] as? String {
                сообщения.append(СообщениеЧата(роль: .ассистент, содержимое: ответ))
            } else {
                добавитьОшибку("Не удалось разобрать ответ")
            }

        } catch {
            // Fallback — локальный ответ
            let локальныйОтвет = генерироватьЛокальныйОтвет(сообщение)
            сообщения.append(СообщениеЧата(роль: .ассистент, содержимое: локальныйОтвет))
        }
    }

    func отправитьАктивность(userId: Int64?) {
        guard let userId = userId else { return }

        Task {
            guard let url = URL(string: базовыйURL + "/api/v1/activity") else { return }

            var запрос = URLRequest(url: url)
            запрос.httpMethod = "POST"
            запрос.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let тело: [String: Any] = [
                "user_id": userId,
                "app": "seafare"
            ]
            запрос.httpBody = try? JSONSerialization.data(withJSONObject: тело)

            _ = try? await URLSession.shared.data(for: запрос)
        }
    }

    private func добавитьОшибку(_ текст: String) {
        сообщения.append(СообщениеЧата(
            роль: .ассистент,
            содержимое: "⚠️ \(текст)\n\nПопробуй позже или напиши в @junomontanaagibot"
        ))
    }

    private func генерироватьЛокальныйОтвет(_ сообщение: String) -> String {
        let текст = сообщение.lowercased()

        if текст.contains("привет") || текст.contains("hello") {
            return "Привет! Я — Юнона. Чем могу помочь с морскими перевозками?"
        }

        if текст.contains("баланс") || текст.contains("монет") {
            return "💰 Для проверки баланса подключись к сети Montana. Сейчас я работаю в автономном режиме."
        }

        if текст.contains("судн") || текст.contains("корабл") {
            return "🚢 Карта судов доступна на вкладке \"Карта\". Там можно найти свободные суда рядом с тобой."
        }

        if текст.contains("груз") {
            return "📦 Грузы для перевозки на вкладке \"Грузы\". Фильтруй по маршруту и срочности."
        }

        if текст.contains("помощь") || текст.contains("help") || текст.contains("умеешь") {
            return """
Я умею:
🚢 Найти суда — "покажи суда рядом"
📦 Найти грузы — "есть срочные грузы?"
💰 Баланс — "мой баланс"
📜 Сделки — "мои сделки"
🌐 Сеть — "статус Montana"

Просто пиши естественным языком!
"""
        }

        return "Слышу тебя. Сеть временно недоступна, работаю автономно. Напиши 'помощь' для списка команд."
    }
}

// MARK: - Модели чата

struct СообщениеЧата: Identifiable {
    let id = UUID()
    let роль: РольСообщения
    let содержимое: String
    let времяОтправки = Date()

    enum РольСообщения {
        case пользователь
        case ассистент
    }
}

// MARK: - Компоненты UI

struct ПузырьСообщения: View {
    let сообщение: СообщениеЧата

    var body: some View {
        HStack {
            if сообщение.роль == .пользователь { Spacer(minLength: 60) }

            if сообщение.роль == .ассистент {
                // Аватар Юноны
                ZStack {
                    Circle()
                        .fill(ПеревозчикТема.вторичный)
                        .frame(width: 32, height: 32)
                    Image(systemName: "sparkles")
                        .font(.caption)
                        .foregroundColor(.white)
                }
            }

            Text(сообщение.содержимое)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(сообщение.роль == .пользователь ? ПеревозчикТема.основной : ПеревозчикТема.карточка)
                .cornerRadius(20)
                .foregroundColor(.white)

            if сообщение.роль == .ассистент { Spacer(minLength: 60) }
        }
    }
}

struct ИндикаторПечати: View {
    @State private var точки = 0

    var body: some View {
        HStack {
            ZStack {
                Circle()
                    .fill(ПеревозчикТема.вторичный)
                    .frame(width: 32, height: 32)
                Image(systemName: "sparkles")
                    .font(.caption)
                    .foregroundColor(.white)
            }

            Text("Юнона думает" + String(repeating: ".", count: точки))
                .foregroundColor(.secondary)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(ПеревозчикТема.карточка)
                .cornerRadius(20)

            Spacer()
        }
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
                точки = (точки + 1) % 4
            }
        }
    }
}

// MARK: - Экран карты судов

struct ЭкранКарты: View {
    @State private var суда: [Судно] = Судно.примеры

    var body: some View {
        NavigationStack {
            ZStack {
                ПеревозчикТема.фон.ignoresSafeArea()

                ScrollView {
                    LazyVStack(spacing: 16) {
                        // Статистика
                        HStack(spacing: 12) {
                            КарточкаСтатистики(
                                заголовок: "Суда онлайн",
                                значение: "847",
                                иконка: "ferry.fill",
                                цвет: ПеревозчикТема.основной
                            )
                            КарточкаСтатистики(
                                заголовок: "Свободные",
                                значение: "234",
                                иконка: "checkmark.circle.fill",
                                цвет: ПеревозчикТема.успех
                            )
                        }

                        // Список судов
                        ForEach(суда) { судно in
                            КарточкаСудна(судно: судно)
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Карта судов")
        }
    }
}

// MARK: - Экран грузов

struct ЭкранГрузов: View {
    @State private var грузы: [Груз] = Груз.примеры

    var body: some View {
        NavigationStack {
            ZStack {
                ПеревозчикТема.фон.ignoresSafeArea()

                ScrollView {
                    LazyVStack(spacing: 16) {
                        // Статистика
                        HStack(spacing: 12) {
                            КарточкаСтатистики(
                                заголовок: "Активные",
                                значение: "1 234",
                                иконка: "shippingbox.fill",
                                цвет: ПеревозчикТема.вторичный
                            )
                            КарточкаСтатистики(
                                заголовок: "Срочные",
                                значение: "89",
                                иконка: "flame.fill",
                                цвет: ПеревозчикТема.акцент
                            )
                        }

                        // Список грузов
                        ForEach(грузы) { груз in
                            КарточкаГруза(груз: груз)
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Грузы")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        // Добавить груз
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(ПеревозчикТема.основной)
                    }
                }
            }
        }
    }
}

// MARK: - Экран сделок

struct ЭкранСделок: View {
    var body: some View {
        NavigationStack {
            ZStack {
                ПеревозчикТема.фон.ignoresSafeArea()

                VStack(spacing: 20) {
                    Image(systemName: "doc.text.fill")
                        .font(.system(size: 60))
                        .foregroundColor(ПеревозчикТема.основной.opacity(0.5))

                    Text("Нет активных сделок")
                        .font(.headline)
                        .foregroundColor(.secondary)

                    Text("Найдите груз или судно\nи создайте первую сделку")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
            }
            .navigationTitle("Сделки")
        }
    }
}


// MARK: - Экран профиля

struct ЭкранПрофиля: View {
    @ObservedObject private var авторизация = СлужбаАвторизации.общий
    @State private var показатьВыход = false

    var body: some View {
        NavigationStack {
            ZStack {
                ПеревозчикТема.фон.ignoresSafeArea()

                List {
                    // Информация о пользователе
                    if let юзер = авторизация.пользователь {
                        Section {
                            HStack(spacing: 16) {
                                ZStack {
                                    Circle()
                                        .fill(
                                            LinearGradient(
                                                colors: [ПеревозчикТема.основной, ПеревозчикТема.вторичный],
                                                startPoint: .topLeading,
                                                endPoint: .bottomTrailing
                                            )
                                        )
                                        .frame(width: 60, height: 60)

                                    Text(String(юзер.имя.prefix(1)))
                                        .font(.title)
                                        .fontWeight(.bold)
                                        .foregroundColor(.white)
                                }

                                VStack(alignment: .leading, spacing: 4) {
                                    Text(юзер.полноеИмя)
                                        .font(.headline)

                                    Text(юзер.названиеРоли)
                                        .font(.caption)
                                        .foregroundColor(ПеревозчикТема.основной)

                                    if let компания = юзер.компания {
                                        Text(компания)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                            .padding(.vertical, 8)
                        }

                        // Кошелёк Montana
                        Section("Кошелёк Montana Ɉ") {
                            if let _ = юзер.mtАдрес {
                                HStack {
                                    Image(systemName: "wallet.pass.fill")
                                        .foregroundColor(ПеревозчикТема.основной)
                                    Text("Адрес")
                                    Spacer()
                                    Text(юзер.короткийАдрес)
                                        .font(.system(.caption, design: .monospaced))
                                        .foregroundColor(.secondary)
                                }
                            }

                            if let телефон = юзер.телефон {
                                HStack {
                                    Image(systemName: "phone.fill")
                                        .foregroundColor(ПеревозчикТема.успех)
                                    Text("Телефон")
                                    Spacer()
                                    Text(телефон)
                                        .foregroundColor(.secondary)
                                }
                            }

                            HStack {
                                Image(systemName: "clock.fill")
                                    .foregroundColor(ПеревозчикТема.вторичный)
                                Text("Баланс времени")
                                Spacer()
                                Text("0 сек")
                                    .foregroundColor(ПеревозчикТема.вторичный)
                            }
                        }

                        // Статистика
                        Section("Статистика") {
                            HStack {
                                Text("Сделок завершено")
                                Spacer()
                                Text("0")
                                    .foregroundColor(.secondary)
                            }

                            HStack {
                                Text("Оборот (USD)")
                                Spacer()
                                Text("$0")
                                    .foregroundColor(.secondary)
                            }

                            HStack {
                                Text("Рейтинг")
                                Spacer()
                                HStack(spacing: 4) {
                                    Image(systemName: "star.fill")
                                        .foregroundColor(ПеревозчикТема.вторичный)
                                    Text("—")
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    }

                    // Настройки
                    Section("Настройки") {
                        NavigationLink {
                            Text("Уведомления")
                        } label: {
                            Label("Уведомления", systemImage: "bell.fill")
                        }

                        NavigationLink {
                            Text("Документы")
                        } label: {
                            Label("Документы", systemImage: "doc.fill")
                        }

                        NavigationLink {
                            Text("Безопасность")
                        } label: {
                            Label("Безопасность", systemImage: "lock.fill")
                        }
                    }

                    // Выход
                    Section {
                        Button(role: .destructive) {
                            показатьВыход = true
                        } label: {
                            Label("Выйти", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                    }
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Профиль")
            .alert("Выйти из аккаунта?", isPresented: $показатьВыход) {
                Button("Отмена", role: .cancel) { }
                Button("Выйти", role: .destructive) {
                    авторизация.выйти()
                }
            }
        }
    }
}

// MARK: - Компоненты

struct КарточкаСтатистики: View {
    let заголовок: String
    let значение: String
    let иконка: String
    let цвет: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: иконка)
                    .foregroundColor(цвет)
                Spacer()
            }

            Text(значение)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text(заголовок)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ПеревозчикТема.карточка)
        .cornerRadius(12)
    }
}

struct КарточкаСудна: View {
    let судно: Судно

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(судно.название)
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                Text(судно.флаг)
                    .font(.title2)
            }

            HStack {
                Label(судно.тип, systemImage: "ferry.fill")
                    .font(.caption)
                    .foregroundColor(ПеревозчикТема.основной)

                Spacer()

                Label("\(судно.дедвейт) DWT", systemImage: "scalemass.fill")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            HStack {
                Image(systemName: "mappin.circle.fill")
                    .foregroundColor(ПеревозчикТема.успех)
                Text(судно.локация)
                    .font(.caption)
                    .foregroundColor(.secondary)

                Spacer()

                Text(судно.свободно ? "Свободно" : "Занято")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(судно.свободно ? ПеревозчикТема.успех.opacity(0.2) : ПеревозчикТема.акцент.opacity(0.2))
                    .foregroundColor(судно.свободно ? ПеревозчикТема.успех : ПеревозчикТема.акцент)
                    .cornerRadius(8)
            }
        }
        .padding()
        .background(ПеревозчикТема.карточка)
        .cornerRadius(12)
    }
}

struct КарточкаГруза: View {
    let груз: Груз

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(груз.наименование)
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                if груз.срочный {
                    Label("Срочно", systemImage: "flame.fill")
                        .font(.caption)
                        .foregroundColor(ПеревозчикТема.акцент)
                }
            }

            HStack {
                VStack(alignment: .leading) {
                    Text("Откуда")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(груз.откуда)
                        .font(.caption)
                        .foregroundColor(.white)
                }

                Image(systemName: "arrow.right")
                    .foregroundColor(ПеревозчикТема.основной)

                VStack(alignment: .leading) {
                    Text("Куда")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(груз.куда)
                        .font(.caption)
                        .foregroundColor(.white)
                }

                Spacer()

                VStack(alignment: .trailing) {
                    Text("Объём")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(груз.объём)
                        .font(.caption)
                        .foregroundColor(ПеревозчикТема.вторичный)
                }
            }

            HStack {
                Text("$\(груз.ставка)/тонна")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(ПеревозчикТема.успех)

                Spacer()

                Text(груз.срок)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(ПеревозчикТема.карточка)
        .cornerRadius(12)
    }
}

// MARK: - Модели данных

struct Судно: Identifiable {
    let id = UUID()
    let название: String
    let флаг: String
    let тип: String
    let дедвейт: Int
    let локация: String
    let свободно: Bool

    static let примеры: [Судно] = [
        Судно(название: "Северная Звезда", флаг: "🇷🇺", тип: "Балкер", дедвейт: 45000, локация: "Новороссийск", свободно: true),
        Судно(название: "Балтийская Королева", флаг: "🇷🇺", тип: "Танкер", дедвейт: 32000, локация: "Санкт-Петербург", свободно: true),
        Судно(название: "Тихоокеанский Странник", флаг: "🇸🇬", тип: "Контейнеровоз", дедвейт: 28000, локация: "Владивосток", свободно: false),
        Судно(название: "Атлантическая Гордость", флаг: "🇬🇧", тип: "Балкер", дедвейт: 52000, локация: "Роттердам", свободно: true),
    ]
}

struct Груз: Identifiable {
    let id = UUID()
    let наименование: String
    let откуда: String
    let куда: String
    let объём: String
    let ставка: Int
    let срок: String
    let срочный: Bool

    static let примеры: [Груз] = [
        Груз(наименование: "Пшеница", откуда: "Новороссийск", куда: "Александрия", объём: "25 000 т", ставка: 45, срок: "15 фев", срочный: true),
        Груз(наименование: "Уголь", откуда: "Мурманск", куда: "Шанхай", объём: "48 000 т", ставка: 38, срок: "1 мар", срочный: false),
        Груз(наименование: "Железная руда", откуда: "Усть-Луга", куда: "Циндао", объём: "120 000 т", ставка: 22, срок: "20 фев", срочный: false),
        Груз(наименование: "Удобрения", откуда: "Санкт-Петербург", куда: "Роттердам", объём: "35 000 т", ставка: 52, срок: "10 фев", срочный: true),
    ]
}

#Preview {
    ГлавныйЭкран()
}
