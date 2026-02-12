import SwiftUI

struct SendView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var recipient = ""
    @State private var amount = ""
    @State private var statusText = ""
    @State private var statusColor: Color = .secondary
    @State private var resolvedAddress = ""
    @State private var resolvedAlias = ""
    @State private var isSending = false
    @FocusState private var recipientFocused: Bool
    @Environment(\.dismiss) private var dismiss

    private let cyan = Color(red: 0, green: 0.83, blue: 1)

    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Text("\u{0248} Отправить")
                    .font(.system(size: 16, weight: .bold))
                Spacer()
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }

            HStack {
                Text("\u{0414}\u{043e}\u{0441}\u{0442}\u{0443}\u{043f}\u{043d}\u{043e}:")
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(engine.availableBalance) \u{0248}")
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(cyan)
            }

            Divider()

            HStack {
                TextField("Номер или mt...", text: $recipient)
                    .font(.system(.body, design: .monospaced))
                    .textFieldStyle(.roundedBorder)
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
                }
                .help("Вставить")
            }

            if !resolvedAlias.isEmpty {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text(resolvedAlias)
                        .font(.caption)
                        .foregroundColor(.green)
                    Spacer()
                }
            }

            HStack {
                TextField("Сумма \u{0248}", text: $amount)
                    .font(.system(.title3, design: .monospaced))
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: .infinity)
            }

            HStack(spacing: 8) {
                quickBtn(100)
                quickBtn(1000)
                quickBtn(10000)
                Button("\u{0412}\u{0441}\u{0435}") {
                    amount = "\(engine.availableBalance)"
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }

            if let amt = Int(amount), amt > engine.availableBalance, engine.availableBalance > 0 {
                Text("Недостаточно средств (доступно: \(engine.availableBalance) Ɉ)")
                    .font(.caption)
                    .foregroundColor(.orange)
            }
            if engine.availableBalance == 0 {
                Text("Нет доступных средств для отправки")
                    .font(.caption)
                    .foregroundColor(.orange)
            }

            Spacer()

            if !statusText.isEmpty {
                Text(statusText)
                    .font(.caption)
                    .foregroundColor(statusColor)
                    .lineLimit(2)
            }

            Button(action: { sendTransfer() }) {
                HStack {
                    if isSending {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Image(systemName: "paperplane.fill")
                    }
                    Text("Отправить")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(cyan)
            .controlSize(.large)
            .disabled(!canSend)
        }
        .padding()
        .frame(width: 300, height: 380)
    }

    private var canSend: Bool {
        guard let amt = Int(amount), amt > 0, amt <= engine.availableBalance else { return false }
        return !resolvedAddress.isEmpty && !isSending
    }

    private func quickBtn(_ value: Int) -> some View {
        Button("\(value)") { amount = "\(value)" }
            .buttonStyle(.bordered)
            .controlSize(.small)
    }

    private func resolveRecipient() {
        let input = recipient.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }

        if input.hasPrefix("mt") && input.count == 42 {
            resolvedAddress = input
            resolvedAlias = String(input.prefix(8)) + "..." + String(input.suffix(4))
            return
        }

        var lookupID = input
        if input.hasPrefix("\u{0248}-") { lookupID = String(input.dropFirst(2)) }
        else if input.hasPrefix("J-") || input.hasPrefix("j-") { lookupID = String(input.dropFirst(2)) }
        else if input.allSatisfy({ $0.isNumber }) { lookupID = input }

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
                statusText = "Адрес не найден. Проверьте номер"
                statusColor = .red
            }
        }
    }

    private func sendTransfer() {
        guard !isSending else { return }
        guard let amt = Int(amount), amt > 0 else { return }
        guard !resolvedAddress.isEmpty else {
            resolveRecipient()
            return
        }
        guard resolvedAddress != (engine.address ?? "") else {
            statusText = "Нельзя отправить себе"
            statusColor = .orange
            return
        }
        isSending = true
        statusText = ""
        Task { @MainActor in
            do {
                try await engine.api.transfer(
                    from: engine.address ?? "",
                    to: resolvedAddress,
                    amount: amt
                )
                statusText = "Отправлено \(amt) Ɉ → \(resolvedAlias)"
                statusColor = .green
                await engine.syncBalance()
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                dismiss()
            } catch {
                statusText = "Ошибка отправки. Попробуйте позже"
                statusColor = .red
                isSending = false
            }
        }
    }
}
