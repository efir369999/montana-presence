//
//  CognitiveKeyView.swift
//  Junona — Montana Messenger
//
//  Montana Native Auth — Когнитивный Ключ
//  "Ключи — это мысли. Подпись — это стиль мышления."
//

import SwiftUI
import MontanaCore

struct CognitiveKeyView: View {
    @ObservedObject private var auth = AuthService.shared
    @ObservedObject private var biometricAuth = BiometricAuth.shared
    @ObservedObject private var passkey = PasskeyService.shared
    @State private var cognitiveKey = ""
    @State private var isRestoring = false
    @State private var showConfirmation = false
    @State private var generatedAddress = ""
    @State private var keyboardHeight: CGFloat = 0
    @FocusState private var keyFocused: Bool

    // Начальный экран выбора
    @State private var showChoiceScreen = true
    @State private var hasAttemptedAutoFaceID = false

    // Multi-step confirmation flow
    @State private var confirmationStep: ConfirmationStep = .showKey
    @State private var keyCopied = false
    @State private var isSettingUpBiometric = false
    @State private var clipboardTimer: Timer?
    @State private var clipboardCountdown = 0
    @State private var showPinSetup = false

    enum ConfirmationStep {
        case showKey      // Step 1: Show key with copy button
        case warning      // Step 2: Warning about backup
        case biometric    // Step 3: Setup Face ID/PIN
    }

    // Валидация когнитивного ключа
    private var validation: CognitiveKeyValidation {
        auth.validateCognitiveKey(cognitiveKey)
    }

    private var isValid: Bool {
        validation.isValid
    }

    // Entropy UI helpers
    private var entropyColor: Color {
        switch validation.entropyLevel {
        case .weak: return .red
        case .medium: return .orange
        case .strong: return MontanaTheme.success
        case .excellent: return MontanaTheme.primary
        }
    }

    private var entropyIcon: String {
        switch validation.entropyLevel {
        case .weak: return "exclamationmark.triangle.fill"
        case .medium: return "shield.fill"
        case .strong: return "checkmark.shield.fill"
        case .excellent: return "lock.shield.fill"
        }
    }

