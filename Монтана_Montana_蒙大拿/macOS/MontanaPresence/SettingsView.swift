import SwiftUI
import ServiceManagement

struct SettingsView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var vpn: VPNManager
    @State private var addressInput: String = ""
    @State private var launchAtLogin = false
    @State private var saved = false

    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)
    private let goldLight = Color(red: 0.95, green: 0.82, blue: 0.45)

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

            Section("Menu Bar") {
                Toggle("\u{0421}\u{0438}\u{043c}\u{0432}\u{043e}\u{043b} \u{0248}", isOn: Binding(
                    get: { engine.showSymbolInMenuBar },
                    set: { _ in engine.toggleMenuBarSymbol() }
                ))
                Toggle("\u{0411}\u{0430}\u{043b}\u{0430}\u{043d}\u{0441}", isOn: Binding(
                    get: { engine.showBalanceInMenuBar },
                    set: { _ in engine.toggleMenuBarBalance() }
                ))
                Toggle("\u{0412}\u{0435}\u{0441}", isOn: Binding(
                    get: { engine.showWeightInMenuBar },
                    set: { _ in engine.toggleMenuBarWeight() }
                ))
            }

            // ╔══════════════════════════════════════════════════════════════════╗
            // ║  IMMUTABLE BLOCK — SENSOR UI (Settings)                         ║
            // ║  НЕ МЕНЯТЬ. Это неизменяемый блок кода.                         ║
            // ║                                                                 ║
            // ║  Тумблер ON + разрешение = золотой, показывает +N Ɉ/с           ║
            // ║  Тумблер OFF или нет разрешения = серый, без рейта              ║
            // ║  Клик на выключенный без разрешения → запрос разрешения          ║
            // ║  Клик на включённый → выключить                                 ║
            // ╚══════════════════════════════════════════════════════════════════╝
            Section("\u{0414}\u{0430}\u{0442}\u{0447}\u{0438}\u{043a}\u{0438} \u{043f}\u{0440}\u{0438}\u{0441}\u{0443}\u{0442}\u{0441}\u{0442}\u{0432}\u{0438}\u{044f}") {
                HStack(spacing: 6) {
                    Image(systemName: "person.fill")
                        .frame(width: 18)
                        .foregroundColor(gold)
                    Text("\u{041f}\u{0440}\u{0438}\u{0441}\u{0443}\u{0442}\u{0441}\u{0442}\u{0432}\u{0438}\u{0435}")
                    Spacer()
                    Text("+1 \u{0248}/\u{0441}")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(goldLight)
                }

                ForEach(engine.sensors) { sensor in
                    let hasPermission = engine.sensorPermissions[sensor.id] ?? false
                    let isActive = sensor.enabled && hasPermission
                    HStack(spacing: 6) {
                        Image(systemName: sensor.icon)
                            .frame(width: 18)
                            .foregroundColor(isActive ? gold : .secondary)
                        Text(sensor.name)
                            .foregroundColor(isActive ? .primary : .secondary)
                        Spacer()
                        if isActive {
                            Text("+\(sensor.rate) \u{0248}/\u{0441}")
                                .font(.system(.caption, design: .monospaced))
                                .foregroundColor(goldLight)
                        }
                        Toggle("", isOn: Binding(
                            get: { sensor.enabled },
                            set: { _ in
                                if !sensor.enabled && !hasPermission {
                                    engine.requestPermission(for: sensor.id)
                                } else {
                                    engine.toggleSensor(sensor.id)
                                }
                            }
                        ))
                        .toggleStyle(.switch)
                        .controlSize(.mini)
                        .labelsHidden()
                    }
                }

                HStack(spacing: 6) {
                    Image(systemName: "lock.shield.fill")
                        .frame(width: 18)
                        .foregroundColor(vpn.isConnected ? gold : .secondary)
                    Text("VPN")
                        .foregroundColor(vpn.isConnected ? .primary : .secondary)
                    Spacer()
                    if vpn.isConnected {
                        Text("+1 \u{0248}/\u{0441}")
                            .font(.system(.caption, design: .monospaced))
                            .foregroundColor(goldLight)
                    }
                    if vpn.isConnecting {
                        ProgressView()
                            .controlSize(.mini)
                    } else {
                        Toggle("", isOn: Binding(
                            get: { vpn.isConnected || vpn.isConnecting },
                            set: { _ in vpn.toggle() }
                        ))
                        .toggleStyle(.switch)
                        .controlSize(.mini)
                        .labelsHidden()
                    }
                }

                if let error = vpn.connectionError {
                    HStack(spacing: 4) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }

                if vpn.isConnected {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 4) {
                            Image(systemName: "network")
                                .foregroundColor(.secondary)
                            Text("IP: \(vpn.vpnIP)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Spacer()
                            Text("\(vpn.pingMs)ms")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.down.circle")
                                .foregroundColor(.secondary)
                            Text(VPNManager.formatBytes(vpn.bytesIn))
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Spacer()
                            Image(systemName: "arrow.up.circle")
                                .foregroundColor(.secondary)
                            Text(VPNManager.formatBytes(vpn.bytesOut))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                LabeledContent("\u{0412}\u{0435}\u{0441} \u{043f}\u{0440}\u{0438}\u{0441}\u{0443}\u{0442}\u{0441}\u{0442}\u{0432}\u{0438}\u{044f}") {
                    Text("\(engine.weight)/\(engine.maxWeight) \u{0248}/\u{0441}")
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(gold)
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
