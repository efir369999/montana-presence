import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var camera: CameraManager

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Balance
            HStack(alignment: .firstTextBaseline) {
                Text("\(engine.displayBalance)")
                    .font(.system(size: 36, weight: .bold, design: .monospaced))
                Text("\u{0248}")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(Color(red: 0.29, green: 0.56, blue: 0.85))
            }

            Divider()

            // Presence status
            HStack {
                Circle()
                    .fill(engine.isPresent ? Color.green : Color.gray)
                    .frame(width: 10, height: 10)
                Text(engine.isPresent ? "Present" : "Away")
                    .foregroundColor(engine.isPresent ? .primary : .secondary)
                Spacer()
                if engine.isTracking {
                    Text(formatDuration(engine.sessionSeconds))
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(.secondary)
                }
            }

            // Connection status
            HStack {
                Circle()
                    .fill(engine.isOnline ? Color.blue : Color.orange)
                    .frame(width: 8, height: 8)
                Text(engine.isOnline ? "Connected" : "Offline")
                    .font(.caption)
                    .foregroundColor(.secondary)
                if engine.pendingSeconds > 0 {
                    Spacer()
                    Text("+\(engine.pendingSeconds) pending")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }

            if let error = camera.cameraError {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
            }

            Divider()

            // Start/Stop
            Button(action: {
                if engine.isTracking {
                    engine.stopTracking()
                } else {
                    engine.startTracking()
                }
            }) {
                HStack {
                    Image(systemName: engine.isTracking ? "stop.circle.fill" : "play.circle.fill")
                    Text(engine.isTracking ? "Stop" : "Start")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(engine.isTracking ? .red : Color(red: 0.29, green: 0.56, blue: 0.85))
            .disabled(engine.address == nil || engine.address?.isEmpty == true)

            if engine.address == nil || engine.address?.isEmpty == true {
                Text("Set your Montana address in Settings")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            // Address
            if let addr = engine.address, !addr.isEmpty {
                HStack {
                    Text(shortenAddress(addr))
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.secondary)
                    Spacer()
                    Button("Copy") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(addr, forType: .string)
                    }
                    .font(.caption)
                }
            }

            Divider()

            Button("Settings...") {
                if #available(macOS 14.0, *) {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                } else {
                    NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
                }
            }
            .keyboardShortcut(",", modifiers: .command)

            Button("Quit Montana Presence") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q", modifiers: .command)
        }
        .padding()
        .frame(width: 280)
    }

    private func formatDuration(_ seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        let s = seconds % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        }
        return String(format: "%02d:%02d", m, s)
    }

    private func shortenAddress(_ addr: String) -> String {
        guard addr.count > 12 else { return addr }
        let prefix = addr.prefix(8)
        let suffix = addr.suffix(4)
        return "\(prefix)...\(suffix)"
    }
}