    private var entropyPercent: Double {
        (validation.entropyBits / 248.0) * 100.0
    }

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                MontanaTheme.background
                    .ignoresSafeArea()

                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 0) {
                            // Content
                            if showChoiceScreen {
                                choiceScreenView
                            } else if showConfirmation {
                                confirmationView
                            } else if case .creatingKeys = auth.state {
                                creatingKeysView
                            } else if case .restoringIdentity = auth.state {
                                restoringView
                            } else {
                                cognitiveKeyInputView
                            }

                            // Padding for keyboard
                            Spacer()
                                .frame(height: keyboardHeight > 0 ? keyboardHeight : 20)
                                .id("bottom")
                        }
                        .padding(.horizontal, 24)
                        .padding(.top, 20)
                    }
                    .scrollDismissesKeyboard(.interactively)
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillShowNotification)) { notification in
            if let keyboardFrame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect {
                withAnimation(.easeOut(duration: 0.25)) {
                    keyboardHeight = keyboardFrame.height
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
            withAnimation(.easeOut(duration: 0.25)) {
                keyboardHeight = 0
            }
        }
        .onChange(of: auth.state) { _, newState in
            if case .authorized = newState {
                showConfirmation = false
                // SECURITY: Clear sensitive data from memory
                clearSensitiveData()
            }
        }
        .onDisappear {
            // SECURITY: Clear clipboard and memory on view disappear
            clearSensitiveData()
        }
        .task {
            // Авто-запуск Face ID ТОЛЬКО на начальном экране выбора
            // ⚠️ SECURITY: НЕ запускать если юзер выбрал "Восстановить" —
            // иначе Face ID авторизует старыми ключами, игнорируя новый когнитивный ключ
            if showChoiceScreen && !hasAttemptedAutoFaceID && auth.canAuthenticateWithPasskey() {
                hasAttemptedAutoFaceID = true
                // Небольшая задержка для UI
                try? await Task.sleep(nanoseconds: 300_000_000)
                if let _ = await auth.authenticateWithPasskey() {
                    // Успех — state станет .authorized, переключимся на WalletView
                }
            }
        }
    }

    // MARK: - Security

    /// Clear all sensitive data from memory and clipboard
    private func clearSensitiveData() {
        // Stop and clear clipboard timer
        clipboardTimer?.invalidate()
        clipboardTimer = nil

        // Clear clipboard if it contains our key
        let clipboard = UIPasteboard.general.string ?? ""
        if clipboard == cognitiveKey || clipboard.contains(cognitiveKey) {
            UIPasteboard.general.string = ""
        }

        // Clear cognitive key from memory
        cognitiveKey = ""
        clipboardCountdown = 0
    }

    // MARK: - Choice Screen (Создать / Восстановить)

    private var choiceScreenView: some View {
        VStack(spacing: 32) {
            Spacer()

            // Логотип
            VStack(spacing: 16) {
                Image("MontanaLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 100, height: 100)
                    .clipShape(Circle())
                    .shadow(color: Color(hex: "D4AF37").opacity(0.4), radius: 16)

                Text("Монтана")
                    .font(.system(size: 32, weight: .light))
                    .foregroundColor(.white)

                Text("Время — единственная реальная валюта")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Passkey login (Face ID / Touch ID)
            if auth.canAuthenticateWithPasskey() {
                Button {
                    Task {
                        if let _ = await auth.authenticateWithPasskey() {
                            // Success - auth state will change to .authorized
                        }
                    }
                } label: {
                    HStack {
                        Image(systemName: "faceid")
                            .font(.title)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Войти с Face ID")
                                .fontWeight(.semibold)
                            Text("Быстрый вход")
                                .font(.caption)
                                .opacity(0.8)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity)
                    .background(
                        LinearGradient(
                            colors: [Color(hex: "D4AF37"), Color(hex: "B8860B")],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(16)
                    .foregroundColor(.black)
                }
                .padding(.bottom, 8)
            }

            // Кнопки выбора
            VStack(spacing: 16) {
                // Создать идентичность
                Button {
                    isRestoring = false
                    showChoiceScreen = false
                } label: {
                    HStack {
                        Image(systemName: "person.badge.plus")
                            .font(.title2)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Создать идентичность")
                                .fontWeight(.semibold)
                            Text("Новый когнитивный ключ")
                                .font(.caption)
                                .opacity(0.8)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity)
                    .background(
                        LinearGradient(
                            colors: [MontanaTheme.primary, MontanaTheme.secondary],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(16)
                    .foregroundColor(.white)
                }

                // Восстановить
                Button {
                    isRestoring = true
                    showChoiceScreen = false
                } label: {
                    HStack {
                        Image(systemName: "arrow.counterclockwise")
                            .font(.title2)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Восстановить")
                                .fontWeight(.semibold)
                            Text("Уже есть ключи на устройстве")
                                .font(.caption)
                                .opacity(0.8)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity)
                    .background(MontanaTheme.cardBackground)
                    .cornerRadius(16)
                    .foregroundColor(.white)
                }
            }

            Spacer()

            // Footer с правовой информацией и версией
            VStack(spacing: 12) {
                // Ссылки
                HStack(spacing: 16) {
                    Link(destination: URL(string: "https://1394793-cy33234.tw1.ru/")!) {
                        Text("1394793-cy33234.tw1.ru")
                            .font(.caption2)
                            .foregroundColor(MontanaTheme.primary)
                    }

                    Link(destination: URL(string: "https://1394793-cy33234.tw1.ru/privacy.html")!) {
                        Text("Конфиденциальность")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }

                // Криптография
                Text("ML-DSA-65 · FIPS 204 · Постквантовая криптография")
                    .font(.caption2)
                    .foregroundColor(.secondary)

                // Версия и сборка
                Text("Версия \(Montana.version) (\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"))")
                    .font(.caption2)
                    .foregroundColor(.secondary.opacity(0.7))
            }
            .padding(.bottom, 20)
        }
        .padding(.horizontal, 24)
    }

    // MARK: - Cognitive Key Input

    private var cognitiveKeyInputView: some View {
        VStack(spacing: 24) {
            // Логотип пирамиды Montana
            VStack(spacing: 16) {
                Image("MontanaLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 80, height: 80)
                    .clipShape(Circle())
                    .shadow(color: Color(hex: "D4AF37").opacity(0.4), radius: 12)

                Text("Монтана")
                    .font(.system(size: 24, weight: .light))
                    .foregroundColor(.white)
            }

            // Заголовок и описание — это и есть вопрос/требование
            VStack(spacing: 8) {
                Text(isRestoring ? "Восстановление" : "Один вопрос памяти")
                    .font(.headline)
                    .foregroundColor(.white)

                Text(isRestoring
                    ? "Введи свой когнитивный ключ"
                    : "Напиши то, что знаешь только ты.\nЧтобы осознавание ключа было только твоё.\nКак мысль в заметке — ничего не значащая на первый взгляд.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            // Text Editor
            VStack(alignment: .leading, spacing: 8) {
                TextEditor(text: $cognitiveKey)
                    .frame(minHeight: 150)
                    .padding(12)
                    .background(MontanaTheme.cardBackground)
                    .cornerRadius(12)
                    .foregroundColor(.white)
                    .focused($keyFocused)
                    .scrollContentBackground(.hidden)

                // Progress bar — как кувшин, который наполняется
                VStack(alignment: .leading, spacing: 8) {
                    // Progress bar (всегда видна)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            // Пустой кувшин
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.gray.opacity(0.2))
                                .frame(height: 8)

                            // Наполнение
                            RoundedRectangle(cornerRadius: 4)
                                .fill(
                                    LinearGradient(
                                        colors: [entropyColor.opacity(0.8), entropyColor],
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    )
                                )
                                .frame(width: geo.size.width * min(entropyPercent / 100, 1.0), height: 8)
                                .animation(.easeOut(duration: 0.2), value: entropyPercent)
                        }
                    }
                    .frame(height: 8)

                    // Показатели под progress bar
                    HStack {
                        // Биты
                        Text("\(Int(validation.entropyBits)) / 248")
                            .foregroundColor(cognitiveKey.isEmpty ? .secondary : entropyColor)
                            .fontWeight(.medium)

                        Spacer()

                        // Слова · Символы
                        if !cognitiveKey.isEmpty {
                            Text("\(validation.wordCount) слов · \(validation.charCount) симв.")
                                .foregroundColor(.secondary)
                        } else {
                            Text("0 слов · 0 симв.")
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        // Статус
                        if isValid {
                            HStack(spacing: 4) {
                                Image(systemName: "checkmark.circle.fill")
                                Text("OK")
                            }
                            .foregroundColor(MontanaTheme.success)
                        } else if !cognitiveKey.isEmpty {
                            Text(validation.entropyLevel.rawValue)
                                .foregroundColor(entropyColor)
                        }
                    }
                    .font(.caption)
                }
            }


            // Error
            if let error = auth.error {
                Text(error)
                    .font(.caption)
                    .foregroundColor(MontanaTheme.error)
                    .multilineTextAlignment(.center)
            }

            // Action Button
            Button {
                keyFocused = false
                Task {
                    if isRestoring {
                        _ = await auth.restoreIdentity(cognitiveKey: cognitiveKey)
                    } else {
                        if let address = await auth.generateMontanaIdentity(cognitiveKey: cognitiveKey) {
                            generatedAddress = address
                            confirmationStep = .showKey
                            keyCopied = false
                            showConfirmation = true
                        }
                    }
                }
            } label: {
                Text(isRestoring ? "Восстановить" : "Создать идентичность")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(isValid ? MontanaTheme.primary : MontanaTheme.primary.opacity(0.5))
                    .cornerRadius(12)
                    .foregroundColor(.white)
                    .fontWeight(.semibold)
            }
            .disabled(!isValid)

            // Назад к выбору
            Button {
                cognitiveKey = ""
                auth.error = nil
                showChoiceScreen = true
            } label: {
                HStack {
                    Image(systemName: "chevron.left")
                    Text("Назад")
                }
                .font(.subheadline)
                .foregroundColor(MontanaTheme.primary)
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Готово") {
                    keyFocused = false
                }
            }
        }
    }

    // MARK: - Confirmation View (Warning + Copy)

    private var confirmationView: some View {
        VStack(spacing: 20) {
            // Предупреждение
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40))
                .foregroundColor(MontanaTheme.warning)

            VStack(spacing: 8) {
                Text("Сохрани когнитивный ключ")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(.white)

                Text("Это ЕДИНСТВЕННЫЙ способ восстановить кошелёк.\nМы НЕ храним твой ключ — только ты.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            // Показываем сам ключ
            VStack(alignment: .leading, spacing: 8) {
                Text("Твой когнитивный ключ:")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Text(cognitiveKey)
                    .font(.system(size: 14, design: .monospaced))
                    .foregroundColor(.white)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.black.opacity(0.3))
                    .cornerRadius(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(MontanaTheme.primary.opacity(0.3), lineWidth: 1)
                    )
                    .textSelection(.enabled)
            }

            // Условия
            VStack(alignment: .leading, spacing: 4) {
                Label("Запомни или запиши в безопасном месте", systemImage: "brain.head.profile")
                Label("Тот же ключ = тот же кошелёк, всегда", systemImage: "key.fill")
                Label("Потеряешь ключ = потеряешь доступ навсегда", systemImage: "exclamationmark.shield")
            }
            .font(.caption2)
            .foregroundColor(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(MontanaTheme.cardBackground.opacity(0.5))
            .cornerRadius(8)

            // Кнопка копирования
            Button {
                UIPasteboard.general.string = cognitiveKey
                keyCopied = true
                clipboardCountdown = 30

                let generator = UIImpactFeedbackGenerator(style: .medium)
                generator.impactOccurred()

                // Auto-clear clipboard
                clipboardTimer?.invalidate()
                clipboardTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { timer in
                    DispatchQueue.main.async {
                        clipboardCountdown -= 1
                        if clipboardCountdown <= 0 {
                            UIPasteboard.general.string = ""
                            timer.invalidate()
                            clipboardTimer = nil
                        }
                    }
                }
            } label: {
                HStack {
                    Image(systemName: keyCopied ? "checkmark" : "doc.on.doc")
                    if keyCopied && clipboardCountdown > 0 {
                        Text("Скопировано · \(clipboardCountdown)с")
                    } else {
                        Text("Скопировать ключ")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(keyCopied ? MontanaTheme.success : MontanaTheme.cardBackground)
                .cornerRadius(12)
                .foregroundColor(.white)
                .fontWeight(.semibold)
            }

            // Passkey (Face ID) — следующий шаг
            if keyCopied && passkey.isPasskeyAvailable {
                VStack(spacing: 8) {
                    Divider()
                        .background(Color.white.opacity(0.2))

                    HStack(spacing: 12) {
                        Image(systemName: "faceid")
                            .font(.title2)
                            .foregroundColor(Color(hex: "D4AF37"))

                        VStack(alignment: .leading, spacing: 2) {
                            Text("Включить Face ID?")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                            Text("Быстрый вход без ввода ключа")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        Toggle("", isOn: .constant(true))
                            .labelsHidden()
                            .tint(Color(hex: "D4AF37"))
                    }
                    .padding(12)
                    .background(MontanaTheme.cardBackground)
                    .cornerRadius(10)

                    Text("Когнитивный ключ — для восстановления на другом устройстве.\nFace ID — для быстрого входа на этом устройстве.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
            }

            // Защитить PIN и войти
            Button {
                showPinSetup = true
            } label: {
                HStack {
                    Image(systemName: "lock.fill")
                    Text("Установить PIN и войти")
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(keyCopied ? MontanaTheme.primary : Color.gray.opacity(0.3))
                .cornerRadius(12)
                .foregroundColor(.white)
                .fontWeight(.semibold)
            }
            .disabled(!keyCopied)
            .sheet(isPresented: $showPinSetup) {
                SetPinView(seed: cognitiveKey) {
                    // PIN set successfully - now authorize
                    Task {
                        if let address = auth.currentUser?.address {
                            await auth.createPasskeyIfAvailable(for: address)
                        }
                        auth.state = .authorized
                    }
                }
            }
        }
    }

    // MARK: - Creating Keys View

    private var creatingKeysView: some View {
        VStack(spacing: 24) {
            ProgressView()
                .scaleEffect(1.5)
                .tint(MontanaTheme.primary)

            Text("Генерация ключей...")
                .font(.headline)
                .foregroundColor(.white)

            VStack(spacing: 4) {
                Text("PBKDF2 · 600,000 итераций")
                Text("ML-DSA-65 · FIPS 204")
                Text("Постквантовая криптография")
            }
            .font(.caption)
            .foregroundColor(.secondary)
        }
    }

    // MARK: - Restoring View

    private var restoringView: some View {
        VStack(spacing: 24) {
            ProgressView()
                .scaleEffect(1.5)
                .tint(MontanaTheme.primary)

            Text("Восстановление...")
                .font(.headline)
                .foregroundColor(.white)

            Text("Проверяем когнитивный ключ на сервере")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Footer

    private var footerView: some View {
        VStack(spacing: 8) {
            Text("\"Ключи — это мысли.\"")
                .font(.caption2)
                .foregroundColor(.secondary)

            Text("\"Подпись — это стиль мышления.\"")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.bottom, 32)
    }
}

// MARK: - Theme Extensions

extension MontanaTheme {
    static var success: Color { Color.green }
    static var warning: Color { Color.orange }
}

#Preview {
    CognitiveKeyView()
}
