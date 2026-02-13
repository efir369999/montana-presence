import SwiftUI

struct MainWindowView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var camera: CameraManager
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var vpn: VPNManager
    @State private var selectedTab = 1  // Default: Wallet (not Junona)

    var body: some View {
        TabView(selection: $selectedTab) {
            // TAB 0: Junona AI Agent — Montana Protocol Control Center
            JunonaView()
                .environmentObject(engine)
                .tabItem {
                    Label("Junona", systemImage: "brain.head.profile")
                }
                .tag(0)

            // TAB 1: Wallet
            WalletTabView()
                .environmentObject(engine)
                .environmentObject(camera)
                .environmentObject(updater)
                .environmentObject(vpn)
                .tabItem {
                    Label("Кошелёк", systemImage: "banknote")
                }
                .tag(1)

            // TAB 2: Domains
            DomainView()
                .environmentObject(engine)
                .tabItem {
                    Label("Домены", systemImage: "at")
                }
                .tag(2)

            // TAB 3: Phone Numbers
            PhoneView()
                .environmentObject(engine)
                .tabItem {
                    Label("Номера", systemImage: "phone")
                }
                .tag(3)

            // TAB 4: Calls
            CallsView()
                .environmentObject(engine)
                .tabItem {
                    Label("Звонки", systemImage: "phone.fill")
                }
                .tag(4)

            // TAB 5: Sites
            SitesView()
                .environmentObject(engine)
                .tabItem {
                    Label("Сайты", systemImage: "globe")
                }
                .tag(5)

            // TAB 6: Video
            VideoView()
                .environmentObject(engine)
                .tabItem {
                    Label("Видео", systemImage: "play.circle")
                }
                .tag(6)

            // TAB 7: History
            HistoryView()
                .environmentObject(engine)
                .tabItem {
                    Label("История", systemImage: "clock.arrow.circlepath")
                }
                .tag(7)

            // TAB 8: TimeChain Explorer
            TimeChainExplorerView()
                .environmentObject(engine)
                .tabItem {
                    Label("Цепочка", systemImage: "pentagon")
                }
                .tag(8)

            // TAB 9: Settings
            SettingsView()
                .environmentObject(engine)
                .tabItem {
                    Label("Настройки", systemImage: "gear")
                }
                .tag(9)
        }
        .frame(minWidth: 600, minHeight: 500)
        .onReceive(NotificationCenter.default.publisher(for: .switchToSettingsTab)) { _ in
            selectedTab = 9  // Settings moved to tab 9
        }
        .onReceive(NotificationCenter.default.publisher(for: .switchToTab)) { notification in
            if let tab = notification.userInfo?["tab"] as? Int {
                selectedTab = tab
            }
        }
    }
}

extension Notification.Name {
    static let switchToSettingsTab = Notification.Name("switchToSettingsTab")
    static let switchToTab = Notification.Name("switchToTab")
}
