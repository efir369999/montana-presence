import SwiftUI

/// Junona AI Agent — Montana Protocol Assistant
/// Dual-AI (Claude + GPT) для помощи и обучения
struct JunonaView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var messages: [ChatMessage] = []
    @State private var inputText = ""
    @State private var isLoading = false
    @State private var showSidebar = false

    // AI toggles
    @State private var claudeEnabled = true
    @State private var gptEnabled = false

    // Chat sessions
    @State private var sessions: [JunonaSession] = []
    @State private var currentSessionId: UUID?

    // Presence tracking (10 min activity required)
    @State private var activeStartTime: Date?
    @State private var hasMessages = false
    @State private var activityTimer: Timer?

    var body: some View {
        ZStack(alignment: .leading) {
            // Main content
            VStack(spacing: 0) {
                // Header
                header

                Divider()

                // Chat messages
                ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        // Welcome message
                        if messages.isEmpty {
                            welcomeMessage
                        }

                        // Messages
                        ForEach(messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }

                        // Loading indicator
                        if isLoading {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.8)
                                Text("Junona думает...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .padding(.leading, 50)
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) {
                    if let lastMessage = messages.last {
                        withAnimation {
                            proxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                }
            }

            Divider()

            // Input area
            inputArea
        }
        .background(Color(NSColor.windowBackgroundColor))

        // Sidebar overlay
        if showSidebar {
            Color.black.opacity(0.3)
                .ignoresSafeArea()
                .onTapGesture {
                    withAnimation {
                        showSidebar = false
                    }
                }

            sidebar
                .transition(.move(edge: .leading))
        }
    }
    .animation(.easeInOut(duration: 0.3), value: showSidebar)
    .onAppear {
        loadSessions()
        startActivityTracking()
    }
    .onDisappear {
        stopActivityTracking()
    }
}

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            // Burger menu button
            Button(action: {
                withAnimation {
                    showSidebar.toggle()
                }
            }) {
                Image(systemName: "line.3.horizontal")
                    .font(.system(size: 20))
                    .foregroundColor(.primary)
            }
            .buttonStyle(.plain)

            // Junona icon
            Circle()
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.0, green: 0.83, blue: 1.0),   // #00d4ff cyan
                            Color(red: 0.48, green: 0.18, blue: 1.0)   // #7b2fff purple
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 40, height: 40)
                .overlay(
                    Text("Ю")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Junona")
                    .font(.headline)
                Text("Montana Protocol Assistant")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // AI toggles
            aiToggles
        }
        .padding()
    }

    private var aiToggles: some View {
        HStack(spacing: 16) {
            // Claude toggle
            Toggle(isOn: $claudeEnabled) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(claudeEnabled ? Color.orange : Color.gray.opacity(0.3))
                        .frame(width: 8, height: 8)
                    Text("Claude")
                        .font(.caption)
                        .foregroundColor(claudeEnabled ? .primary : .secondary)
                }
            }
            .toggleStyle(.checkbox)

            // GPT toggle
            Toggle(isOn: $gptEnabled) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(gptEnabled ? Color.green : Color.gray.opacity(0.3))
                        .frame(width: 8, height: 8)
                    Text("GPT")
                        .font(.caption)
                        .foregroundColor(gptEnabled ? .primary : .secondary)
                }
            }
            .toggleStyle(.checkbox)
        }
    }

    // MARK: - Sidebar

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Sidebar header
            HStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 0.0, green: 0.83, blue: 1.0),
                                Color(red: 0.48, green: 0.18, blue: 1.0)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 32, height: 32)
                    .overlay(
                        Text("Ю")
                            .font(.system(size: 16, weight: .bold))
                            .foregroundColor(.white)
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text("Junona")
                        .font(.headline)
                    Text("Montana Protocol")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Button(action: {
                    withAnimation {
                        showSidebar = false
                    }
                }) {
                    Image(systemName: "xmark")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Montana Technologies
                    montanaNavigation

                    Divider()

                    // Junona Sessions
                    junonaSessions
                }
                .padding()
            }
        }
        .frame(width: 280)
        .background(Color(NSColor.controlBackgroundColor).opacity(0.95))
        .shadow(radius: 10)
    }

    private var montanaNavigation: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Montana")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            VStack(spacing: 4) {
                NavItem(icon: "banknote", label: "Кошелёк", tag: 1)
                NavItem(icon: "at", label: "Домены", tag: 2)
                NavItem(icon: "phone", label: "Номера", tag: 3)
                NavItem(icon: "phone.fill", label: "Звонки", tag: 4)
                NavItem(icon: "globe", label: "Сайты", tag: 5)
                NavItem(icon: "play.circle", label: "Видео", tag: 6)
                NavItem(icon: "clock.arrow.circlepath", label: "История", tag: 7)
                NavItem(icon: "pentagon", label: "Цепочка", tag: 8)
                NavItem(icon: "gear", label: "Настройки", tag: 9)
            }
        }
    }

    private var junonaSessions: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Чаты с Юноной")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)

                Spacer()

                Button(action: newSession) {
                    Image(systemName: "plus")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))
                }
                .buttonStyle(.plain)
            }

            if sessions.isEmpty {
                Text("Начни новый чат")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.vertical, 8)
            } else {
                VStack(spacing: 4) {
                    ForEach(sessions) { session in
                        SessionItem(session: session, isCurrent: session.id == currentSessionId) {
                            loadSession(session)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Welcome Message

    private var welcomeMessage: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("👋 Привет! Я — Junona")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Я помогу тебе разобраться с Montana Protocol:")
                .foregroundColor(.secondary)

            VStack(alignment: .leading, spacing: 8) {
                FeatureRow(icon: "💰", text: "Управление кошельком и балансом")
                FeatureRow(icon: "📞", text: "Регистрация доменов и номеров")
                FeatureRow(icon: "🔐", text: "Безопасность и криптография")
                FeatureRow(icon: "⚡", text: "Майнинг и датчики присутствия")
                FeatureRow(icon: "🌐", text: "Аукционы и экономическая модель")
            }
            .padding(.vertical, 8)

            Text("Просто задай любой вопрос!")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
        .padding(.horizontal)
    }

    // MARK: - Input Area

    private var inputArea: some View {
        HStack(spacing: 12) {
            TextField("Спроси Junona...", text: $inputText, axis: .vertical)
                .textFieldStyle(.plain)
                .padding(8)
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
                .lineLimit(1...5)
                .onSubmit {
                    sendMessage()
                }

            Button(action: sendMessage) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(inputText.isEmpty ? .gray : Color(red: 0.0, green: 0.83, blue: 1.0))
            }
            .buttonStyle(.plain)
            .disabled(inputText.isEmpty || isLoading)
        }
        .padding()
    }

    // MARK: - Actions

    private func sendMessage() {
        guard !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        // Input sanitization (max 500 chars)
        let sanitized = sanitizeInput(inputText)
        guard !sanitized.isEmpty else {
            messages.append(ChatMessage(
                role: .assistant,
                content: "⚠️ Пожалуйста, введи корректный вопрос",
                timestamp: Date()
            ))
            return
        }

        let userMessage = ChatMessage(
            role: .user,
            content: sanitized,
            timestamp: Date()
        )

        messages.append(userMessage)
        let question = sanitized
        inputText = ""
        isLoading = true
        hasMessages = true

        // Check if should activate Junona sensor (>10 min activity + messages)
        checkAndActivateJunona()

        // Get AI response
        Task {
            do {
                let response = try await getAIResponse(for: question)
                await MainActor.run {
                    messages.append(ChatMessage(
                        role: .assistant,
                        content: response,
                        timestamp: Date(),
                        aiModel: claudeEnabled ? "claude" : "gpt"
                    ))
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    // Generic error message (no implementation details)
                    messages.append(ChatMessage(
                        role: .assistant,
                        content: "❌ Не удалось получить ответ. Проверь подключение к интернету и попробуй позже.",
                        timestamp: Date()
                    ))
                    isLoading = false
                }
            }
        }
    }

    private func getAIResponse(for question: String) async throws -> String {
        // System prompt for Junona
        let systemPrompt = """
        Ты — Junona, AI-агент Montana Protocol. Твоя задача — помогать пользователям разобраться с Montana.

        Montana Protocol — это протокол идеальных денег (Ideal Money), где:
        - 1 Ɉ (монета времени) = 1 секунда человеческого присутствия
        - Genesis Price: 1 Ɉ = $0.1605 USD = 12.04₽ RUB
        - Постквантовая криптография: ML-DSA-65 (Dilithium)

        Аукционная модель:
        - Домены (alice@montana.network): N-й домен = N Ɉ
        - Виртуальные номера (+montana-000042): N-й номер = N Ɉ
        - Звонки: фиксированная цена 1 Ɉ/сек для владельцев номеров

        Майнинг:
        - Базовый вес: 1 (просто запущенное приложение)
        - Каждый датчик (камера, микрофон, GPS, Bluetooth): +1
        - VPN: +1
        - Формула: weight = 1 + активные датчики + VPN

        Датчики НЕ СОБИРАЮТ ДАННЫЕ — это просто якоря (anchors) для proof-of-presence.

        Отвечай кратко, по-русски, с примерами. Будь дружелюбной и помогай разобраться.
        """

        // Get user's Montana context (NO SENSITIVE DATA)
        let userContext = """

        Контекст пользователя:
        - Кошелёк: \((engine.address ?? "").isEmpty ? "не создан" : "создан ✓")
        - Вес майнинга: \(engine.weight)x
        - Майнинг активен: \(engine.isTracking ? "да" : "нет")
        """

        let fullPrompt = systemPrompt + userContext + "\n\nВопрос: \(question)"

        // Call AI API based on toggles
        if claudeEnabled {
            return try await callClaudeAPI(prompt: fullPrompt)
        } else if gptEnabled {
            return try await callGPTAPI(prompt: fullPrompt)
        } else {
            return "⚠️ Включи хотя бы один AI (Claude или GPT) в настройках выше"
        }
    }

    private func sanitizeInput(_ input: String) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let maxLength = 500
        let limited = String(trimmed.prefix(maxLength))

        // Remove control characters
        let allowed = CharacterSet.alphanumerics
            .union(.whitespaces)
            .union(.punctuationCharacters)
            .union(CharacterSet(charactersIn: "?!.,;:-—–—()[]{}\"'«»№@#$%^&*+=<>/\\"))

        return String(limited.unicodeScalars.filter { allowed.contains($0) })
    }

    private func callClaudeAPI(prompt: String) async throws -> String {
        // Load API key from keychain
        guard var apiKey = getAPIKey(service: "ANTHROPIC_API_KEY") else {
            return "❌ Claude API key не найден в keychain"
        }

        // Zero API key after use
        defer {
            apiKey = String(repeating: "\0", count: apiKey.count)
        }

        let url = URL(string: "https://api.anthropic.com/v1/messages")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30  // 30s timeout

        let body: [String: Any] = [
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 1024,
            "messages": [
                ["role": "user", "content": prompt]
            ]
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        // Use session with timeout
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        let session = URLSession(configuration: config)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NSError(domain: "Junona", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "Не удалось получить ответ"
            ])
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = json["content"] as? [[String: Any]],
              let firstContent = content.first,
              let text = firstContent["text"] as? String else {
            throw NSError(domain: "Junona", code: -2, userInfo: [
                NSLocalizedDescriptionKey: "Не удалось получить ответ"
            ])
        }

        return text
    }

    private func callGPTAPI(prompt: String) async throws -> String {
        // Load API key from keychain
        guard var apiKey = getAPIKey(service: "OPENAI_API_KEY") else {
            return "❌ OpenAI API key не найден в keychain"
        }

        // Zero API key after use
        defer {
            apiKey = String(repeating: "\0", count: apiKey.count)
        }

        let url = URL(string: "https://api.openai.com/v1/chat/completions")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30  // 30s timeout

        let body: [String: Any] = [
            "model": "gpt-4o",
            "messages": [
                ["role": "user", "content": prompt]
            ],
            "max_tokens": 1024
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        // Use session with timeout
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        let session = URLSession(configuration: config)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NSError(domain: "Junona", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "Не удалось получить ответ"
            ])
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let choices = json["choices"] as? [[String: Any]],
              let firstChoice = choices.first,
              let message = firstChoice["message"] as? [String: Any],
              let content = message["content"] as? String else {
            throw NSError(domain: "Junona", code: -2, userInfo: [
                NSLocalizedDescriptionKey: "Не удалось получить ответ"
            ])
        }

        return content
    }

    private func getAPIKey(service: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: "montana",
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let key = String(data: data, encoding: .utf8) else {
            return nil
        }

        return key
    }

    // MARK: - Session Management

    private func loadSessions() {
        // TODO: Load from UserDefaults or file
        sessions = []
    }

    private func newSession() {
        let session = JunonaSession(
            title: "Новый чат",
            timestamp: Date(),
            messages: []
        )
        sessions.insert(session, at: 0)
        currentSessionId = session.id
        messages = []
        withAnimation {
            showSidebar = false
        }
    }

    private func loadSession(_ session: JunonaSession) {
        currentSessionId = session.id
        messages = session.messages
        withAnimation {
            showSidebar = false
        }
    }

    // MARK: - Activity Tracking

    private func startActivityTracking() {
        activeStartTime = Date()

        // Check every minute if 10 minutes passed
        activityTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { _ in
            checkAndActivateJunona()
        }
    }

    private func stopActivityTracking() {
        activityTimer?.invalidate()
        activityTimer = nil
        activeStartTime = nil
    }

    private func checkAndActivateJunona() {
        guard let startTime = activeStartTime, hasMessages else { return }

        let elapsed = Date().timeIntervalSince(startTime)

        // Activate Junona sensor if window active >10 minutes AND user sent messages
        if elapsed >= 600 {  // 600 seconds = 10 minutes
            engine.activateJunona()
        }
    }
}

