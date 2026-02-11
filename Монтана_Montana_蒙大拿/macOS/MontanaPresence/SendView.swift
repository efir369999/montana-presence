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
                Text("Баланс:")
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(engine.serverBalance) \u{0248}")
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(cyan)
            }

            Divider()

            HStack {
                TextField("\u{0248}-1 или mt...", text: $recipient)
                    .font(.system(.body, design: .monospaced))
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { resolveRecipient() }

                Button(action: {
                    if let str = NSPasteboard.general.string(forType: .string) {
                        recipient = str.trimmingCharacters(in: .whitespacesAndNewlines)
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
                Button("Все") {
                    amount = "\(engine.serverBalance)"
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
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
        guard let amt = Int(amount), amt > 0, amt <= engine.serverBalance else { return false }
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
        Task {
            do {
                let (addr, alias) = try await engine.api.lookupWallet(identifier: lookupID)
                resolvedAddress = addr
                resolvedAlias = alias
                statusText = ""
            } catch {
                statusText = "Адрес не найден"
                statusColor = .red
            }
        }
    }

    private func sendTransfer() {
        guard let amt = Int(amount), amt > 0 else { return }
        guard !resolvedAddress.isEmpty else {
            resolveRecipient()
            return
        }
        isSending = true
        statusText = ""
        Task {
            do {
                try await engine.api.transfer(
                    from: engine.address ?? "",
                    to: resolvedAddress,
                    amount: amt
                )
                statusText = "Отправлено!"
                statusColor = .green
                await engine.syncBalance()
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                dismiss()
            } catch {
                statusText = "Ошибка: \(error.localizedDescription)"
                statusColor = .red
                isSending = false
            }
        }
    }
}
