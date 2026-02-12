import Foundation
import Combine
import CoreLocation
import CoreBluetooth
import AVFoundation
import ApplicationServices
import AppKit
import ServiceManagement

struct Sensor: Identifiable {
    let id: String
    let icon: String
    let name: String
    let info: String
    var enabled: Bool
    let rate: Int
}

@MainActor
class PresenceEngine: ObservableObject {
    static let shared = PresenceEngine()

    @Published var isTracking = false
    @Published var isPresent = false
    @Published var sessionSeconds: Int = 0
    @Published var pendingSeconds: Int = 0
    @Published var serverBalance: Int = 0
    @Published var isOnline = false
    @Published var sensors: [Sensor] = []
    @Published var networkNodes: [(name: String, location: String, online: Bool)] = []
    @Published var networkHealth: String = "0%"
    @Published var networkOnline: Int = 0
    @Published var networkTotal: Int = 3
    @Published var protocolVersion: String = "2.0.0"
    @Published var protocolMode: String = "MAINNET"
    @Published var protocolCrypto: String = "ML-DSA-65 (FIPS 204)"
    @Published var ledgerVerified: Bool = false
    @Published var ledgerBalance: Int = 0
    @Published var t2BlockNumber: Int = 0
    @Published var t2SecondsElapsed: Int = 0
    @Published var t2TrackingSeconds: Int = 0
    @Published var sensorPermissions: [String: Bool] = [:]
    @Published var showBalanceInMenuBar: Bool = true
    @Published var showWeightInMenuBar: Bool = true
    // Speed/rate removed from menu bar — only Balance and Weight visibility toggles remain
    @Published var genesisDate: Date = {
        var c = DateComponents()
        c.year = 2026; c.month = 1; c.day = 9; c.hour = 0; c.minute = 0
        return Calendar.current.date(from: c) ?? Date()
    }()

    var displayBalance: Int { serverBalance + pendingSeconds }

    /// Callback fired AFTER pendingSeconds is updated in tick() — for menu bar sync
    var onTick: (() -> Void)?

    // ── GENESIS ECONOMICS ──
    // Montana Genesis: 09.01.2026 — network launch
    // Price Genesis: 12.03.2021 — BIPL (Bill Payment) price anchor
    //
    // Model: 1 second of human presence = 1 Ɉ (base rate)
    // BIPL price: 1 second = $0.1605 USD
    // RUB rate at price genesis (12.03.2021): ~75 ₽/$
    // 1 Ɉ = $0.1605 = ₽12.04
    //
    // Source: https://x.com/tojesatoshi/status/2012823709858275473
    //
    static let genesisPriceUSD: Double = 0.1605     // $0.1605 per Ɉ (BIPL)
    static let genesisPriceRUB: Double = 12.04      // ₽12.04 per Ɉ ($0.1605 × 75 ₽/$)
    static let genesisSettlementDate = "12.03.2021"

    var balanceUSD: Double { Double(displayBalance) * Self.genesisPriceUSD }
    var balanceRUB: Double { Double(displayBalance) * Self.genesisPriceRUB }

    var epochDays: Int {
        let diff = Calendar.current.dateComponents([.day], from: genesisDate, to: Date())
        return max(diff.day ?? 0, 0)
    }

    var epochNumber: Int { epochDays / 7 + 1 }

    // ╔══════════════════════════════════════════════════════════════════╗
    // ║  IMMUTABLE BLOCK — SENSOR MODEL                                 ║
    // ║  НЕ МЕНЯТЬ. Это неизменяемый блок кода.                         ║
    // ║                                                                 ║
    // ║  Правила:                                                       ║
    // ║  1. Разрешение есть + тумблер ON = датчик активен               ║
    // ║     (якорь присутствия, данные НЕ собирает/НЕ отправляет)       ║
    // ║  2. Разрешения нет ИЛИ тумблер OFF = всё выключено              ║
    // ║     (ничего не собирает, никуда не отправляет)                   ║
    // ║  3. На старте: тумблер ON без разрешения → автоотключение        ║
    // ║  4. Вес = активные датчики + 1 (базовое присутствие) + VPN      ║
    // ╚══════════════════════════════════════════════════════════════════╝
    var weight: Int {
        sensors.filter { $0.enabled && (sensorPermissions[$0.id] ?? false) }.reduce(0) { $0 + $1.rate } + 1 + (VPNManager.shared.isConnected ? 1 : 0)
    }

    let t2Duration = 600

    var t2SecondsRemaining: Int { max(t2Duration - t2SecondsElapsed, 0) }
    var t2Progress: Double { min(Double(t2SecondsElapsed) / Double(t2Duration), 1.0) }
    var t2PendingCoins: Int { t2TrackingSeconds * weight }

