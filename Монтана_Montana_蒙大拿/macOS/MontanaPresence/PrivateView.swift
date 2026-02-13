import SwiftUI

/// Montana Private — Приватные кошельки и зашифрованные транзакции
/// Zero-knowledge proof, stealth addresses, полная анонимность
struct PrivateView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var privateNickname = ""
    @State private var isPurchasing = false
    @State private var purchaseStatus = ""
    @State private var hasPrivateWallet = false
    @State private var privateBalance = 0
    @State private var privateAddress = ""

    private let darkPurple = Color(red: 0.25, green: 0.0, blue: 0.4)
    private let neonPurple = Color(red: 0.48, green: 0.18, blue: 1.0)
    private let cyan = Color(red: 0.0, green: 0.83, blue: 1.0)

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            Divider()

            // Main content
            ScrollView {
                VStack(spacing: 24) {
                    if hasPrivateWallet {
                        // Private wallet card
                        privateWalletCard
                    } else {
                        // Purchase card
                        purchaseCard
                    }

                    // Info section
                    infoSection
                }
                .padding()
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear {
            loadPrivateWallet()
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            // Private icon
            Circle()
                .fill(
                    LinearGradient(
                        colors: [darkPurple, neonPurple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 40, height: 40)
                .overlay(
                    Image(systemName: "eye.slash.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.white)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Приват")
                    .font(.headline)
                Text("Зашифрованные транзакции")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Privacy badge
            HStack(spacing: 4) {
                Image(systemName: "lock.shield.fill")
                    .font(.system(size: 10))
                Text("ZERO-KNOWLEDGE")
                    .font(.system(size: 8, weight: .bold))
            }
            .foregroundColor(neonPurple)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(neonPurple.opacity(0.1))
            .cornerRadius(8)
        }
        .padding()
    }

    // MARK: - Purchase Card

    private var purchaseCard: some View {
        VStack(spacing: 20) {
            Image(systemName: "eye.slash.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(neonPurple)

            Text("🔐 Приватный кошелёк")
                .font(.title)
                .fontWeight(.bold)

            Text("Покупка приватного ника открывает доступ к зашифрованным транзакциям. Баланс, история, адрес — всё скрыто от blockchain explorer.")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .lineSpacing(4)

            Divider()

            // Nickname input
            VStack(alignment: .leading, spacing: 8) {
                Text("Выбери приватный ник")
                    .font(.callout)
                    .fontWeight(.semibold)

                HStack(spacing: 8) {
                    TextField("nickname", text: $privateNickname)
                        .textFieldStyle(.plain)
                        .font(.system(size: 14, design: .monospaced))
                        .padding(10)
                        .background(Color(NSColor.controlBackgroundColor))
                        .cornerRadius(8)
                        .disabled(isPurchasing)

                    Text("@private.montana")
                        .font(.system(size: 14, design: .monospaced))
                        .foregroundColor(.secondary)
                }

                if !purchaseStatus.isEmpty {
                    Text(purchaseStatus)
                        .font(.caption)
                        .foregroundColor(purchaseStatus.contains("✅") ? .green : .red)
                }
            }

            // Purchase button
            Button(action: purchasePrivateNick) {
                HStack(spacing: 8) {
                    if isPurchasing {
                        ProgressView()
                            .controlSize(.small)
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "cart.fill")
                            .font(.system(size: 14))
                    }
                    Text("Купить приватный ник")
                        .font(.system(size: 14, weight: .semibold))
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(
                    LinearGradient(
                        colors: [darkPurple, neonPurple],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(10)
            }
            .buttonStyle(.plain)
            .disabled(privateNickname.isEmpty || isPurchasing)
        }
        .frame(maxWidth: .infinity)
        .padding(40)
        .background(darkPurple.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Private Wallet Card

    private var privateWalletCard: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Приватный кошелёк")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.secondary)

                    Text("\(privateNickname)@private.montana")
                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                        .foregroundColor(neonPurple)
                }
                Spacer()
                Image(systemName: "checkmark.shield.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.green)
            }

            Divider()

            // Balance (encrypted)
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("БАЛАНС")
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundColor(.secondary)
                    Text("█████ Ɉ")
                        .font(.system(size: 20, weight: .bold, design: .monospaced))
                        .foregroundColor(cyan)
                }
                Spacer()
                Text("🔒 ЗАШИФРОВАНО")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(neonPurple)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(neonPurple.opacity(0.1))
                    .cornerRadius(6)
            }

            // Stealth address
            VStack(alignment: .leading, spacing: 4) {
                Text("STEALTH ADDRESS")
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .foregroundColor(.secondary)
                Text(privateAddress.isEmpty ? "████████████████████████████" : privateAddress)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }

            // Private actions
            HStack(spacing: 8) {
                Button(action: {}) {
                    HStack(spacing: 4) {
                        Text("Ɉ")
                            .font(.system(size: 12, weight: .bold))
                        Image(systemName: "arrow.up")
                            .font(.system(size: 10, weight: .bold))
                        Text("Отправить")
                            .font(.system(size: 11, weight: .semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(neonPurple.opacity(0.15))
                    .foregroundColor(neonPurple)
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)

                Button(action: {}) {
                    HStack(spacing: 4) {
                        Text("Ɉ")
                            .font(.system(size: 12, weight: .bold))
                        Image(systemName: "arrow.down")
                            .font(.system(size: 10, weight: .bold))
                        Text("Получить")
                            .font(.system(size: 11, weight: .semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(darkPurple.opacity(0.15))
                    .foregroundColor(neonPurple)
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(16)
        .background(
            LinearGradient(
                colors: [darkPurple.opacity(0.1), neonPurple.opacity(0.05)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(neonPurple.opacity(0.3), lineWidth: 1)
        )
    }

    // MARK: - Info Section

    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("💡 Как работает приват")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(alignment: .leading, spacing: 8) {
                InfoRow(icon: "🔐", text: "Zero-knowledge proof — никто не видит баланс")
                InfoRow(icon: "🎭", text: "Stealth addresses — новый адрес для каждой транзакции")
                InfoRow(icon: "🔒", text: "Ring signatures — невозможно отследить отправителя")
                InfoRow(icon: "👻", text: "Не отображается в blockchain explorer")
                InfoRow(icon: "💰", text: "Покупка приватного ника = доступ навсегда")
            }
        }
        .padding()
        .background(darkPurple.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Actions

    private func loadPrivateWallet() {
        // TODO: Load from UserDefaults or keychain
        hasPrivateWallet = false
    }

    private func purchasePrivateNick() {
        guard !privateNickname.isEmpty else { return }
        isPurchasing = true
        purchaseStatus = ""

        Task { @MainActor in
            do {
                // TODO: Call API to purchase private nickname
                try await Task.sleep(nanoseconds: 2_000_000_000)

                // Mock success
                hasPrivateWallet = true
                privateAddress = "stealth_████████████████████████████"
                purchaseStatus = "✅ Приватный ник куплен!"

                isPurchasing = false
            } catch {
                purchaseStatus = "❌ Ошибка покупки"
                isPurchasing = false
            }
        }
    }
}

// MARK: - Supporting Views

private struct InfoRow: View {
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

// MARK: - Preview

#Preview {
    PrivateView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
