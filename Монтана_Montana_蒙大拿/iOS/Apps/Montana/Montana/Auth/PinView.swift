//
//  PinView.swift
//  Montana — Post-Quantum Wallet
//
//  PIN-код для защиты когнитивного ключа
//

import SwiftUI
import MontanaCore

// MARK: - PIN Mode

enum PinMode {
    case create      // Создание нового PIN
    case verify      // Проверка PIN для просмотра seed
    case change      // Смена PIN
}

// MARK: - PIN View

struct PinView: View {
    let mode: PinMode
    let onSuccess: (String) -> Void
    let onCancel: () -> Void

    @State private var pin = ""
    @State private var confirmPin = ""
    @State private var isConfirming = false
    @State private var error: String?
    @State private var shake = false
    @FocusState private var isInputFocused: Bool

    private let pinLength = 6

    var body: some View {
        VStack(spacing: 32) {
            // Header
            VStack(spacing: 8) {
                Image(systemName: mode == .create ? "lock.badge.plus" : "lock.fill")
                    .font(.system(size: 48))
                    .foregroundColor(MontanaTheme.primary)

                Text(headerText)
                    .font(.title2)
                    .fontWeight(.semibold)

                Text(subtitleText)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            // PIN Dots - тапни чтобы показать клавиатуру
            HStack(spacing: 16) {
                ForEach(0..<pinLength, id: \.self) { index in
                    Circle()
                        .fill(index < currentPin.count ? MontanaTheme.primary : Color.gray.opacity(0.3))
                        .frame(width: 16, height: 16)
                }
            }
            .modifier(ShakeEffect(shakes: shake ? 2 : 0))
            .onTapGesture {
                isInputFocused = true
            }

            // Error
            if let error = error {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
            }

            // Hidden TextField для нативной клавиатуры
            TextField("", text: isConfirming ? $confirmPin : $pin)
                .keyboardType(.numberPad)
                .focused($isInputFocused)
                .opacity(0)
                .frame(width: 1, height: 1)
                .onChange(of: pin) { _, newValue in
                    // Только цифры, максимум pinLength
                    let filtered = String(newValue.filter { $0.isNumber }.prefix(pinLength))
                    if filtered != newValue {
                        pin = filtered
                    }
                    if pin.count == pinLength && !isConfirming {
                        handlePinComplete()
                    }
                }
                .onChange(of: confirmPin) { _, newValue in
                    // Только цифры, максимум pinLength
                    let filtered = String(newValue.filter { $0.isNumber }.prefix(pinLength))
                    if filtered != newValue {
                        confirmPin = filtered
                    }
                    if confirmPin.count == pinLength && isConfirming {
                        checkConfirmation()
                    }
                }

            Spacer()

            // Cancel button
            Button {
                onCancel()
            } label: {
                Text("Отмена")
                    .foregroundColor(.secondary)
                    .padding()
            }
            .padding(.bottom, 32)
        }
        .padding()
        .onAppear {
            // Автоматически показать клавиатуру
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                isInputFocused = true
            }
        }
    }

    // MARK: - Computed Properties

    private var currentPin: String {
        isConfirming ? confirmPin : pin
    }

    private var headerText: String {
        switch mode {
        case .create:
            return isConfirming ? "Подтвердите PIN" : "Создайте PIN"
        case .verify:
            return "Введите PIN"
        case .change:
            return isConfirming ? "Новый PIN" : "Текущий PIN"
        }
    }

    private var subtitleText: String {
        switch mode {
        case .create:
            return "PIN защитит ваш когнитивный ключ"
        case .verify:
            return "Для просмотра Recovery Phrase"
        case .change:
            return isConfirming ? "Введите новый PIN" : "Введите текущий PIN"
        }
    }

    // MARK: - Actions

    private func appendDigit(_ digit: String) {
        error = nil

        if isConfirming {
            guard confirmPin.count < pinLength else { return }
            confirmPin += digit
            if confirmPin.count == pinLength {
                checkConfirmation()
            }
        } else {
            guard pin.count < pinLength else { return }
            pin += digit
            if pin.count == pinLength {
                handlePinComplete()
            }
        }
    }

    private func deleteDigit() {
        if isConfirming {
            guard !confirmPin.isEmpty else { return }
            confirmPin.removeLast()
        } else {
            guard !pin.isEmpty else { return }
            pin.removeLast()
        }
    }

