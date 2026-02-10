import SwiftUI
import ServiceManagement

@main
struct MontanaPresenceApp: App {
    @StateObject private var engine = PresenceEngine.shared
    @StateObject private var camera = CameraManager.shared

    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environmentObject(engine)
                .environmentObject(camera)
        } label: {
            HStack(spacing: 4) {
                Image(systemName: engine.isPresent ? "eye.fill" : "eye.slash")
                if engine.isTracking {
                    Text("\(engine.displayBalance) \u{0248}")
                        .font(.system(.caption, design: .monospaced))
                }
            }
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environmentObject(engine)
        }
    }
}
