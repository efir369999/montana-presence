import SwiftUI

/// Montana Video — Video Services
/// Видео сервисы Montana Protocol (placeholder)
struct VideoView: View {
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
            // Video icon
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
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.white)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Видео Montana")
                    .font(.headline)
                Text("Видеохостинг и стриминг")
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
            Image(systemName: "play.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(Color(red: 0.48, green: 0.18, blue: 1.0))

            Text("🎬 В разработке")
                .font(.title)
                .fontWeight(.bold)

            Text("Видеосервисы Montana Protocol скоро будут доступны")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(40)
        .background(Color.purple.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Info Section

    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("💡 Планируемые возможности")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(alignment: .leading, spacing: 8) {
                InfoRow(icon: "🎥", text: "Видеохостинг на Montana")
                InfoRow(icon: "📺", text: "Прямые трансляции")
                InfoRow(icon: "🔐", text: "Приватные видео")
                InfoRow(icon: "💾", text: "Децентрализованное хранение")
                InfoRow(icon: "💰", text: "Монетизация в Ɉ")
            }
        }
        .padding()
        .background(Color.purple.opacity(0.05))
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
    VideoView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
