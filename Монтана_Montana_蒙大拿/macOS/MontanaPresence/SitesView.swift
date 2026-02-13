import SwiftUI

/// Montana Sites — Web Hosting
/// Хостинг сайтов Montana Protocol (placeholder)
struct SitesView: View {
    @EnvironmentObject var engine: PresenceEngine

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            Divider()

            // Main content
            ScrollView {
                VStack(spacing: 24) {
                    // Coming soon card
                    comingSoonCard

                    // Info section
                    infoSection
                }
                .padding()
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            // Sites icon
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
                    Image(systemName: "globe")
                        .font(.system(size: 18))
                        .foregroundColor(.white)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Сайты Montana")
                    .font(.headline)
                Text("Хостинг и веб-сервисы")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()
        }
        .padding()
    }

    // MARK: - Coming Soon Card

    private var comingSoonCard: some View {
        VStack(spacing: 20) {
            Image(systemName: "globe")
                .font(.system(size: 60))
                .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))

            Text("🚧 В разработке")
                .font(.title)
                .fontWeight(.bold)

            Text("Хостинг сайтов Montana Protocol скоро будет доступен")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(40)
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Info Section

    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("💡 Планируемые возможности")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(alignment: .leading, spacing: 8) {
                InfoRow(icon: "🌐", text: "Хостинг на alice.montana.network")
                InfoRow(icon: "⚡", text: "Децентрализованное хранилище")
                InfoRow(icon: "🔐", text: "SSL сертификаты")
                InfoRow(icon: "📊", text: "CDN и аналитика")
                InfoRow(icon: "💰", text: "Оплата в Ɉ (Montana Protocol)")
            }
        }
        .padding()
        .background(Color.orange.opacity(0.05))
        .cornerRadius(12)
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
    SitesView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