// MARK: - Supporting Views

struct NavItem: View {
    let icon: String
    let label: String
    let tag: Int

    var body: some View {
        Button(action: {
            NotificationCenter.default.post(
                name: .switchToTab,
                object: nil,
                userInfo: ["tab": tag]
            )
        }) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))
                    .frame(width: 20)

                Text(label)
                    .font(.callout)
                    .foregroundColor(.primary)

                Spacer()
            }
            .padding(.vertical, 6)
            .padding(.horizontal, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(Color.gray.opacity(0.0))
        )
        .onHover { hovering in
            if hovering {
                NSCursor.pointingHand.push()
            } else {
                NSCursor.pop()
            }
        }
    }
}

struct SessionItem: View {
    let session: JunonaSession
    let isCurrent: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: "message.fill")
                    .font(.system(size: 12))
                    .foregroundColor(isCurrent ? Color(red: 0.0, green: 0.83, blue: 1.0) : .secondary)

                VStack(alignment: .leading, spacing: 2) {
                    Text(session.title)
                        .font(.caption)
                        .fontWeight(isCurrent ? .semibold : .regular)
                        .foregroundColor(isCurrent ? .primary : .secondary)
                        .lineLimit(1)

                    Text(session.timestamp, style: .relative)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
            .padding(.vertical, 6)
            .padding(.horizontal, 12)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(isCurrent ? Color(red: 0.0, green: 0.83, blue: 1.0).opacity(0.1) : Color.clear)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Supporting Views

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if message.role == .assistant {
                // Junona avatar
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 0.0, green: 0.83, blue: 1.0),   // #00d4ff cyan
                                Color(red: 0.48, green: 0.18, blue: 1.0)   // #7b2fff purple
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 32, height: 32)
                    .overlay(
                        Text("Ю")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.white)
                    )
            }

            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                Text(message.content)
                    .padding(10)
                    .background(message.role == .user ? Color.blue : Color.gray.opacity(0.1))
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .cornerRadius(12)

                HStack(spacing: 4) {
                    Text(message.timestamp, style: .time)
                    if let model = message.aiModel {
                        Text("•")
                        Text(model)
                    }
                }
                .font(.caption2)
                .foregroundColor(.secondary)
            }

            if message.role == .user {
                Spacer()
            }
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 8) {
            Text(icon)
                .font(.body)
            Text(text)
                .font(.callout)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Models

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: MessageRole
    let content: String
    let timestamp: Date
    var aiModel: String?

    enum MessageRole {
        case user
        case assistant
    }
}

struct JunonaSession: Identifiable {
    let id = UUID()
    var title: String
    let timestamp: Date
    var messages: [ChatMessage]
}

// MARK: - Preview

#Preview {
    JunonaView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
