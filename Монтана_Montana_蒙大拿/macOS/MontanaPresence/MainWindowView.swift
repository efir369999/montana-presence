import SwiftUI

struct MainWindowView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var camera: CameraManager
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var vpn: VPNManager
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            // TAB 0: Junona AI Agent — Montana Protocol Assistant
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

            // TAB 2: History
            HistoryView()
                .environmentObject(engine)
                .tabItem {
                    Label("История", systemImage: "clock.arrow.circlepath")
                }
                .tag(2)

            // TAB 3: TimeChain Explorer
            TimeChainExplorerView()
                .environmentObject(engine)
                .tabItem {
                    Label("Цепочка", systemImage: "pentagon")
                }
                .tag(3)

            // TAB 4: Settings
            SettingsView()
                .environmentObject(engine)
                .tabItem {
                    Label("Настройки", systemImage: "gear")
                }
                .tag(4)
        }
        .frame(minWidth: 600, minHeight: 500)
        .onReceive(NotificationCenter.default.publisher(for: .switchToSettingsTab)) { _ in
            selectedTab = 4  // Settings moved to tab 4
        }
    }
}

extension Notification.Name {
    static let switchToSettingsTab = Notification.Name("switchToSettingsTab")
}