    private func handlePinComplete() {
        switch mode {
        case .create:
            // Move to confirmation
            isConfirming = true
        case .verify:
            // Verify PIN
            if KeychainManager.shared.verifyPin(pin) {
                onSuccess(pin)
            } else {
                showError("Неверный PIN")
            }
        case .change:
            if !isConfirming {
                // Verify current PIN first
                if KeychainManager.shared.verifyPin(pin) {
                    isConfirming = true
                } else {
                    showError("Неверный PIN")
                }
            }
        }
    }

    private func checkConfirmation() {
        if pin == confirmPin {
            onSuccess(pin)
        } else {
            showError("PIN не совпадает")
            confirmPin = ""
            isConfirming = false
            pin = ""
        }
    }

    private func showError(_ message: String) {
        error = message
        withAnimation(.default) {
            shake = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            shake = false
            if mode == .verify {
                pin = ""
            }
        }
    }
}

// MARK: - PIN Button

struct PinButton: View {
    let digit: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(digit)
                .font(.title)
                .fontWeight(.medium)
                .foregroundColor(.primary)
                .frame(width: 72, height: 72)
                .background(Color.gray.opacity(0.1))
                .clipShape(Circle())
        }
    }
}

// MARK: - Shake Effect

struct ShakeEffect: GeometryEffect {
    var shakes: CGFloat

    var animatableData: CGFloat {
        get { shakes }
        set { shakes = newValue }
    }

    func effectValue(size: CGSize) -> ProjectionTransform {
        ProjectionTransform(CGAffineTransform(
            translationX: 10 * sin(shakes * .pi * 2),
            y: 0
        ))
    }
}

// MARK: - Recovery Phrase View (PIN Protected)

struct RecoveryPhraseView: View {
    @Environment(\.dismiss) var dismiss
    @State private var showingPin = true
    @State private var recoveryPhrase: String?
    @State private var copied = false

    var body: some View {
        NavigationStack {
            Group {
                if showingPin {
                    PinView(
                        mode: .verify,
                        onSuccess: { pin in
                            if let seed = KeychainManager.shared.loadSeed(pin: pin) {
                                recoveryPhrase = seed
                                showingPin = false
                            }
                        },
                        onCancel: {
                            dismiss()
                        }
                    )
                } else if let phrase = recoveryPhrase {
                    ScrollView {
                        VStack(spacing: 24) {
                            // Warning
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.orange)
                                Text("Никому не показывайте!")
                                    .font(.headline)
                            }
                            .padding()
                            .background(Color.orange.opacity(0.1))
                            .cornerRadius(12)

                            // Phrase
                            Text(phrase)
                                .font(.system(.body, design: .monospaced))
                                .padding()
                                .background(Color.gray.opacity(0.1))
                                .cornerRadius(12)
                                .textSelection(.enabled)

                            // Copy button
                            Button {
                                UIPasteboard.general.string = phrase
                                copied = true
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                    copied = false
                                }
                            } label: {
                                HStack {
                                    Image(systemName: copied ? "checkmark" : "doc.on.doc")
                                    Text(copied ? "Скопировано" : "Копировать")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(MontanaTheme.primary)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                            }

                            Text("Этот когнитивный ключ — единственный способ восстановить кошелёк. Запишите его и храните в безопасном месте.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Когнитивный ключ")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Готово") {
                        dismiss()
                    }
                }
            }
        }
    }
}

// MARK: - Set PIN View

struct SetPinView: View {
    @Environment(\.dismiss) var dismiss
    let seed: String
    let onComplete: () -> Void

    @State private var pinSet = false

