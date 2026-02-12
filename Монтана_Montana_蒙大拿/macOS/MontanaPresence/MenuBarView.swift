import SwiftUI
import AppKit

struct MenuBarView: View {
    @EnvironmentObject var engine: PresenceEngine
    @EnvironmentObject var camera: CameraManager
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var vpn: VPNManager
    @State private var showSend = false
    @State private var showReceive = false
    @State private var showSensorInfo: String? = nil
    @State private var showNetworkNodes = false

    // Montana palette — gold coin aesthetic
    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)
    private let goldLight = Color(red: 0.95, green: 0.82, blue: 0.45)
    private let goldDim = Color(red: 0.6, green: 0.48, blue: 0.18)
    private let bg = Color(red: 0.06, green: 0.06, blue: 0.08)
    private let cardBg = Color(red: 0.09, green: 0.09, blue: 0.12)
    private let dividerColor = Color(red: 0.15, green: 0.14, blue: 0.12)

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                // ── BALANCE HEADER ──
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .firstTextBaseline) {
                        Text("\(formatNumber(engine.displayBalance))")
                            .font(.system(size: 34, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                        Text("\u{0248}")
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(gold)
                        Spacer()
                        Text(formatDuration(engine.sessionSeconds))
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(goldDim)
                    }

                    HStack(spacing: 8) {
                        Text(engine.displayAddress)
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.35))
                        Spacer()
                        Text("\u{2248}$\(formatCurrency(engine.balanceUSD))")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                        Text("\u{2248}\(formatCurrency(engine.balanceRUB))\u{20bd}")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                    }

                    HStack {
                        Text("+\(engine.ratePerSecond) \u{0248}/\u{0441}\u{0435}\u{043a}")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(goldLight)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 10)

                sep()

                // ── MENU BAR DISPLAY ──
                VStack(spacing: 2) {
                    menuBarRow(icon: "number", name: "\u{0411}\u{0430}\u{043b}\u{0430}\u{043d}\u{0441}", enabled: engine.showBalanceInMenuBar) {
                        engine.toggleMenuBarBalance()
                    }
                    menuBarRow(icon: "scalemass", name: "\u{0412}\u{0435}\u{0441}", enabled: engine.showWeightInMenuBar) {
                        engine.toggleMenuBarWeight()
                    }
                    menuBarRow(icon: "speedometer", name: "\u{0421}\u{043a}\u{043e}\u{0440}\u{043e}\u{0441}\u{0442}\u{044c}", enabled: engine.showRateInMenuBar) {
                        engine.toggleMenuBarRate()
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── SEND / RECEIVE ──
                HStack(spacing: 8) {
                    Button(action: { showSend = true }) {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 13))
                            Text("\u{041e}\u{0442}\u{043f}\u{0440}\u{0430}\u{0432}\u{0438}\u{0442}\u{044c}")
                                .font(.system(size: 13, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(gold.opacity(0.15))
                        .foregroundColor(gold)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(gold.opacity(0.3), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .popover(isPresented: $showSend) {
                        SendView().environmentObject(engine)
                    }

                    Button(action: { showReceive = true }) {
                        HStack(spacing: 4) {
                            Image(systemName: "arrow.down.circle.fill")
                                .font(.system(size: 13))
                            Text("\u{041f}\u{043e}\u{043b}\u{0443}\u{0447}\u{0438}\u{0442}\u{044c}")
                                .font(.system(size: 13, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(goldDim.opacity(0.15))
                        .foregroundColor(goldLight)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(goldDim.opacity(0.3), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .popover(isPresented: $showReceive) {
                        ReceiveView().environmentObject(engine)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

                sep()

                // ── КОШЕЛЁК ──
                VStack(spacing: 4) {
                    row(icon: engine.ledgerVerified ? "checkmark.shield.fill" : "shield.slash",
                        iconColor: engine.ledgerVerified ? .green : .orange,
                        label: "\u{041a}\u{043e}\u{0448}\u{0435}\u{043b}\u{0451}\u{043a}",
                        value: engine.ledgerVerified ? "\u{0432}\u{0435}\u{0440}\u{0438}\u{0444}\u{0438}\u{0446}\u{0438}\u{0440}\u{043e}\u{0432}\u{0430}\u{043d}" : "\u{043d}\u{0435} \u{043f}\u{0440}\u{043e}\u{0432}\u{0435}\u{0440}\u{0435}\u{043d}",
                        valueColor: engine.ledgerVerified ? .green : .orange)

                    row(icon: "doc.text.magnifyingglass",
                        iconColor: goldDim,
                        label: "\u{0411}\u{0430}\u{043b}\u{0430}\u{043d}\u{0441} \u{043a}\u{043e}\u{0448}\u{0435}\u{043b}\u{044c}\u{043a}\u{0430}",
                        value: "\(formatNumber(engine.ledgerBalance)) \u{0248}",
                        valueColor: Color.white.opacity(0.5))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── ТАЙЧЕЙН T2 ──
                VStack(spacing: 4) {
                    HStack(spacing: 6) {
                        Image(systemName: "cube.fill")
                            .font(.system(size: 12))
                            .frame(width: 18)
                            .foregroundColor(gold)
                        Text("\u{041e}\u{043a}\u{043d}\u{043e} #\(formatNumber(engine.t2BlockNumber))")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(Color.white.opacity(0.8))
                        Spacer()
                        Text(formatT2Time(engine.t2SecondsRemaining))
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(goldDim)
                        Image(systemName: "arrow.right")
                            .font(.system(size: 8))
                            .foregroundColor(Color.white.opacity(0.15))
                    }

                    // Progress bar
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Color.white.opacity(0.05))
                                .frame(height: 6)
                            RoundedRectangle(cornerRadius: 3)
                                .fill(
                                    LinearGradient(
                                        colors: [goldDim, gold, goldLight],
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    )
                                )
                                .frame(width: max(geo.size.width * engine.t2Progress, 2), height: 6)
                        }
                    }
                    .frame(height: 6)

                    HStack {
                        Text("+\(formatNumber(engine.t2PendingCoins)) \u{0248}")
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                            .foregroundColor(goldLight)
                        Text("\u{043d}\u{0430}\u{0447}\u{0438}\u{0441}\u{043b}\u{0435}\u{043d}\u{043e}")
                            .font(.system(size: 10))
                            .foregroundColor(Color.white.opacity(0.3))
                        Spacer()
                        Text("T\u{2082} = 10 \u{043c}\u{0438}\u{043d}")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.2))
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── SENSORS ──
                VStack(spacing: 2) {
                    sensorRow(icon: "person.fill", name: "\u{041f}\u{0440}\u{0438}\u{0441}\u{0443}\u{0442}\u{0441}\u{0442}\u{0432}\u{0438}\u{0435}", rate: "+1 \u{0248}/\u{0441}", enabled: true, isFixed: true)

                    ForEach(engine.sensors) { sensor in
                        let hasPermission = engine.sensorPermissions[sensor.id] ?? false
                        let isActive = sensor.enabled && hasPermission
                        HStack(spacing: 6) {
                            Image(systemName: sensor.icon)
                                .font(.system(size: 12))
                                .frame(width: 18)
                                .foregroundColor(isActive ? gold : Color.white.opacity(0.2))
                            Text(sensor.name)
                                .font(.system(size: 12))
                                .foregroundColor(Color.white.opacity(isActive ? 0.7 : 0.35))

                            Button(action: {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    showSensorInfo = showSensorInfo == sensor.id ? nil : sensor.id
                                }
                            }) {
                                Image(systemName: "info.circle")
                                    .font(.system(size: 9))
                                    .foregroundColor(Color.white.opacity(0.2))
                            }
                            .buttonStyle(.plain)

                            Spacer()

                            if isActive {
                                Text("+\(sensor.rate) \u{0248}/\u{0441}")
                                    .font(.system(size: 10, design: .monospaced))
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
                        .padding(.vertical, 1)

                        if showSensorInfo == sensor.id {
                            Text(sensor.info)
                                .font(.system(size: 9))
                                .foregroundColor(Color.white.opacity(0.3))
                                .padding(.leading, 24)
                                .transition(.opacity)
                        }
                    }

                    // ── VPN ──
                    HStack(spacing: 6) {
                        Image(systemName: "lock.shield.fill")
                            .font(.system(size: 12))
                            .frame(width: 18)
                            .foregroundColor(vpn.isConnected ? gold : Color.white.opacity(0.2))
                        Text("VPN")
                            .font(.system(size: 12))
                            .foregroundColor(Color.white.opacity(vpn.isConnected ? 0.7 : 0.35))

                        if vpn.isConnected {
                            Text(vpn.vpnIP)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundColor(Color.white.opacity(0.3))
                            if vpn.pingMs > 0 {
                                Text("\(vpn.pingMs)ms")
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundColor(Color.white.opacity(0.3))
                            }
                        }

                        Spacer()

                        if vpn.isConnected {
                            Text("+1 \u{0248}/\u{0441}")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundColor(goldLight)
                        }

                        if vpn.isConnecting {
                            ProgressView()
                                .controlSize(.mini)
                        } else {
                            Toggle("", isOn: Binding(
                                get: { vpn.isConnected },
                                set: { _ in vpn.toggle() }
                            ))
                            .toggleStyle(.switch)
                            .controlSize(.mini)
                            .labelsHidden()
                        }
                    }
                    .padding(.vertical, 1)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── WEIGHT ──
                HStack {
                    Text("\u{0412}\u{0435}\u{0441} \u{043f}\u{0440}\u{0438}\u{0441}\u{0443}\u{0442}\u{0441}\u{0442}\u{0432}\u{0438}\u{044f}:")
                        .font(.system(size: 11))
                        .foregroundColor(Color.white.opacity(0.4))
                    Spacer()
                    Text("\(engine.weight)/\(engine.maxWeight) \u{0248}/\u{0441}")
                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                        .foregroundColor(gold)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── NETWORK NODES ──
                VStack(spacing: 4) {
                    Button(action: {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            showNetworkNodes.toggle()
                        }
                    }) {
                        HStack {
                            Image(systemName: "network")
                                .font(.system(size: 12))
                                .frame(width: 18)
                                .foregroundColor(gold)
                            Text("\u{0421}\u{0435}\u{0442}\u{044c} Montana")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(Color.white.opacity(0.8))
                            Spacer()
                            Text("\(engine.networkOnline)/\(engine.networkTotal) \u{0443}\u{0437}\u{043b}\u{043e}\u{0432}")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundColor(engine.networkOnline == engine.networkTotal ? .green : .orange)
                            Image(systemName: showNetworkNodes ? "chevron.up" : "chevron.down")
                                .font(.system(size: 8))
                                .foregroundColor(Color.white.opacity(0.2))
                        }
                    }
                    .buttonStyle(.plain)

                    if showNetworkNodes {
                        ForEach(Array(engine.networkNodes.enumerated()), id: \.offset) { _, node in
                            HStack(spacing: 6) {
                                Circle()
                                    .fill(node.online ? Color.green : Color.red)
                                    .frame(width: 5, height: 5)
                                Text(node.name)
                                    .font(.system(size: 10))
                                    .foregroundColor(Color.white.opacity(0.5))
                                Spacer()
                                Text(node.online ? "\u{043e}\u{043d}\u{043b}\u{0430}\u{0439}\u{043d}" : "\u{043e}\u{0444}\u{043b}\u{0430}\u{0439}\u{043d}")
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundColor(node.online ? .green : .red)
                            }
                            .padding(.leading, 24)
                        }
                        .transition(.opacity)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── EPOCH / GENESIS ──
                VStack(spacing: 3) {
                    HStack(spacing: 6) {
                        Image(systemName: "calendar.badge.clock")
                            .font(.system(size: 11))
                            .frame(width: 18)
                            .foregroundColor(gold)
                        Text("\u{042d}\u{043f}\u{043e}\u{0445}\u{0430} #\(engine.epochNumber)")
                            .font(.system(size: 11))
                            .foregroundColor(Color.white.opacity(0.7))
                        Spacer()
                        Text("\u{0434}\u{0435}\u{043d}\u{044c} \(engine.epochDays)")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.35))
                    }

                    HStack(spacing: 6) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 11))
                            .frame(width: 18)
                            .foregroundColor(goldDim)
                        Text("\u{0413}\u{0435}\u{043d}\u{0435}\u{0437}\u{0438}\u{0441}")
                            .font(.system(size: 11))
                            .foregroundColor(Color.white.opacity(0.4))
                        Spacer()
                        Text("09.01.2026")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                    }

                    HStack(spacing: 6) {
                        Image(systemName: "dollarsign.circle")
                            .font(.system(size: 11))
                            .frame(width: 18)
                            .foregroundColor(goldDim)
                        Text("1 \u{0248}")
                            .font(.system(size: 11))
                            .foregroundColor(Color.white.opacity(0.4))
                        Spacer()
                        Text("$\(String(format: "%.4f", PresenceEngine.genesisPriceUSD))")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                        Text("\(String(format: "%.2f", PresenceEngine.genesisPriceRUB))\u{20bd}")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                    }

                    HStack(spacing: 6) {
                        Image(systemName: "banknote")
                            .font(.system(size: 11))
                            .frame(width: 18)
                            .foregroundColor(goldDim)
                        Text("\u{0413}\u{0435}\u{043d}\u{0435}\u{0437}\u{0438}\u{0441} \u{0426}\u{0435}\u{043d}\u{044b}")
                            .font(.system(size: 11))
                            .foregroundColor(Color.white.opacity(0.4))
                        Spacer()
                        Text(PresenceEngine.genesisSettlementDate)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── STATUS ──
                VStack(spacing: 3) {
                    HStack {
                        Circle()
                            .fill(engine.isOnline ? Color.green : Color.orange)
                            .frame(width: 6, height: 6)
                        Text(engine.isOnline ? "\u{041f}\u{043e}\u{0434}\u{043a}\u{043b}\u{044e}\u{0447}\u{0435}\u{043d}" : "\u{041e}\u{0444}\u{043b}\u{0430}\u{0439}\u{043d}")
                            .font(.system(size: 11))
                            .foregroundColor(Color.white.opacity(0.4))
                        if engine.pendingSeconds > 0 {
                            Spacer()
                            Text("+\(engine.pendingSeconds) \u{043e}\u{0436}\u{0438}\u{0434}\u{0430}\u{0435}\u{0442}")
                                .font(.system(size: 10))
                                .foregroundColor(.orange)
                        }
                    }

                    HStack(spacing: 5) {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 9))
                            .foregroundColor(goldDim)
                        Text(engine.protocolCrypto)
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.3))
                        Spacer()
                        Text(engine.protocolMode)
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(.green)
                        Text("v\(engine.protocolVersion)")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(Color.white.opacity(0.25))
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 6)

                sep()

                // ── CONTROLS ──
                VStack(spacing: 6) {
                    Button(action: {
                        if engine.isTracking {
                            engine.stopTracking()
                        } else {
                            engine.startTracking()
                        }
                    }) {
                        HStack(spacing: 6) {
                            Image(systemName: engine.isTracking ? "stop.circle.fill" : "play.circle.fill")
                                .font(.system(size: 14))
                            Text(engine.isTracking ? "\u{0421}\u{0442}\u{043e}\u{043f}" : "\u{0421}\u{0442}\u{0430}\u{0440}\u{0442}")
                                .font(.system(size: 14, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(engine.isTracking ?
                            Color.red.opacity(0.15) : gold.opacity(0.2))
                        .foregroundColor(engine.isTracking ? .red : gold)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(
                            engine.isTracking ? Color.red.opacity(0.3) : gold.opacity(0.3), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .disabled(engine.address == nil || engine.address?.isEmpty == true)

                    HStack {
                        Button(action: {
                            NSApp.activate(ignoringOtherApps: true)
                            if #available(macOS 14.0, *) {
                                NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                            } else {
                                NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
                            }
                        }) {
                            Text("\u{041d}\u{0430}\u{0441}\u{0442}\u{0440}\u{043e}\u{0439}\u{043a}\u{0438}")
                                .font(.system(size: 11))
                                .foregroundColor(Color.white.opacity(0.4))
                        }
                        .buttonStyle(.plain)
                        .keyboardShortcut(",", modifiers: .command)

                        Spacer()

                        Text("v\(appVersion)")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(goldDim.opacity(0.6))

                        Spacer()

                        Button(action: {
                            NSApplication.shared.terminate(nil)
                        }) {
                            Text("\u{0412}\u{044b}\u{0445}\u{043e}\u{0434}")
                                .font(.system(size: 11))
                                .foregroundColor(Color.white.opacity(0.3))
                        }
                        .buttonStyle(.plain)
                        .keyboardShortcut("q", modifiers: .command)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

                // ── VERSION FOOTER ──
                HStack {
                    Text("Montana \u{0248} v\(appVersion)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(Color.white.opacity(0.15))
                    Spacer()
                    Text("@junomoneta")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(goldDim.opacity(0.4))
                    Spacer()
                    Text("build \(appBuild)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(Color.white.opacity(0.1))
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 8)
            }
        }
        .frame(width: 320, height: 720)
        .background(bg)
        .onAppear {
            engine.refreshPermissions()
            engine.updateT2()
            Task { await engine.syncBalance() }
        }
    }

    // ── Version ──

    private var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "2.10.0"
    }

    private var appBuild: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "27"
    }

    // ── Helpers ──

    @ViewBuilder
    private func sep() -> some View {
        dividerColor.frame(height: 0.5)
            .padding(.horizontal, 12)
    }

    @ViewBuilder
    private func row(icon: String, iconColor: Color, label: String, value: String, valueColor: Color) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .frame(width: 18)
                .foregroundColor(iconColor)
            Text(label)
                .font(.system(size: 11))
                .foregroundColor(Color.white.opacity(0.6))
            Spacer()
            Text(value)
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(valueColor)
        }
    }

    @ViewBuilder
    private func sensorRow(icon: String, name: String, rate: String, enabled: Bool, isFixed: Bool = false) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .frame(width: 18)
                .foregroundColor(enabled ? gold : Color.white.opacity(0.2))
            Text(name)
                .font(.system(size: 12))
                .foregroundColor(Color.white.opacity(0.7))
            Spacer()
            Text(rate)
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(goldLight)
        }
        .padding(.vertical, 1)
    }

    @ViewBuilder
    private func menuBarRow(icon: String, name: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .frame(width: 18)
                .foregroundColor(enabled ? gold : Color.white.opacity(0.2))
            Text(name)
                .font(.system(size: 12))
                .foregroundColor(Color.white.opacity(0.7))
            Spacer()
            Toggle("", isOn: Binding(
                get: { enabled },
                set: { _ in action() }
            ))
            .toggleStyle(.switch)
            .controlSize(.mini)
            .labelsHidden()
        }
        .padding(.vertical, 1)
    }

    private func formatNumber(_ n: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = ","
        return formatter.string(from: NSNumber(value: n)) ?? "\(n)"
    }

    private func formatT2Time(_ seconds: Int) -> String {
        let m = seconds / 60
        let s = seconds % 60
        return String(format: "%d:%02d", m, s)
    }

    private func formatDuration(_ seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        let s = seconds % 60
        return String(format: "%d:%02d:%02d", h, m, s)
    }

    private func formatCurrency(_ value: Double) -> String {
        if value < 1 {
            return String(format: "%.2f", value)
        } else if value < 100 {
            return String(format: "%.1f", value)
        } else {
            let formatter = NumberFormatter()
            formatter.numberStyle = .decimal
            formatter.maximumFractionDigits = 0
            formatter.groupingSeparator = ","
            return formatter.string(from: NSNumber(value: value)) ?? String(format: "%.0f", value)
        }
    }

}
