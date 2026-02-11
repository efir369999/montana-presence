import SwiftUI

struct LoginView: View {
    @EnvironmentObject var appState: AppState
    @State private var sessionId: String = UUID().uuidString.prefix(8).lowercased()
    @State private var isChecking = false
    @State private var statusText = ""
    @State private var checkTimer: Timer?

    var body: some View {
        ZStack {
            // Background
            Color("Background")
                .ignoresSafeArea()

            // Large background symbol
            Text("Ɉ")
                .font(.system(size: 400, weight: .ultraLight))
                .foregroundColor(Color("Gold").opacity(0.03))

            VStack(spacing: 32) {
                Spacer()

                // Logo
                VStack(spacing: 16) {
                    Text("Ɉ")
                        .font(.system(size: 80, weight: .thin))
                        .foregroundColor(Color("Gold"))
                        .shadow(color: Color("Gold").opacity(0.5), radius: 30)

                    Text("MONTANA")
                        .font(.system(size: 36, weight: .light))
                        .tracking(4)

                    Text("Время — единственная реальная валюта")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Login Button
                Button(action: loginViaTelegram) {
                    HStack(spacing: 12) {
                        Image(systemName: "paperplane.fill")
                            .font(.title2)
                        Text("Войти через Telegram")
                            .font(.headline)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 18)
                    .background(
                        LinearGradient(
                            colors: [Color(hex: "0088cc"), Color(hex: "229ED9")],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .foregroundColor(.white)
                    .cornerRadius(16)
                }
                .padding(.horizontal, 32)

                Text("@junomontanaagibot")
                    .font(.caption)
                    .foregroundColor(.secondary)

                if !statusText.isEmpty {
                    Text(statusText)
                        .font(.subheadline)
                        .foregroundColor(Color("Success"))
                }

                Spacer()
                    .frame(height: 50)
            }
        }
        .onDisappear {
            checkTimer?.invalidate()
        }
    }

    private func loginViaTelegram() {
        // Open Telegram bot
        let botURL = "https://t.me/junomontanaagibot?start=login_\(sessionId)"
        if let url = URL(string: botURL) {
            UIApplication.shared.open(url)
        }

        statusText = "Ожидание входа..."
        isChecking = true

        // Start checking login status
        checkTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            checkLoginStatus()
        }
    }

    private func checkLoginStatus() {
        API.shared.checkLoginStatus(sessionId: sessionId) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let session):
                    if let deviceId = session.deviceId {
                        // Login successful
                        checkTimer?.invalidate()
                        UserDefaults.standard.set(deviceId, forKey: "deviceId")
                        statusText = "✓ Вход выполнен"

                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            appState.loadUser(deviceId: deviceId)
                        }
                    }
                case .failure:
                    break
                }
            }
        }
    }
}

// MARK: - Color Extension
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