    var maxWeight: Int {
        let v = UserDefaults.standard.integer(forKey: "montana_max_weight")
        return v > 0 ? min(max(v, 1), 20) : 10
    }

    var ratePerSecond: Int { weight }

    private var tickTimer: Timer?
    private var reportTimer: Timer?
    private var tickCount = 0
    private let pendingKey = "montana_presence_pending"
    private let balanceKey = "montana_presence_balance"
    let api = MontanaAPIClient()

    // Permission managers (retained for dialog lifecycle)
    private var locationManager: CLLocationManager?
    private var bluetoothManager: CBCentralManager?

    private init() {
        pendingSeconds = UserDefaults.standard.integer(forKey: pendingKey)
        serverBalance = UserDefaults.standard.integer(forKey: balanceKey)
        showBalanceInMenuBar = UserDefaults.standard.object(forKey: "menubar_balance") as? Bool ?? true
        showWeightInMenuBar = UserDefaults.standard.object(forKey: "menubar_weight") as? Bool ?? true
        // showRateInMenuBar removed — speed display eliminated
        migrateActivitySensor()
        registerSensorDefaults()
        loadSensors()
        updateT2()
        refreshPermissions()
    }

    // Migration: reset all sensors to OFF on first run with new defaults
    private func migrateActivitySensor() {
        if !UserDefaults.standard.bool(forKey: "sensor_defaults_off_v1") {
            for key in ["sensor_camera", "sensor_mic", "sensor_location", "sensor_activity",
                        "sensor_bluetooth", "sensor_wifi", "sensor_autostart"] {
                UserDefaults.standard.set(false, forKey: key)
            }
            UserDefaults.standard.set(true, forKey: "sensor_defaults_off_v1")
        }
    }

    private func registerSensorDefaults() {
        // Sensors are ANCHORS of presence — they verify sensor availability,
        // NOT collect or transmit data. Each permission = proof of anchor = +1 weight.
        // Default: ALL OFF. User grants permission → sensor auto-enables via transition sync.
        let defaults: [String: Any] = [
            "sensor_camera": false,
            "sensor_mic": false,
            "sensor_location": false,
            "sensor_activity": false,
            "sensor_bluetooth": false,
            "sensor_wifi": false,
            "sensor_autostart": false
        ]
        UserDefaults.standard.register(defaults: defaults)
    }

    private func loadSensors() {
        let d = UserDefaults.standard
        sensors = [
            Sensor(id: "camera", icon: "camera.fill",
                   name: "Камера",
                   info: "Камера как якорь присутствия. Видео не записывается и не отправляется.",
                   enabled: d.bool(forKey: "sensor_camera"), rate: 1),
            Sensor(id: "mic", icon: "mic.fill",
                   name: "Микрофон",
                   info: "Детекция присутствия по звуку. Звук не записывается и не отправляется.",
                   enabled: d.bool(forKey: "sensor_mic"), rate: 1),
            Sensor(id: "location", icon: "location.fill",
                   name: "Локация",
                   info: "Подтверждение геопозиции. Координаты не передаются — только факт доступа.",
                   enabled: d.bool(forKey: "sensor_location"), rate: 1),
            Sensor(id: "activity", icon: "desktopcomputer",
                   name: "Активность",
                   info: "Мониторинг активности клавиатуры и мыши. Нажатия не записываются.",
                   enabled: d.bool(forKey: "sensor_activity"), rate: 1),
            Sensor(id: "bluetooth", icon: "wave.3.right",
                   name: "Bluetooth",
                   info: "Обнаружение устройств поблизости. MAC-адреса не собираются.",
                   enabled: d.bool(forKey: "sensor_bluetooth"), rate: 1),
            Sensor(id: "wifi", icon: "wifi",
                   name: "Wi-Fi",
                   info: "Проверка подключения к сети. SSID не отправляется.",
                   enabled: d.bool(forKey: "sensor_wifi"), rate: 1),
            Sensor(id: "autostart", icon: "clock.arrow.circlepath",
                   name: "Автозапуск",
                   info: "Запуск при входе в систему. Непрерывный майнинг присутствия.",
                   enabled: d.bool(forKey: "sensor_autostart"), rate: 1),
        ]
    }

    func requestLocationPermission() {
        locationManager = CLLocationManager()
        locationManager?.requestAlwaysAuthorization()
    }

    func requestBluetoothPermission() {
        bluetoothManager = CBCentralManager(delegate: nil, queue: nil)
    }

