import SwiftUI

struct MainWindowView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var camera: CameraManager
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var vpn: VPNManager
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            WalletTabView()
                .environmentObject(engine)
                .environmentObject(camera)
                .environmentObject(updater)
                .environmentObject(vpn)
                .tabItem {
                    Label("Кошелёк", systemImage: "banknote")
                }
                .tag(0)

            HistoryView()
                .environmentObject(engine)
                .tabItem {
                    Label("История", systemImage: "clock.arrow.circlepath")
                }
                .tag(1)

            TimeChainExplorerView()
                .environmentObject(engine)
                .tabItem {
                    Label("Цепочка", systemImage: "pentagon")
                }
                .tag(2)

            SettingsView()
                .environmentObject(engine)
                .tabItem {
                    Label("Настройки", systemImage: "gear")
                }
                .tag(3)
        }
        .frame(minWidth: 600, minHeight: 500)
        .onReceive(NotificationCenter.default.publisher(for: .switchToSettingsTab)) { _ in
            selectedTab = 3
        }
    }
}

extension Notification.Name {
    static let switchToSettingsTab = Notification.Name("switchToSettingsTab")
}
