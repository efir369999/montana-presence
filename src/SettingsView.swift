import SwiftUI
import ServiceManagement

struct SettingsView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var addressInput: String = ""
    @State private var launchAtLogin = false
    @State private var saved = false

    var body: some View {
        Form {
            Section("Montana Address") {
                TextField("mt...", text: $addressInput)
                    .font(.system(.body, design: .monospaced))
                    .textFieldStyle(.roundedBorder)

                if !addressInput.isEmpty && !isValidAddress(addressInput) {
                    Text("Address must start with 'mt' and be 42 characters")
                        .font(.caption)
                        .foregroundColor(.red)
                }

                HStack {
                    Button("Save") {
                        engine.address = addressInput
                        saved = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { saved = false }
                    }
                    .disabled(!isValidAddress(addressInput))

                    if saved {
                        Text("Saved!")
                            .font(.caption)
                            .foregroundColor(.green)
                    }

                    Spacer()

                    Button("Paste") {
                        if let str = NSPasteboard.general.string(forType: .string) {
                            addressInput = str.trimmingCharacters(in: .whitespacesAndNewlines)
                        }
                    }
                }
            }

            Section("Startup") {
                Toggle("Launch at login", isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { _, newValue in
                        toggleLoginItem(enabled: newValue)
                    }
            }

            Section("Stats") {
                LabeledContent("Server Balance") {
                    Text("\(engine.serverBalance) \u{0248}")
                        .font(.system(.body, design: .monospaced))
                }
                LabeledContent("Pending") {
                    Text("+\(engine.pendingSeconds)")
                        .font(.system(.body, design: .monospaced))
                }
                LabeledContent("Connection") {
                    HStack {
                        Circle()
                            .fill(engine.isOnline ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(engine.isOnline ? "Online" : "Offline")
                    }
                }
            }

            Section("About") {
                LabeledContent("App") { Text("Montana Presence 1.0.0") }
                LabeledContent("Protocol") { Text("Montana Protocol \u{0248}") }
                LabeledContent("Detection") { Text("Apple Vision (local)") }
            }
        }
        .formStyle(.grouped)
        .frame(width: 400, height: 380)
        .onAppear {
            addressInput = engine.address ?? ""
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
    }

    private func isValidAddress(_ addr: String) -> Bool {
        addr.count == 42 && addr.hasPrefix("mt")
    }

    private func toggleLoginItem(enabled: Bool) {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
    }
}
