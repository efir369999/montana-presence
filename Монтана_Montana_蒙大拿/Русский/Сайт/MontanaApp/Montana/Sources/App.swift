import SwiftUI

@main
struct MontanaApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .preferredColorScheme(.dark)
        }
    }
}

// MARK: - App State
class AppState: ObservableObject {
    @Published var isLoggedIn: Bool = false
    @Published var user: User?
    @Published var balance: Int = 0
    @Published var presenceSeconds: Int = 0
    @Published var contacts: [Contact] = []

    var deviceId: String? {
        UserDefaults.standard.string(forKey: "deviceId")
    }

    var userPhone: String? {
        user?.phone
    }

    private var presenceTimer: Timer?

    init() {
        // Check existing login
        if let deviceId = UserDefaults.standard.string(forKey: "deviceId") {
            loadUser(deviceId: deviceId)
        }
    }

    func startPresence() {
        presenceTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.presenceSeconds += 1

            // Sync every 60 seconds
            if self?.presenceSeconds ?? 0 % 60 == 0 {
                self?.syncPresence()
            }
        }
    }

    func stopPresence() {
        presenceTimer?.invalidate()
        syncPresence()
    }

    private func syncPresence() {
        guard let deviceId = UserDefaults.standard.string(forKey: "deviceId") else { return }
        let seconds = presenceSeconds % 60
        if seconds > 0 {
            API.shared.syncPresence(deviceId: deviceId, seconds: seconds)
        }
    }

    func loadUser(deviceId: String) {
        API.shared.getUser(deviceId: deviceId) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let user):
                    self?.user = user
                    self?.balance = user.balance
                    self?.isLoggedIn = true
                    self?.startPresence()
                    self?.loadContacts()
                case .failure:
                    UserDefaults.standard.removeObject(forKey: "deviceId")
                    self?.isLoggedIn = false
                }
            }
        }
    }

    func loadContacts() {
        guard let deviceId = UserDefaults.standard.string(forKey: "deviceId") else { return }
        API.shared.getContacts(deviceId: deviceId) { [weak self] result in
            DispatchQueue.main.async {
                if case .success(let contacts) = result {
                    self?.contacts = contacts
                }
            }
        }
    }

    func logout() {
        stopPresence()
        UserDefaults.standard.removeObject(forKey: "deviceId")
        isLoggedIn = false
        user = nil
        balance = 0
        presenceSeconds = 0
        contacts = []
    }
}