    var body: some View {
        NavigationStack {
            PinView(
                mode: .create,
                onSuccess: { pin in
                    if KeychainManager.shared.saveSeed(seed, pin: pin) {
                        pinSet = true
                        onComplete()
                        dismiss()
                    }
                },
                onCancel: {
                    dismiss()
                }
            )
            .navigationTitle("Защита PIN")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Setup PIN From Settings View

struct SetupPinFromSettingsView: View {
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            PinView(
                mode: .create,
                onSuccess: { pin in
                    // Сохраняем PIN хеш для верификации
                    // Когнитивный ключ уже в Keychain если был сохранён при создании
                    KeychainManager.shared.savePinOnly(pin)
                    dismiss()
                },
                onCancel: {
                    dismiss()
                }
            )
            .navigationTitle("Установка PIN")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Change PIN View

struct ChangePinView: View {
    @Environment(\.dismiss) var dismiss
    @State private var phase: ChangePhase = .verifyOld
    @State private var oldPin = ""
    @State private var newPin = ""

    enum ChangePhase {
        case verifyOld
        case createNew
    }

    var body: some View {
        NavigationStack {
            Group {
                switch phase {
                case .verifyOld:
                    PinView(
                        mode: .verify,
                        onSuccess: { pin in
                            oldPin = pin
                            phase = .createNew
                        },
                        onCancel: {
                            dismiss()
                        }
                    )
                case .createNew:
                    PinView(
                        mode: .create,
                        onSuccess: { pin in
                            // Load seed with old PIN, save with new PIN
                            if let seed = KeychainManager.shared.loadSeed(pin: oldPin) {
                                // Delete old PIN data
                                KeychainManager.shared.deleteSeed()
                                // Save with new PIN
                                if KeychainManager.shared.saveSeed(seed, pin: pin) {
                                    dismiss()
                                }
                            }
                        },
                        onCancel: {
                            dismiss()
                        }
                    )
                }
            }
            .navigationTitle(phase == .verifyOld ? "Текущий PIN" : "Новый PIN")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Create Identity View

struct CreateIdentityView: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var auth = AuthService.shared
    @State private var cognitiveKey = ""
    @State private var isCreating = false
    @State private var showSuccess = false
    @State private var newAddress = ""
    @FocusState private var keyFocused: Bool
    let onComplete: () -> Void

    private var existingWalletCount: Int {
        KeychainManager.shared.walletCount
    }

    private var isValid: Bool {
        let words = cognitiveKey.split(separator: " ").count
        let chars = cognitiveKey.count
        return words >= 24 || chars >= 150
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Header
                Image(systemName: "wallet.pass.fill")
                    .font(.system(size: 48))
                    .foregroundColor(Color(hex: "D4AF37"))

                Text("Добавить кошелёк")
                    .font(.title2)
                    .fontWeight(.semibold)

                if existingWalletCount > 0 {
                    HStack {
                        Image(systemName: "checkmark.shield.fill")
                            .foregroundColor(.green)
                        Text("Существующие \(existingWalletCount) кошелёк(ов) сохранятся")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                // Cognitive key input
                VStack(alignment: .leading, spacing: 8) {
                    Text("Когнитивный ключ")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    TextEditor(text: $cognitiveKey)
                        .focused($keyFocused)
                        .frame(height: 120)
                        .padding(12)
                        .background(Color.black.opacity(0.2))
                        .cornerRadius(12)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)

                    HStack {
                        let words = cognitiveKey.split(separator: " ").count
                        Text("\(words) слов · \(cognitiveKey.count) симв.")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        Spacer()

                        if isValid {
                            HStack(spacing: 4) {
                                Image(systemName: "checkmark.circle.fill")
                                Text("OK")
                            }
                            .foregroundColor(.green)
                            .font(.caption)
                        }
                    }
                }

                Text("Минимум 24 слова или 150 символов. Это ваш новый когнитивный ключ для нового кошелька.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)

                Spacer()

                // Action buttons
                VStack(spacing: 12) {
                    Button {
                        keyFocused = false
                        isCreating = true
                        Task {
                            await createNewWallet()
                        }
                    } label: {
                        HStack {
                            if isCreating {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            } else {
                                Image(systemName: "plus.circle.fill")
                            }
                            Text("Создать кошелёк")
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(isValid ? Color(hex: "D4AF37") : Color(hex: "D4AF37").opacity(0.5))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    .disabled(!isValid || isCreating)

                    Button {
                        dismiss()
                    } label: {
                        Text("Отмена")
                            .frame(maxWidth: .infinity)
                            .padding()
                    }
                }
            }
            .padding()
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Готово") {
                        keyFocused = false
                    }
                }
            }
            .sheet(isPresented: $showSuccess) {
                NewWalletSuccessView(address: newAddress) {
                    dismiss()
                    onComplete()
                }
            }
        }
        .navigationTitle("Новый кошелёк")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func createNewWallet() async {
        // Derive keys from cognitive key
        guard let keys = MontanaSeed.deriveKeypair(from: cognitiveKey) else {
            isCreating = false
            return
        }

        // Create new wallet (doesn't delete existing)
        if let newIndex = KeychainManager.shared.createNewWallet(privateKey: keys.privateKey, publicKey: keys.publicKey) {
            // Switch to new wallet
            _ = KeychainManager.shared.switchToWallet(newIndex)

            // Generate address for new wallet
            let address = MLDSA65.generateAddress(from: keys.publicKey)
            KeychainManager.shared.saveWalletAddress(address, forWallet: newIndex)

            // Update UserDefaults for new wallet
            UserDefaults.standard.set(address, forKey: "montana_address")
            UserDefaults.standard.removeObject(forKey: "montana_mt_number")
            UserDefaults.standard.removeObject(forKey: "montana_mt_id")

            // Store cognitive key for viewing later
            _ = PasskeyService.shared.storeCognitiveKey(cognitiveKey)

            // Clear input and show success
            newAddress = address
            cognitiveKey = ""
            showSuccess = true
        }

        isCreating = false
    }
}

// MARK: - New Wallet Success View

struct NewWalletSuccessView: View {
    let address: String
    let onDone: () -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 64))
                    .foregroundColor(.green)

                Text("Кошелёк создан!")
                    .font(.title2)
                    .fontWeight(.semibold)

                VStack(spacing: 8) {
                    Text("Адрес:")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    Text(address)
                        .font(.system(size: 12, design: .monospaced))
                        .multilineTextAlignment(.center)
                        .padding()
                        .background(Color.black.opacity(0.2))
                        .cornerRadius(8)
                }

                Text("Сохраните когнитивный ключ в надёжном месте. Это единственный способ восстановить доступ.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)

                Spacer()

                Button {
                    onDone()
                } label: {
                    Text("Готово")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(hex: "D4AF37"))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
            }
            .padding()
            .navigationTitle("Готово")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Restore Identity View

struct RestoreIdentityView: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var auth = AuthService.shared
    @State private var cognitiveKey = ""
    @State private var isRestoring = false
    @State private var showPinSetup = false
    @State private var error: String?
    let onComplete: () -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Image(systemName: "arrow.counterclockwise.circle.fill")
                        .font(.system(size: 48))
                        .foregroundColor(MontanaTheme.primary)

                    Text("Восстановить кошелёк")
                        .font(.title2)
                        .fontWeight(.semibold)

                    Text("Введите ваш когнитивный ключ")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                // Input field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Когнитивный ключ")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    TextEditor(text: $cognitiveKey)
                        .font(.system(.body, design: .monospaced))
                        .frame(minHeight: 120)
                        .padding(8)
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(12)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }

                if let error = error {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }

                Spacer()

                // Actions
                VStack(spacing: 12) {
                    Button {
                        restoreWallet()
                    } label: {
                        HStack {
                            if isRestoring {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            } else {
                                Image(systemName: "checkmark.circle.fill")
                            }
                            Text("Восстановить")
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(cognitiveKey.count >= 20 ? MontanaTheme.primary : Color.gray)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    .disabled(cognitiveKey.count < 20 || isRestoring)

                    Button {
                        dismiss()
                    } label: {
                        Text("Отмена")
                            .frame(maxWidth: .infinity)
                            .padding()
                    }
                }
            }
            .padding()
            .navigationTitle("Восстановление")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showPinSetup) {
                SetPinView(seed: cognitiveKey) {
                    dismiss()
                    onComplete()
                }
            }
        }
    }

    private func restoreWallet() {
        let trimmed = cognitiveKey.trimmingCharacters(in: .whitespacesAndNewlines)

        guard trimmed.count >= 20 else {
            error = "Когнитивный ключ слишком короткий"
            return
        }

        isRestoring = true
        error = nil

        Task {
            // Delete existing keys
            KeychainManager.shared.deleteAll()

            // Derive keys from cognitive key
            // This would normally call the key derivation service
            // For now, we just proceed to PIN setup
            await MainActor.run {
                isRestoring = false
                showPinSetup = true
            }
        }
    }
}

#Preview {
    PinView(mode: .create, onSuccess: { _ in }, onCancel: {})
        .preferredColorScheme(.dark)
}
