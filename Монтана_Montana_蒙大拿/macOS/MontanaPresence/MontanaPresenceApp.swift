import SwiftUI
import ServiceManagement
import AVFoundation

@main
struct MontanaPresenceApp: App {
    @StateObject private var engine = PresenceEngine.shared
    @StateObject private var camera = CameraManager.shared
    @StateObject private var updater = UpdateManager.shared
    @StateObject private var vpn = VPNManager.shared

    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environmentObject(engine)
                .environmentObject(camera)
                .environmentObject(updater)
                .environmentObject(vpn)
        } label: {
            Text(menuBarLabel)
                .font(.system(size: 12, weight: .medium, design: .monospaced))
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environmentObject(engine)
                .environmentObject(updater)
                .environmentObject(vpn)
        }
    }

    init() {
        try? SMAppService.mainApp.register()
        Task { @MainActor in
            UpdateManager.shared.startChecking()
            await MontanaPresenceApp.requestAllPermissions()
            PresenceEngine.shared.autoStart()
        }
    }

    private var menuBarLabel: String {
        var parts: [String] = []
        if engine.showBalanceInMenuBar {
            parts.append("\(formatFullBalance(engine.displayBalance)) \u{0248}")
        } else {
            parts.append("\u{0248}")
        }
        if engine.showWeightInMenuBar {
            parts.append("x\(engine.weight)")
        }
        if engine.showRateInMenuBar {
            parts.append("+\(engine.ratePerSecond)/\u{0441}")
        }
        return parts.joined(separator: " ")
    }

    private func formatFullBalance(_ n: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = ","
        return formatter.string(from: NSNumber(value: n)) ?? "\(n)"
    }

    @MainActor
    static func requestAllPermissions() async {
        // 1. Camera
        if AVCaptureDevice.authorizationStatus(for: .video) == .notDetermined {
            await AVCaptureDevice.requestAccess(for: .video)
        }
        // 2. Microphone
        if AVCaptureDevice.authorizationStatus(for: .audio) == .notDetermined {
            await AVCaptureDevice.requestAccess(for: .audio)
        }
        // 3. Location
        PresenceEngine.shared.requestLocationPermission()
        try? await Task.sleep(nanoseconds: 2_000_000_000)
        // 4. Bluetooth
        PresenceEngine.shared.requestBluetoothPermission()
        try? await Task.sleep(nanoseconds: 500_000_000)
    }
}
