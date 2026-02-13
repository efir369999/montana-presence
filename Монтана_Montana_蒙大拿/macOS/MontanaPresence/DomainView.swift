import SwiftUI

/// Montana Name Service — Domain Registration
/// Регистрация доменов через аукцион (N-й домен = N Ɉ)
struct DomainView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var domainInput = ""
    @State private var currentPrice = 1
    @State private var isLoading = false
    @State private var statusMessage = ""
    @State private var ownedDomains: [OwnedDomain] = []

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            Divider()

            // Main content
            ScrollView {
                VStack(spacing: 24) {
                    // Registration card
                    registrationCard

                    // Owned domains
                    if !ownedDomains.isEmpty {
                        ownedDomainsSection
                    }

                    // Info section
                    infoSection
                }
                .padding()
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear {
            loadCurrentPrice()
            loadOwnedDomains()
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            // Domain icon
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
                    Text("@")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.white)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Домены Montana")
                    .font(.headline)
                Text("Регистрация доменов @montana.network")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Current price badge
            HStack(spacing: 4) {
                Text("\(currentPrice)")
                    .font(.title2)
                    .fontWeight(.bold)
                Text("Ɉ")
                    .font(.title2)
            }
            .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color(red: 0.0, green: 0.83, blue: 1.0).opacity(0.1))
            .cornerRadius(8)
        }
        .padding()
    }

    // MARK: - Registration Card

    private var registrationCard: some View {
        VStack(spacing: 16) {
            Text("Регистрация домена")
                .font(.title3)
                .fontWeight(.semibold)

            HStack(spacing: 8) {
                TextField("имя", text: $domainInput)
                    .textFieldStyle(.plain)
                    .font(.system(size: 16))
                    .padding(10)
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(8)
                    .disabled(isLoading)

                Text("@montana.network")
                    .foregroundColor(.secondary)
            }

            if !statusMessage.isEmpty {
                Text(statusMessage)
                    .font(.caption)
                    .foregroundColor(statusMessage.hasPrefix("✓") ? .green : .red)
            }

            Button(action: registerDomain) {
                HStack {
                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.8)
                            .padding(.trailing, 4)
                    }
                    Text("Зарегистрировать за \(currentPrice) Ɉ")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(domainInput.isEmpty || isLoading ? Color.gray : Color(red: 0.0, green: 0.83, blue: 1.0))
                .foregroundColor(.white)
                .cornerRadius(8)
            }
            .buttonStyle(.plain)
            .disabled(domainInput.isEmpty || isLoading)
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Owned Domains Section

    private var ownedDomainsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Мои домены")
                .font(.title3)
                .fontWeight(.semibold)

            ForEach(ownedDomains) { domain in
                HStack {
                    Text(domain.name + "@montana.network")
                        .font(.system(.body, design: .monospaced))

                    Spacer()

                    Text("\(domain.pricePaid) Ɉ")
                        .foregroundColor(.secondary)
                        .font(.caption)
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
            }
        }
    }

    // MARK: - Info Section

    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("💡 Аукционная модель")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(alignment: .leading, spacing: 8) {
                InfoRow(icon: "1️⃣", text: "1-й домен: 1 Ɉ")
                InfoRow(icon: "2️⃣", text: "2-й домен: 2 Ɉ")
                InfoRow(icon: "🔢", text: "N-й домен: N Ɉ")
                InfoRow(icon: "📧", text: "Формат: alice@montana.network")
                InfoRow(icon: "🔐", text: "Постквантовая криптография ML-DSA-65")
            }
        }
        .padding()
        .background(Color.orange.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Actions

    private func loadCurrentPrice() {
        // TODO: API call to get current domain price
        // For now, use placeholder
        currentPrice = 1
    }

    private func loadOwnedDomains() {
        // TODO: API call to get owned domains
        // For now, empty
        ownedDomains = []
    }

    private func registerDomain() {
        guard !domainInput.isEmpty else { return }

        // Validate domain name
        let sanitized = domainInput.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard sanitized.range(of: "^[a-z0-9_-]+$", options: .regularExpression) != nil else {
            statusMessage = "❌ Только латиница, цифры, _ и -"
            return
        }

        isLoading = true
        statusMessage = ""

        // TODO: API call to register domain
        Task {
            do {
                // Simulate API call
                try await Task.sleep(nanoseconds: 1_000_000_000)

                await MainActor.run {
                    statusMessage = "✓ Домен \(sanitized)@montana.network зарегистрирован!"
                    ownedDomains.append(OwnedDomain(name: sanitized, pricePaid: currentPrice))
                    domainInput = ""
                    currentPrice += 1
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    statusMessage = "❌ Не удалось зарегистрировать домен"
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - Models

struct OwnedDomain: Identifiable {
    let id = UUID()
    let name: String
    let pricePaid: Int
}

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
    DomainView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
