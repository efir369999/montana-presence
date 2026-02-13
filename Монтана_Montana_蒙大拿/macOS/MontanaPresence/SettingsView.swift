import SwiftUI
import ServiceManagement

struct SettingsView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var vpn: VPNManager
    @State private var addressInput: String = ""
    @State private var launchAtLogin = false
    @State private var saved = false

    var body: some View {
        Form {
            Section("\u{0410}\u{0434}\u{0440}\u{0435}\u{0441} Montana") {
                TextField("mt...", text: $addressInput)
                    .font(.system(.body, design: .monospaced))
                    .textFieldStyle(.roundedBorder)

                if !addressInput.isEmpty && !isValidAddress(addressInput) {
                    Text("\u{0410}\u{0434}\u{0440}\u{0435}\u{0441} \u{0434}\u{043e}\u{043b}\u{0436}\u{0435}\u{043d} \u{043d}\u{0430}\u{0447}\u{0438}\u{043d}\u{0430}\u{0442}\u{044c}\u{0441}\u{044f} \u{0441} 'mt' \u{0438} \u{0441}\u{043e}\u{0434}\u{0435}\u{0440}\u{0436}\u{0430}\u{0442}\u{044c} 42 \u{0441}\u{0438}\u{043c}\u{0432}\u{043e}\u{043b}\u{0430}")
                        .font(.caption)
                        .foregroundColor(.red)
                }

                HStack {
                    Button("\u{0421}\u{043e}\u{0445}\u{0440}\u{0430}\u{043d}\u{0438}\u{0442}\u{044c}") {
                        engine.address = addressInput
                        saved = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { saved = false }
                    }
                    .disabled(!isValidAddress(addressInput))

                    if saved {
                        Text("\u{0421}\u{043e}\u{0445}\u{0440}\u{0430}\u{043d}\u{0435}\u{043d}\u{043e}!")
                            .font(.caption)
                            .foregroundColor(.green)
                    }

                    Spacer()

                    Button("\u{0412}\u{0441}\u{0442}\u{0430}\u{0432}\u{0438}\u{0442}\u{044c}") {
                        if let str = NSPasteboard.general.string(forType: .string) {
                            addressInput = str.trimmingCharacters(in: .whitespacesAndNewlines)
                        }
                    }
                }
            }

            Section("\u{0417}\u{0430}\u{043f}\u{0443}\u{0441}\u{043a}") {
                Toggle("\u{0417}\u{0430}\u{043f}\u{0443}\u{0441}\u{043a}\u{0430}\u{0442}\u{044c} \u{043f}\u{0440}\u{0438} \u{0432}\u{0445}\u{043e}\u{0434}\u{0435}", isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { _, newValue in
                        toggleLoginItem(enabled: newValue)
                    }
            }

            Section("\u{0421}\u{0442}\u{0430}\u{0442}\u{0438}\u{0441}\u{0442}\u{0438}\u{043a}\u{0430}") {
                LabeledContent("\u{0411}\u{0430}\u{043b}\u{0430}\u{043d}\u{0441} \u{0441}\u{0435}\u{0440}\u{0432}\u{0435}\u{0440}\u{0430}") {
                    Text("\(engine.serverBalance) \u{0248}")
                        .font(.system(.body, design: .monospaced))
                }
                LabeledContent("\u{041e}\u{0436}\u{0438}\u{0434}\u{0430}\u{0435}\u{0442}") {
                    Text("+\(engine.pendingSeconds)")
                        .font(.system(.body, design: .monospaced))
                }
                LabeledContent("\u{0421}\u{043e}\u{0435}\u{0434}\u{0438}\u{043d}\u{0435}\u{043d}\u{0438}\u{0435}") {
                    HStack {
                        Circle()
                            .fill(engine.isOnline ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(engine.isOnline ? "\u{041e}\u{043d}\u{043b}\u{0430}\u{0439}\u{043d}" : "\u{041e}\u{0444}\u{043b}\u{0430}\u{0439}\u{043d}")
                    }
                }
            }

            Section("\u{041e} \u{043f}\u{0440}\u{0438}\u{043b}\u{043e}\u{0436}\u{0435}\u{043d}\u{0438}\u{0438}") {
                LabeledContent("\u{0412}\u{0435}\u{0440}\u{0441}\u{0438}\u{044f}") { Text("Montana \(updater.currentVersion)") }
                LabeledContent("\u{041f}\u{0440}\u{043e}\u{0442}\u{043e}\u{043a}\u{043e}\u{043b}") { Text("Montana Protocol \u{0248}") }
                LabeledContent("\u{042f}\u{043a}\u{043e}\u{0440}\u{044f}") { Text("\u{0421}\u{0435}\u{043d}\u{0441}\u{043e}\u{0440}\u{044b} \u{043f}\u{0440}\u{0438}\u{0441}\u{0443}\u{0442}\u{0441}\u{0442}\u{0432}\u{0438}\u{044f}") }
                if updater.updateAvailable {
                    LabeledContent("\u{041e}\u{0431}\u{043d}\u{043e}\u{0432}\u{043b}\u{0435}\u{043d}\u{0438}\u{0435}") {
                        HStack {
                            Text("v\(updater.latestVersion)")
                                .foregroundColor(Color(red: 0, green: 0.83, blue: 1))
                            Button("\u{0423}\u{0441}\u{0442}\u{0430}\u{043d}\u{043e}\u{0432}\u{0438}\u{0442}\u{044c}") {
                                Task { await updater.downloadAndInstall() }
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(Color(red: 0, green: 0.83, blue: 1))
                            .controlSize(.small)
                            .disabled(updater.isDownloading)
                        }
                    }
                }

                HStack {
                    Spacer()
                    Button("\u{041f}\u{0440}\u{043e}\u{0432}\u{0435}\u{0440}\u{0438}\u{0442}\u{044c} \u{043e}\u{0431}\u{043d}\u{043e}\u{0432}\u{043b}\u{0435}\u{043d}\u{0438}\u{044f}") {
                        Task { await updater.checkForUpdate() }
                    }
                    .controlSize(.small)
                }
            }
        }
        .formStyle(.grouped)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
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