    func requestPermission(for sensorId: String) {
        switch sensorId {
        case "camera":
            let status = AVCaptureDevice.authorizationStatus(for: .video)
            if status == .notDetermined {
                AVCaptureDevice.requestAccess(for: .video) { _ in
                    Task { @MainActor in self.refreshPermissions() }
                }
            } else {
                openSystemSettings("Privacy_Camera")
            }
        case "mic":
            let status = AVCaptureDevice.authorizationStatus(for: .audio)
            if status == .notDetermined {
                AVCaptureDevice.requestAccess(for: .audio) { _ in
                    Task { @MainActor in self.refreshPermissions() }
                }
            } else {
                openSystemSettings("Privacy_Microphone")
            }
        case "location":
            let locMgr = CLLocationManager()
            let status = locMgr.authorizationStatus
            if status == .notDetermined {
                requestLocationPermission()
            } else {
                openSystemSettings("Privacy_LocationServices")
            }
        case "bluetooth":
            let btAuth = CBManager.authorization
            if btAuth == .notDetermined {
                requestBluetoothPermission()
            } else {
                openSystemSettings("Privacy_Bluetooth")
            }
        case "activity", "appdata":
            let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
            AXIsProcessTrustedWithOptions(options)
        case "wifi":
            let locMgr2 = CLLocationManager()
            let locStat = locMgr2.authorizationStatus
            if locStat == .notDetermined {
                requestLocationPermission()
            } else {
                openSystemSettings("Privacy_LocationServices")
            }
        case "autostart":
            try? SMAppService.mainApp.register()
            openLoginItemsSettings()
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                self.refreshPermissions()
            }
        default:
            openSystemSettings("Privacy")
        }
    }

    private func openSystemSettings(_ pane: String) {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?\(pane)") {
            NSWorkspace.shared.open(url)
        }
    }

    private func openLoginItemsSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.LoginItems-Settings.extension") {
            NSWorkspace.shared.open(url)
        }
    }

    func toggleMenuBarBalance() {
        showBalanceInMenuBar.toggle()
        UserDefaults.standard.set(showBalanceInMenuBar, forKey: "menubar_balance")
    }

    func toggleMenuBarWeight() {
        showWeightInMenuBar.toggle()
        UserDefaults.standard.set(showWeightInMenuBar, forKey: "menubar_weight")
    }

    /// Available balance = everything confirmed BEFORE current T2 window
    var availableBalance: Int { max(displayBalance - t2PendingCoins, 0) }

    func toggleSensor(_ id: String) {
        if let idx = sensors.firstIndex(where: { $0.id == id }) {
            sensors[idx].enabled.toggle()
            UserDefaults.standard.set(sensors[idx].enabled, forKey: "sensor_\(id)")

            // Autostart: sync with SMAppService + open Login Items
            if id == "autostart" {
                if sensors[idx].enabled {
                    try? SMAppService.mainApp.register()
                } else {
                    try? SMAppService.mainApp.unregister()
                }
                openLoginItemsSettings()
            }
        }
    }

    func refreshPermissions() {
        let camStatus = AVCaptureDevice.authorizationStatus(for: .video)
        let micStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        let locMgr = CLLocationManager()
        let locStatus = locMgr.authorizationStatus
        let btAuth = CBManager.authorization

        let oldPermissions = sensorPermissions

        let axTrusted = AXIsProcessTrusted()
        let locGranted = locStatus == .authorizedAlways || locStatus == .authorized

        sensorPermissions = [
            "camera": camStatus == .authorized,
            "mic": micStatus == .authorized,
            "location": locGranted,
            "bluetooth": btAuth == .allowedAlways,
            "activity": axTrusted,
            "wifi": true,  // Wi-Fi не требует разрешения на macOS — чистый якорь
            "autostart": SMAppService.mainApp.status == .enabled,
        ]

        // ╔══════════════════════════════════════════════════════════════════╗
        // ║  IMMUTABLE BLOCK — PERMISSION SYNC                              ║
        // ║  НЕ МЕНЯТЬ. Это неизменяемый блок кода.                         ║
        // ║                                                                 ║
        // ║  Первый вызов (старт приложения):                               ║
        // ║  - НЕ включать датчики автоматически                            ║
        // ║  - ВЫКЛЮЧИТЬ датчики у которых тумблер ON но разрешения нет     ║
        // ║  → UI не врёт: если тумблер ON, датчик реально считается        ║
        // ║                                                                 ║
        // ║  Последующие вызовы (transition sync):                          ║
        // ║  - Разрешение дано → автовключение                              ║
        // ║  - Разрешение отозвано → автоотключение                         ║
        // ║  - Без изменений → уважаем выбор пользователя                   ║
        // ╚══════════════════════════════════════════════════════════════════╝
        if oldPermissions.isEmpty {
            // First call: don't auto-enable, but auto-disable sensors without permission
            for (id, allowed) in sensorPermissions {
                if !allowed, let idx = sensors.firstIndex(where: { $0.id == id }), sensors[idx].enabled {
                    sensors[idx].enabled = false
                    UserDefaults.standard.set(false, forKey: "sensor_\(id)")
                }
            }
            return
        }
        for (id, allowed) in sensorPermissions {
            let wasAllowed = oldPermissions[id] ?? false
            if let idx = sensors.firstIndex(where: { $0.id == id }) {
                if allowed && !wasAllowed {
                    // Permission just granted → enable
                    sensors[idx].enabled = true
                    UserDefaults.standard.set(true, forKey: "sensor_\(id)")
                } else if !allowed && wasAllowed {
                    // Permission just revoked → disable
                    sensors[idx].enabled = false
                    UserDefaults.standard.set(false, forKey: "sensor_\(id)")
                }
            }
        }
    }

    var address: String? {
        get { UserDefaults.standard.string(forKey: "montana_address") }
        set { UserDefaults.standard.set(newValue, forKey: "montana_address") }
    }

    var walletNumber: Int {
        UserDefaults.standard.integer(forKey: "wallet_number")
    }

    var displayAddress: String {
        let num = walletNumber
        if num > 0 { return "\u{0248}-\(num)" }
        if let addr = address { return String(addr.prefix(8)) + "..." + String(addr.suffix(4)) }
        return ""
    }

    func autoStart() {
        guard address != nil, !address!.isEmpty, !isTracking else { return }
        // Auto-request camera permission and start tracking
        startTracking()
    }

    func startTracking() {
        guard address != nil, !isTracking else { return }
        isTracking = true
        isPresent = true  // Always present when tracking — timer ticks immediately
        sessionSeconds = 0
        t2TrackingSeconds = 0
        refreshPermissions()
        if sensorPermissions["camera"] == true {
            CameraManager.shared.startCamera()
        }
        tickTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
        reportTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.reportToServer() }
        }
        Task { await syncBalance() }
    }

    func stopTracking() {
        isTracking = false
        isPresent = false
        tickTimer?.invalidate()
        tickTimer = nil
        reportTimer?.invalidate()
        reportTimer = nil
        CameraManager.shared.stopCamera()
        Task { await reportToServer() }
    }

    // isPresent stays true while tracking — app running = presence proved

    private func tick() {
        guard isTracking else { return }
        // Re-check permissions every 5 seconds so toggling in System Settings is auto-detected
        if tickCount % 5 == 0 {
            refreshPermissions()
        }
        let w = weight
        sessionSeconds += 1
        pendingSeconds += w
        tickCount += 1
        updateT2()
        t2TrackingSeconds += 1
        if tickCount % 10 == 0 {
            UserDefaults.standard.set(pendingSeconds, forKey: pendingKey)
        }
        onTick?()
    }

    func updateT2() {
        let secs = max(Int(Date().timeIntervalSince(genesisDate)), 0)
        let newBlock = secs / t2Duration
        if newBlock != t2BlockNumber {
            t2TrackingSeconds = 0
        }
        t2BlockNumber = newBlock
        t2SecondsElapsed = secs % t2Duration
    }

    func reportToServer() async {
        guard let addr = address, !addr.isEmpty, pendingSeconds > 0 else { return }
        let delta = pendingSeconds
        do {
            let balance = try await api.reportPresence(address: addr, seconds: delta)
            serverBalance = balance
            pendingSeconds = 0
            isOnline = true
            UserDefaults.standard.set(0, forKey: pendingKey)
            UserDefaults.standard.set(serverBalance, forKey: balanceKey)
        } catch {
            isOnline = false
            UserDefaults.standard.set(pendingSeconds, forKey: pendingKey)
        }
    }

    func syncBalance() async {
        guard let addr = address, !addr.isEmpty else { return }
        do {
            let balance = try await api.fetchBalance(address: addr)
            serverBalance = balance
            isOnline = true
            UserDefaults.standard.set(serverBalance, forKey: balanceKey)
        } catch {
            isOnline = false
        }

        // Sync network status
        do {
            let (net, proto) = try await api.fetchStatus()
            networkNodes = net.nodes
            networkOnline = net.onlineCount
            networkTotal = net.totalNodes
            networkHealth = net.health
            protocolVersion = proto.version
            protocolMode = proto.mode
            protocolCrypto = proto.crypto
        } catch {}

        // Sync ledger verification
        do {
            let verify = try await api.fetchLedgerVerify(address: addr)
            ledgerVerified = verify.verified
            ledgerBalance = verify.ledgerBalance
        } catch {}
    }
}
