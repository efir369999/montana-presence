import SwiftUI

enum SendMethod: String, CaseIterable {
    case montanaID = "montanaID"
    case nickname = "nickname"
    case fullAddress = "fullAddress"

    var label: String {
        switch self {
        case .montanaID: return "Ɉ-ID"
        case .nickname: return "@ Ник"
        case .fullAddress: return "mt... Адрес"
        }
    }

    var placeholder: String {
        switch self {
        case .montanaID: return "1"
        case .nickname: return "@junomoneta"
        case .fullAddress: return "mt..."
        }
    }

    var icon: String {
        switch self {
        case .montanaID: return "person.text.rectangle"
        case .nickname: return "at"
        case .fullAddress: return "key.horizontal"
        }
    }
}

// Состояния экрана отправки
enum SendStep {
    case form           // ввод данных
    case preConfirm     // подтверждение перед отправкой
    case result         // результат
}

struct SendView: View {
    @EnvironmentObject var engine: PresenceEngine
    var onShowHistory: (() -> Void)? = nil

    @State private var step: SendStep = .form
    @State private var sendMethod: SendMethod = .montanaID
    @State private var recipient = ""
    @State private var amount = ""
    @State private var statusText = ""
    @State private var statusColor: Color = .secondary
    @State private var resolvedAddress = ""
    @State private var resolvedAlias = ""
    @State private var isSending = false
    @State private var sentAmount = 0
    @State private var sentRecipient = ""
    @State private var sentTimestamp = ""
    @FocusState private var recipientFocused: Bool
    @Environment(\.dismiss) private var dismiss

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let purple = Color(red: 0.48, green: 0.18, blue: 1)
    private let cardBg = Color(red: 0.09, green: 0.09, blue: 0.12)
    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)

    var body: some View {
        Group {
            switch step {
            case .form:
                sendFormView
            case .preConfirm:
                preConfirmView
            case .result:
                resultView
            }
        }
        .frame(width: 320, height: 440)
    }

    // ═══════════════════════════════════════════════════════════════════
    //  STEP 2: Подтверждение перед отправкой
    // ═══════════════════════════════════════════════════════════════════

    private var preConfirmView: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "exclamationmark.shield.fill")
                    .foregroundColor(gold)
                Text("Подтверждение")
                    .font(.system(size: 16, weight: .bold))
                Spacer()
                Button(action: { step = .form }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 16)

            Spacer()

            Text("Вы отправляете")
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .padding(.bottom, 6)

            Text(formatAmount(Int(amount) ?? 0))
                .font(.system(size: 28, weight: .bold, design: .monospaced))
                .foregroundColor(cyan)
                .padding(.bottom, 16)

            VStack(spacing: 10) {
                confirmRow(label: "Получатель", value: resolvedAlias.isEmpty ? displayAddr(resolvedAddress) : resolvedAlias)
                confirmRow(label: "Адрес", value: displayAddr(resolvedAddress))
            }
            .padding(14)
            .background(cardBg)
            .cornerRadius(10)
            .padding(.horizontal, 20)

            Spacer()

            if !statusText.isEmpty {
                Text(statusText)
                    .font(.system(size: 11))
                    .foregroundColor(statusColor)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 6)
            }

            // Подтвердить
            Button(action: { executeTransfer() }) {
                HStack(spacing: 8) {
                    if isSending {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Image(systemName: "checkmark.shield.fill")
                    }
                    Text("Подтвердить")
                        .font(.system(size: 14, weight: .bold))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .tint(gold)
            .controlSize(.large)
            .disabled(isSending)
            .padding(.horizontal, 16)
            .padding(.bottom, 8)

            // Назад
            Button(action: { step = .form }) {
                Text("Назад")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 14)
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  STEP 3: Результат — Готово + История
    // ═══════════════════════════════════════════════════════════════════

    private var resultView: some View {
        VStack(spacing: 0) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 48))
                .foregroundColor(.green)
                .padding(.bottom, 16)

            Text("Отправлено")
                .font(.system(size: 18, weight: .bold))
                .foregroundColor(.green)
                .padding(.bottom, 20)

            VStack(spacing: 12) {
                confirmRow(label: "Сумма", value: formatAmount(sentAmount))
                confirmRow(label: "Получатель", value: sentRecipient)
                confirmRow(label: "Время", value: sentTimestamp)
            }
            .padding(16)
            .background(cardBg)
            .cornerRadius(10)
            .padding(.horizontal, 24)

            Spacer()

            // История
            Button(action: {
                dismiss()
                onShowHistory?()
            }) {
                HStack(spacing: 6) {
                    Image(systemName: "clock.arrow.circlepath")
                    Text("Посмотреть историю")
                        .font(.system(size: 13, weight: .medium))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .tint(gold)
            .controlSize(.large)
            .padding(.horizontal, 16)
            .padding(.bottom, 8)

            // Готово
            Button(action: { dismiss() }) {
                Text("Готово")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 14)
        }
    }

    private func confirmRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 11))
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.system(size: 13, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  STEP 1: Форма ввода
    // ═══════════════════════════════════════════════════════════════════

    private var sendFormView: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "paperplane.fill")
                    .foregroundColor(cyan)
                Text("Ɉ Отправить")
                    .font(.system(size: 16, weight: .bold))
                Spacer()
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 10)

            // Balance card
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Доступно")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                    Text("\(formatAmount(engine.availableBalance))")
                        .font(.system(size: 18, weight: .bold, design: .monospaced))
                        .foregroundColor(cyan)
                }
                Spacer()
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(cardBg)
            .cornerRadius(8)
            .padding(.horizontal, 16)
            .padding(.bottom, 12)

            // Send method picker
            VStack(alignment: .leading, spacing: 6) {
                Text("Как отправить")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 16)

                HStack(spacing: 4) {
                    ForEach(SendMethod.allCases, id: \.self) { method in
                        methodButton(method)
                    }
                }
                .padding(.horizontal, 16)
            }
            .padding(.bottom, 10)

            // Recipient input
            VStack(spacing: 6) {
                HStack(spacing: 6) {
                    Image(systemName: sendMethod.icon)
                        .foregroundColor(cyan.opacity(0.6))
                        .font(.system(size: 12))
                        .frame(width: 20)

                    TextField(sendMethod.placeholder, text: $recipient)
                        .font(.system(size: 14, weight: .medium, design: .monospaced))
                        .textFieldStyle(.plain)
                        .focused($recipientFocused)
                        .onSubmit { resolveRecipient() }
                        .onChange(of: recipient) { _ in
                            resolvedAddress = ""
                            resolvedAlias = ""
                            statusText = ""
                        }
                        .onChange(of: recipientFocused) { focused in
                            if !focused && !recipient.isEmpty && resolvedAddress.isEmpty {
                                resolveRecipient()
                            }
                        }

                    Button(action: {
                        if let str = NSPasteboard.general.string(forType: .string) {
                            recipient = String(str.trimmingCharacters(in: .whitespacesAndNewlines).prefix(100))
                            resolveRecipient()
                        }
                    }) {
                        Image(systemName: "doc.on.clipboard")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                    .help("Вставить")
                }
                .padding(10)
                .background(cardBg)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(recipientFocused ? cyan.opacity(0.5) : Color.secondary.opacity(0.2), lineWidth: 1)
                )
                .padding(.horizontal, 16)

                if !resolvedAlias.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .font(.system(size: 10))
                        Text(resolvedAlias)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(.green)
                        Spacer()
                    }
                    .padding(.horizontal, 20)
                }
            }
            .padding(.bottom, 10)

            // Amount input
            VStack(spacing: 8) {
                HStack(spacing: 6) {
                    Text("Ɉ")
                        .font(.system(size: 18, weight: .bold, design: .monospaced))
                        .foregroundColor(gold.opacity(0.5))

                    TextField("0", text: $amount)
                        .font(.system(size: 22, weight: .bold, design: .monospaced))
                        .textFieldStyle(.plain)
                        .frame(maxWidth: .infinity)
                }
                .padding(10)
                .background(cardBg)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
                )
                .padding(.horizontal, 16)

                // Quick amount buttons
                HStack(spacing: 6) {
                    quickBtn(100)
                    quickBtn(1000)
                    quickBtn(10000)
                    Button(action: { amount = "\(engine.availableBalance)" }) {
                        Text("MAX")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(cyan)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background(cyan.opacity(0.1))
                            .cornerRadius(6)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 16)
            }

            // Warnings
            if let amt = Int(amount), amt > engine.availableBalance, engine.availableBalance > 0 {
                HStack(spacing: 4) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 9))
                    Text("Недостаточно средств")
                }
                .font(.system(size: 10))
                .foregroundColor(.orange)
                .padding(.top, 6)
            }
            if engine.availableBalance == 0 {
                HStack(spacing: 4) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 9))
                    Text("Нет доступных средств")
                }
                .font(.system(size: 10))
                .foregroundColor(.orange)
                .padding(.top, 6)
            }

            Spacer()

            // Status
            if !statusText.isEmpty {
                Text(statusText)
                    .font(.system(size: 11))
                    .foregroundColor(statusColor)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 6)
            }

            // Send button → переход к подтверждению
            Button(action: { prepareConfirmation() }) {
                HStack(spacing: 8) {
                    Image(systemName: "paperplane.fill")
                    Text("Отправить")
                        .font(.system(size: 14, weight: .bold))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .tint(canSend ? cyan : Color.secondary.opacity(0.3))
            .controlSize(.large)
            .disabled(!canSend)
            .padding(.horizontal, 16)
            .padding(.bottom, 14)
        }
    }

    // MARK: - Subviews

    private func methodButton(_ method: SendMethod) -> some View {
        let isSelected = sendMethod == method
        return Button(action: {
            sendMethod = method
            recipient = ""
            resolvedAddress = ""
            resolvedAlias = ""
            statusText = ""
        }) {
            VStack(spacing: 3) {
                Image(systemName: method.icon)
                    .font(.system(size: 11))
                Text(method.label)
                    .font(.system(size: 8, weight: .medium))
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(isSelected ? cyan.opacity(0.15) : cardBg)
            .foregroundColor(isSelected ? cyan : .secondary)
            .cornerRadius(6)
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(isSelected ? cyan.opacity(0.4) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private func quickBtn(_ value: Int) -> some View {
        Button(action: { amount = "\(value)" }) {
            Text("\(value)")
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundColor(.secondary)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(cardBg)
                .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }

    private func formatAmount(_ amount: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        let formatted = formatter.string(from: NSNumber(value: amount)) ?? "\(amount)"
        return "\(formatted) Ɉ"
    }

    // MARK: - Helpers

    private func displayAddr(_ addr: String) -> String {
        guard addr.count > 10 else { return addr }
        return String(addr.prefix(6)) + "..." + String(addr.suffix(4))
    }

    // MARK: - Logic

    private var canSend: Bool {
        guard let amt = Int(amount), amt > 0, amt <= engine.availableBalance else { return false }
        return !recipient.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isSending
    }

    private func extractLookupID(from input: String) -> String? {
        switch sendMethod {
        case .montanaID:
            // Символ Ɉ зашит — вводится только номер цифрами
            if input.hasPrefix("Ɉ-") { return String(input.dropFirst(2)) }
            else if input.hasPrefix("J-") || input.hasPrefix("j-") { return String(input.dropFirst(2)) }
            let digits = input.filter { $0.isNumber }
            return digits.isEmpty ? nil : digits
        case .nickname:
            let nick = input.hasPrefix("@") ? String(input.dropFirst()) : input
            return nick.isEmpty ? nil : nick
        case .fullAddress:
            return nil
        }
    }

    private func resolveRecipient() {
        let input = recipient.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }

        if sendMethod == .fullAddress {
            if input.hasPrefix("mt") && input.count == 42 {
                resolvedAddress = input
                resolvedAlias = String(input.prefix(8)) + "..." + String(input.suffix(4))
            } else {
                statusText = "Адрес должен начинаться с mt и содержать 42 символа"
                statusColor = .orange
            }
            return
        }

        guard let lookupID = extractLookupID(from: input) else { return }

        statusText = "Ищу..."
        statusColor = .secondary
        Task { @MainActor in
            do {
                let (addr, alias) = try await engine.api.lookupWallet(identifier: lookupID)
                if addr == (engine.address ?? "") {
                    resolvedAddress = ""
                    resolvedAlias = ""
                    statusText = "Нельзя отправить себе"
                    statusColor = .orange
                    return
                }
                resolvedAddress = addr
                resolvedAlias = alias
                statusText = ""
            } catch {
                statusText = "Адрес не найден"
                statusColor = .red
            }
        }
    }

    /// Шаг 1 → 2: Резолвим адрес и показываем экран подтверждения
    private func prepareConfirmation() {
        guard !isSending else { return }
        guard let _ = Int(amount), canSend else { return }

        // Если адрес ещё не резолвлен — резолвим
        if resolvedAddress.isEmpty {
            let input = recipient.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !input.isEmpty else {
                statusText = "Введите получателя"
                statusColor = .orange
                return
            }
            if sendMethod == .fullAddress && input.hasPrefix("mt") && input.count == 42 {
                resolvedAddress = input
                resolvedAlias = String(input.prefix(8)) + "..." + String(input.suffix(4))
                step = .preConfirm
            } else if let lookupID = extractLookupID(from: input) {
                isSending = true
                statusText = "Ищу..."
                statusColor = .secondary
                Task { @MainActor in
                    defer { isSending = false }
                    do {
                        let (addr, alias) = try await engine.api.lookupWallet(identifier: lookupID)
                        guard addr != (engine.address ?? "") else {
                            statusText = "Нельзя отправить себе"
                            statusColor = .orange
                            return
                        }
                        resolvedAddress = addr
                        resolvedAlias = alias
                        statusText = ""
                        step = .preConfirm
                    } catch {
                        statusText = "Адрес не найден"
                        statusColor = .red
                    }
                }
            }
        } else {
            guard resolvedAddress != (engine.address ?? "") else {
                statusText = "Нельзя отправить себе"
                statusColor = .orange
                return
            }
            step = .preConfirm
        }
    }

    /// Шаг 2 → 3: Реальная отправка после подтверждения
    private func executeTransfer() {
        guard !isSending else { return }
        guard let amt = Int(amount), amt > 0 else { return }
        guard !resolvedAddress.isEmpty else { return }

        isSending = true
        statusText = ""
        Task { @MainActor in
            defer { isSending = false }
            do {
                try await engine.api.transfer(
                    from: engine.address ?? "",
                    to: resolvedAddress,
                    amount: amt
                )
                await engine.syncBalance()
                let df = DateFormatter()
                df.dateFormat = "dd.MM.yyyy HH:mm:ss"
                sentAmount = amt
                sentRecipient = resolvedAlias.isEmpty ? displayAddr(resolvedAddress) : resolvedAlias
                sentTimestamp = df.string(from: Date())
                step = .result
            } catch {
                statusText = "Ошибка отправки. Попробуйте позже"
                statusColor = .red
            }
        }
    }
}
