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

    // Clock seconds hand animation
    @State private var secondsAngle: Double = 0
    @State private var clockTimer: Timer?

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

            // Junona logo
            if let logoPath = Bundle.main.path(forResource: "JunonaLogo", ofType: "jpg"),
               let nsImage = NSImage(contentsOfFile: logoPath) {
                Image(nsImage: nsImage)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: 40, height: 40)
                    .clipShape(Circle())
                    .overlay(
                        Circle()
                            .stroke(
                                LinearGradient(
                                    colors: [
                                        Color(red: 0.83, green: 0.69, blue: 0.22),  // gold
                                        Color(red: 0.94, green: 0.82, blue: 0.38)   // goldLight
                                    ],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ),
                                lineWidth: 2
                            )
                    )
            } else {
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
                    .frame(width: 40, height: 40)
                    .overlay(
                        Text("Ю")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.white)
                    )
            }

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
                if let logoPath = Bundle.main.path(forResource: "JunonaLogo", ofType: "jpg"),
                   let nsImage = NSImage(contentsOfFile: logoPath) {
                    Image(nsImage: nsImage)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 32, height: 32)
                        .clipShape(Circle())
                        .overlay(
                            Circle()
                                .stroke(
                                    LinearGradient(
                                        colors: [
                                            Color(red: 0.83, green: 0.69, blue: 0.22),
                                            Color(red: 0.94, green: 0.82, blue: 0.38)
                                        ],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    ),
                                    lineWidth: 1.5
                                )
                        )
                } else {
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
                }

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

                    // Приложения
                    appsNavigation

                    Divider()

                    // Обмен
                    exchangeNavigation

                    Divider()

                    // Приват
                    privateNavigation

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

    private var appsNavigation: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Приложения")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            VStack(spacing: 4) {
                AppItem(icon: "shippingbox.fill", label: "SeaFare Montana", url: "https://efir.org/seafare")
                AppItem(icon: "hammer.fill", label: "Аукцион", url: "https://efir.org/auction")
            }
        }
    }

    private var exchangeNavigation: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Обмен")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            VStack(spacing: 4) {
                ExchangeItem(icon: "bitcoinsign.circle.fill", label: "BTC → Ɉ")
                ExchangeItem(icon: "dollarsign.circle.fill", label: "USD → Ɉ")
                ExchangeItem(icon: "rublesign.circle.fill", label: "RUB → Ɉ")
            }
        }
    }

    private var privateNavigation: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Приват")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)

            VStack(spacing: 4) {
                NavItem(icon: "eye.slash.fill", label: "Приватный кошелёк", tag: 10)
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
        VStack(spacing: 16) {
            Spacer()

            // Balance + Weight info (top)
            HStack(spacing: 12) {
                // Balance
                let formatter = NumberFormatter()
                let _ = {
                    formatter.numberStyle = .decimal
                    formatter.groupingSeparator = ","
                }()
                let balanceStr = formatter.string(from: NSNumber(value: engine.displayBalance)) ?? "\(engine.displayBalance)"

                Text(balanceStr)
                    .font(.system(size: 32, weight: .bold, design: .monospaced))
                    .foregroundColor(Color(red: 0.83, green: 0.69, blue: 0.22))

                Text("Ɉ")
                    .font(.system(size: 32, weight: .bold))
                    .foregroundColor(Color(red: 0.94, green: 0.82, blue: 0.38))

                // Weight
                Text("x\(engine.weight)")
                    .font(.system(size: 24, weight: .semibold, design: .monospaced))
                    .foregroundColor(.secondary)
            }

            // Static Junona clock
            ZStack {
                // Static Junona logo (center)
                if let junonaPath = Bundle.main.path(forResource: "JunonaLogo", ofType: "jpg"),
                   let junonaImage = NSImage(contentsOfFile: junonaPath) {
                    Image(nsImage: junonaImage)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 200, height: 200)
                        .clipShape(Circle())
                        .overlay(
                            Circle()
                                .stroke(
                                    LinearGradient(
                                        colors: [
                                            Color(red: 0.83, green: 0.69, blue: 0.22),
                                            Color(red: 0.94, green: 0.82, blue: 0.38)
                                        ],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    ),
                                    lineWidth: 3
                                )
                        )
                        .shadow(color: Color(red: 0.83, green: 0.69, blue: 0.22).opacity(0.3), radius: 20, x: 0, y: 10)
                }

                // Golden dot traveling around the edge
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 0.83, green: 0.69, blue: 0.22),
                                Color(red: 0.94, green: 0.82, blue: 0.38)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 12, height: 12)
                    .offset(
                        x: 100 * cos((secondsAngle - 90) * .pi / 180),
                        y: 100 * sin((secondsAngle - 90) * .pi / 180)
                    )
                    .shadow(color: Color(red: 0.94, green: 0.82, blue: 0.38), radius: 8)
            }
            .frame(width: 220, height: 220)
            .onAppear {
                startClock()
            }
            .onDisappear {
                stopClock()
            }

            VStack(spacing: 12) {
                Text("Добро пожаловать в Junona")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(Color(red: 0.91, green: 0.88, blue: 0.82))  // textBeige

                Text("Montana Protocol AI Assistant")
                    .font(.system(size: 16))
                    .foregroundColor(.secondary)

                Divider()
                    .padding(.vertical, 8)

                VStack(alignment: .leading, spacing: 8) {
                    FeatureRow(icon: "brain.head.profile", text: "Dual-AI система (Claude + GPT)")
                    FeatureRow(icon: "shield.fill", text: "Безопасность и конфиденциальность")
                    FeatureRow(icon: "network", text: "Управление Montana Protocol")
                    FeatureRow(icon: "lightbulb.fill", text: "Обучение и помощь 24/7")
                }
                .padding()
                .background(Color(red: 0.83, green: 0.69, blue: 0.22).opacity(0.05))
                .cornerRadius(16)
            }
            .frame(maxWidth: 500)

            Spacer()
        }
        .frame(maxWidth: .infinity)
        .padding()
    }

    // MARK: - Input Area

    private var inputArea: some View {
        VStack(spacing: 4) {
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

            // Subtle greeting
            Text("Управляет всей Montana Protocol")
                .font(.caption2)
                .foregroundColor(.secondary.opacity(0.7))
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.top, 2)
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
        // Use Montana API (efir.org) instead of direct Claude/GPT calls
        return try await callMontanaAPI(question: question)
    }

    private func callMontanaAPI(question: String) async throws -> String {
        let url = URL(string: "https://efir.org/api/chat")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30

        // Get user context
        let userContext = """
        Контекст: кошелёк \((engine.address ?? "").isEmpty ? "не создан" : "создан"), \
        вес майнинга x\(engine.weight), \
        майнинг \(engine.isTracking ? "активен" : "не активен")
        """

        let body: [String: Any] = [
            "question": question,
            "lang": "ru",
            "context": userContext
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

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
              let answer = json["answer"] as? String else {
            throw NSError(domain: "Junona", code: -2, userInfo: [
                NSLocalizedDescriptionKey: "Не удалось получить ответ"
            ])
        }

        return answer
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

    // MARK: - Clock Animation

    private func startClock() {
        // Set initial position to current time
        let currentSecond = Calendar.current.component(.second, from: Date())
        secondsAngle = Double(currentSecond) * 6  // 0-59 seconds → 0-354°

        // Update dot position every second based on real time
        clockTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [self] _ in
            let second = Calendar.current.component(.second, from: Date())
            withAnimation(.linear(duration: 1.0)) {
                secondsAngle = Double(second) * 6  // 360° / 60 seconds = 6° per second
            }
        }
    }

    private func stopClock() {
        clockTimer?.invalidate()
        clockTimer = nil
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

struct AppItem: View {
    let icon: String
    let label: String
    let url: String

    var body: some View {
        Button(action: {
            if let appUrl = URL(string: url) {
                NSWorkspace.shared.open(appUrl)
            }
        }) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundColor(Color(red: 0.48, green: 0.18, blue: 1.0))
                    .frame(width: 20)

                Text(label)
                    .font(.callout)
                    .foregroundColor(.primary)

                Spacer()

                Image(systemName: "arrow.up.right")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 6)
            .padding(.horizontal, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            if hovering {
                NSCursor.pointingHand.push()
            } else {
                NSCursor.pop()
            }
        }
    }
}

struct ExchangeItem: View {
    let icon: String
    let label: String

    var body: some View {
        Button(action: {
            // TODO: Open exchange view/dialog
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

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if message.role == .assistant {
                // Junona avatar
                if let logoPath = Bundle.main.path(forResource: "JunonaLogo", ofType: "jpg"),
                   let nsImage = NSImage(contentsOfFile: logoPath) {
                    Image(nsImage: nsImage)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 32, height: 32)
                        .clipShape(Circle())
                        .overlay(
                            Circle()
                                .stroke(
                                    LinearGradient(
                                        colors: [
                                            Color(red: 0.83, green: 0.69, blue: 0.22),
                                            Color(red: 0.94, green: 0.82, blue: 0.38)
                                        ],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    ),
                                    lineWidth: 1
                                )
                        )
                } else {
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
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(.white)
                        )
                }
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
