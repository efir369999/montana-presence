import Foundation
import Network
import AppKit
import Security
import NetworkExtension

@MainActor
class VPNManager: ObservableObject {
    static let shared = VPNManager()

    // Public API (same as before — PresenceEngine IMMUTABLE BLOCK compatible)
    @Published var isConnected = false
    @Published var isConnecting = false
    @Published var isConfigured = false
    @Published var vpnIP: String = ""
    @Published var pingMs: Int = 0
    @Published var serverLocation: String = "Amsterdam"

    // Conflict detection
    @Published var hasConflictingVPN = false
    @Published var conflictingVPNName: String = ""
    @Published var isProfileInstalled = false
    @Published var connectionError: String? = nil
    @Published var needsProfileInstall = false

    // Real traffic stats (bytes via netstat)
    @Published var bytesIn: Int64 = 0
    @Published var bytesOut: Int64 = 0
    @Published var vpnInterface: String = ""
    @Published var sessionStart: Date? = nil

    var sessionDuration: Int {
        guard let start = sessionStart else { return 0 }
        return max(Int(Date().timeIntervalSince(start)), 0)
    }

    // IKEv2 config
    private let serverAddress = "72.56.102.240"
    private let ikev2Subnet = "10.77.77"
    private let wgSubnet = "10.66.66"
    private let eapUser = "montana"
    private let eapPassword = "M0ntana!VPN#2026"
    private let vpnServiceName = "Montana VPN"

    // NEVPNManager — programmatic VPN control (like HIT VPN)
    private let neManager = NEVPNManager.shared()
    private var useNEVPN = true // primary mode, falls back to mobileconfig if entitlement fails

    // Monitoring
    private var pathMonitor: NWPathMonitor?
    private var checkTimer: Timer?
    private var sessionTimer: Timer?

    // Mobileconfig fallback
    private let profileIdentifier = "network.montana.vpn.profile"
    private let stableProfileUUID = "A1B2C3D4-1234-5678-9ABC-DEF012345678"
    private let stableCaUUID = "B2C3D4E5-2345-6789-ABCD-EF0123456789"
    private let stableVpnUUID = "C3D4E5F6-3456-789A-BCDE-F01234567890"
    private var profileWaitTimer: Timer?
    private var userCancelledConnect = false

    private var profileDir: URL {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        return appSupport.appendingPathComponent("Montana")
    }
    private var profilePath: String {
        profileDir.appendingPathComponent("MontanaVPN.mobileconfig").path
    }

    // Montana Protocol CA certificate (DER format, base64)
    // Organization: Montana Protocol, CN: Montana Protocol CA
    // Valid: 2026-02-12 to 2036-02-10 (10 years)
    private let caCertBase64 = "MIIFUDCCAzigAwIBAgIIC2LcP0IMpEQwDQYJKoZIhvcNAQEMBQAwRjELMAkGA1UEBhMCTkwxGTAXBgNVBAoTEE1vbnRhbmEgUHJvdG9jb2wxHDAaBgNVBAMTE01vbnRhbmEgUHJvdG9jb2wgQ0EwHhcNMjYwMjEyMTg0NjI1WhcNMzYwMjEwMTg0NjI1WjBGMQswCQYDVQQGEwJOTDEZMBcGA1UEChMQTW9udGFuYSBQcm90b2NvbDEcMBoGA1UEAxMTTW9udGFuYSBQcm90b2NvbCBDQTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAKVVV1k/osHjWrHJ8h9wNQRD6qiTUYXRM1BaFotVPNuguc3fT6h70t3aCL7ebYLccIH9LidRw/KSPYsSpm6eYNWDKsaYuv0S5uYA0SzRYSGtD8ZcEEzoDYIFr+S5hK1GS6Fj1dWdRw2K054kRhTSe7mwkgi+826Mni0ImxYxAL3Z/Ys51Dp+supFDEtJLe5/i3YiBiyIF6qwMb8liLb4TNgB3UOq70fCj+gJ1wKTS31eM/vmcU3hJBmOYWok6LtVw3XQzfIzavz3qETIQ0sBNrJtiJf/27SRZXghmIsqHKKEnRiEdI0IBwMQqscZQP7T4Qr+AWOj27wxZU3aWEl09Sum/+Nb/fp3fREZGkgfQ+vznOVha24R4KIUvbLvsQOwwo9RqtJQQIBDqON+PRhPRIJD6QEOZLry4L/x99SPADSh3u9ORiP+PjhPwkun9wFrxsgvFbbDznJZjCYHGKi+stHQ/vMZenr3KnyFl3wUY0KXEpt5Z6bmQK4wm3+qnvOVwM+32UuKzVT2PuzzwzEQZ4Moj8PCV+EPPF5fpkEcqvvvQQIi0h1B04AIctq2PTWcqgr3jODpFZ6e0WgwYRpRWF4WzUrYnItPUnKJZnLO1DfeDVr74tQgm/01xZ7WEp5Y2XZajQN+nyFRVpInX/Y7ZFTXj0wpTXUhQBAzp56pHHvbAgMBAAGjQjBAMA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMB0GA1UdDgQWBBQx8gTH4Vc3A1B760FYnJxrMNd4KjANBgkqhkiG9w0BAQwFAAOCAgEAaDbU9XmANCY9CQuEWeQB6uGlX/rIM58ZUQdkKx5/XkCvfijKEeuMvEvrsQOydHJkp/VDZsVbMV7/3trIs5NJ+2zv5RX7YCweMfY8EMj8kbEbs5b1Z0eXz03IU3+V0vrqEBJTq+5xuXYWJVFz/amWX1U0XqmKabS1NIG/jw8WL60XB9gRMd8CwyVWcZFbjTr845R+v1RuyDioIGh+5VG5WDZwExR4cF5uXZ6XMjAUwbBtLJXr1cyuTqAuNGkCnOpsp3UNxkKJtHQ2Q15mieUDEYz1As90D29qsGZpsGcvsX7Gv2bgiW5eToXJzkYWePw1nAVYfXu+NEag7lzcBQ2PR8fNFL94+5n7COgFJEKDu8Kgu9/f+3jhETfRvWg3GUy4IVyASZQ+swKDXdXI+gVGPgSwSgaBMCLqN4rG5X28anZfKljP/e0jeD11cXmUlI+gvwkrjT7w9xS2WgSm86glUYrp2vx7eFzHT1uJcCVS3oJkl6ZBtxPM2dyM+ZQksJDyHfX/7Zq8GaS0DHVpukZBQ+C7bQv9R4tl8JGVQcC3xV1E4AUsqb23o+/UdjIAYBhFIO7/WADQaAx5uBgqV6KjxIkjiciTjcEYEmvyOxYaMmt+uVPeloIiRNgYkBqvaj1Oj0J4kpVAsJW5E14zZzRjnhv1vvFiwZeOaPyPzQkZnzs="

    private init() {
        // NEVPNManager — subscribe to VPN status changes
        NotificationCenter.default.addObserver(
            forName: .NEVPNStatusDidChange,
            object: neManager.connection,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.handleNEVPNStatusChange()
            }
        }

        // Load existing NEVPNManager config
        loadNEVPNConfig()
        detectConflictingVPNs()
        startPathMonitor()
        startStatusPolling()
    }

    deinit {
        pathMonitor?.cancel()
        checkTimer?.invalidate()
        profileWaitTimer?.invalidate()
        sessionTimer?.invalidate()
    }

    // MARK: - NEVPNManager Configuration

    /// Load existing VPN configuration from system
    private func loadNEVPNConfig() {
        neManager.loadFromPreferences { [weak self] error in
            Task { @MainActor in
                guard let self else { return }
                if error != nil {
                    // NEVPNManager not available — fall back to mobileconfig
                    self.useNEVPN = false
                    self.checkProfileInstalled()
                    return
                }
                let configured = self.neManager.protocolConfiguration != nil
                self.isConfigured = configured
                self.isProfileInstalled = configured
                self.needsProfileInstall = !configured
                self.handleNEVPNStatusChange()
            }
        }
    }

    /// Create Montana VPN configuration in System Settings (NEVPNManager)
    private func configureNEVPN(completion: @escaping (Bool) -> Void) {
        // Install CA cert to keychain first
        installCACertIfNeeded()

        // Save password to keychain on main actor first
        let passwordRef = savePasswordToKeychain()

        neManager.loadFromPreferences { [weak self] _ in
            Task { @MainActor in
                guard let self else { completion(false); return }

                let proto = NEVPNProtocolIKEv2()
                proto.serverAddress = self.serverAddress
                proto.remoteIdentifier = self.serverAddress
                proto.localIdentifier = self.eapUser
                proto.authenticationMethod = .none // EAP
                proto.useExtendedAuthentication = true
                proto.username = self.eapUser
                proto.passwordReference = passwordRef
                proto.serverCertificateIssuerCommonName = "Montana Protocol CA"
                proto.serverCertificateCommonName = self.serverAddress
                proto.certificateType = .RSA
                proto.disconnectOnSleep = false
                proto.deadPeerDetectionRate = .medium

                // IKE SA — AES-256 + SHA2-256 + DH14
                proto.ikeSecurityAssociationParameters.encryptionAlgorithm = .algorithmAES256
                proto.ikeSecurityAssociationParameters.integrityAlgorithm = .SHA256
                proto.ikeSecurityAssociationParameters.diffieHellmanGroup = .group14

                // Child SA — AES-256 + SHA2-256 + DH14
                proto.childSecurityAssociationParameters.encryptionAlgorithm = .algorithmAES256
                proto.childSecurityAssociationParameters.integrityAlgorithm = .SHA256
                proto.childSecurityAssociationParameters.diffieHellmanGroup = .group14

                self.neManager.protocolConfiguration = proto
                self.neManager.localizedDescription = self.vpnServiceName
                self.neManager.isEnabled = true

                self.neManager.saveToPreferences { [weak self] saveError in
                    Task { @MainActor in
                        guard let self else { completion(false); return }
                        if saveError != nil {
                            // NEVPNManager failed (likely entitlement issue) — fallback to mobileconfig
                            self.useNEVPN = false
                            self.connectionError = nil
                            completion(false)
                            return
                        }
                        self.isConfigured = true
                        self.isProfileInstalled = true
                        self.needsProfileInstall = false
                        self.connectionError = nil
                        // Reload after save
                        self.neManager.loadFromPreferences { _ in
                            Task { @MainActor in
                                completion(true)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Keychain (EAP password for NEVPNManager)

    private func savePasswordToKeychain() -> Data? {
        let service = "network.montana.vpn.eap"
        let account = eapUser

        // Delete existing
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(deleteQuery as CFDictionary)

        // Add new with persistent ref
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: eapPassword.data(using: .utf8)!,
            kSecReturnPersistentRef as String: true,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        var result: AnyObject?
        let status = SecItemAdd(addQuery as CFDictionary, &result)

        if status == errSecSuccess, let ref = result as? Data {
            return ref
        }
        return nil
    }

    // MARK: - CA Certificate Installation

    private func installCACertIfNeeded() {
        guard let certData = Data(base64Encoded: caCertBase64),
              let cert = SecCertificateCreateWithData(nil, certData as CFData) else {
            return
        }

        // Add to login keychain with Montana Protocol label
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassCertificate,
            kSecValueRef as String: cert,
            kSecAttrLabel as String: "Montana Protocol CA"
        ]
        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
        guard addStatus == errSecSuccess || addStatus == errSecDuplicateItem else { return }

        // Restrict trust to IPsec/SSL only (not code signing, email, etc.)
        let trustPolicy = SecPolicyCreateSSL(true, nil)
        let trustSettings: [[String: Any]] = [
            [
                kSecTrustSettingsPolicy as String: trustPolicy,
                kSecTrustSettingsResult as String: SecTrustSettingsResult.trustRoot.rawValue
            ]
        ]
        let trustStatus = SecTrustSettingsSetTrustSettings(cert, .user, trustSettings as CFArray)
        if trustStatus != errSecSuccess {
            // Trust settings require user auth — will show system dialog with "Montana Protocol CA"
            // Fallback: try without policy restriction
            SecTrustSettingsSetTrustSettings(cert, .user, nil)
        }
    }

    // MARK: - NEVPNManager Status Handler

    private func handleNEVPNStatusChange() {
        guard useNEVPN else { return }
        let status = neManager.connection.status

        switch status {
        case .connected:
            if !isConnected {
                sessionStart = Date()
                startSessionTimer()
                measurePing()
            }
            isConnected = true
            isConnecting = false
            connectionError = nil
            needsProfileInstall = false
            checkVPNIP()

        case .connecting, .reasserting:
            isConnecting = true
            isConnected = false

        case .disconnecting:
            isConnecting = false

        case .disconnected:
            isConnected = false
            isConnecting = false
            vpnIP = ""
            vpnInterface = ""
            pingMs = 0
            bytesIn = 0
            bytesOut = 0
            sessionStart = nil
            stopSessionTimer()

        case .invalid:
            isConnected = false
            isConnecting = false
            isConfigured = false

        @unknown default:
            break
        }

        UserDefaults.standard.set(isConnected, forKey: "vpnRelayActive")
    }

    // MARK: - Connect / Disconnect

    func toggle() {
        if isConnected || isConnecting {
            disconnect()
        } else {
            connect()
        }
    }

    func connect() {
        guard !isConnected, !isConnecting else { return }
        isConnecting = true
        connectionError = nil
        userCancelledConnect = false
        needsProfileInstall = false

        // Disconnect other VPNs first
        DispatchQueue.global().async {
            Self.disconnectAllOtherVPNs()
        }

        if useNEVPN {
            connectViaNEVPN()
        } else {
            connectViaMobileconfig()
        }
    }

    func disconnect() {
        userCancelledConnect = true
        profileWaitTimer?.invalidate()
        profileWaitTimer = nil
        needsProfileInstall = false

        if useNEVPN {
            neManager.connection.stopVPNTunnel()
        } else {
            DispatchQueue.global().async {
                _ = Self.runProcess("/usr/sbin/scutil", args: ["--nc", "stop", "Montana VPN"])
            }
        }

        isConnecting = false
        connectionError = nil
    }

    // MARK: - NEVPNManager Connect Path

    private func connectViaNEVPN() {
        neManager.loadFromPreferences { [weak self] error in
            Task { @MainActor in
                guard let self else { return }

                if self.neManager.protocolConfiguration == nil {
                    // Not configured yet — set up, then connect
                    self.configureNEVPN { [weak self] success in
                        Task { @MainActor in
                            guard let self else { return }
                            if success {
                                self.startNEVPNTunnel()
                            } else {
                                // Fallback to mobileconfig
                                self.connectViaMobileconfig()
                            }
                        }
                    }
                } else {
                    self.startNEVPNTunnel()
                }
            }
        }
    }

    private func startNEVPNTunnel() {
        do {
            try neManager.connection.startVPNTunnel()
        } catch {
            isConnecting = false
            connectionError = "Montana VPN: Не удалось запустить туннель — проверьте подключение"
        }
    }

    // MARK: - Mobileconfig Fallback

    private func connectViaMobileconfig() {
        DispatchQueue.global().async { [weak self] in
            guard let self else { return }
            Thread.sleep(forTimeInterval: 0.5)

            let profileReady = Self.runProcess("/usr/sbin/scutil", args: ["--nc", "list"]).contains("Montana VPN")

            if !profileReady {
                Task { @MainActor in
                    guard !self.userCancelledConnect else {
                        self.isConnecting = false
                        return
                    }
                    self.installProfile()
                    self.waitForProfileAndConnect()
                }
                return
            }

            Self.startVPNviaScutil(user: self.eapUser, password: self.eapPassword)
            Thread.sleep(forTimeInterval: 3.0)
            Task { @MainActor in
                guard !self.userCancelledConnect else { return }
                self.isConnecting = false
                self.needsProfileInstall = false
                self.checkVPNStatus()
                self.detectConflictingVPNs()
            }
        }
    }

    func installProfile() {
        if isProfileInstalled {
            needsProfileInstall = false
            return
        }

        // If NEVPNManager is available, configure programmatically
        if useNEVPN {
            configureNEVPN { [weak self] success in
                Task { @MainActor in
                    if !success {
                        self?.installMobileconfig()
                    }
                }
            }
            return
        }

        installMobileconfig()
    }

    private func installMobileconfig() {
        let path = profilePath
        try? FileManager.default.createDirectory(at: profileDir, withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: path) {
            let profile = generateMobileconfig()
            do {
                try profile.write(toFile: path, atomically: true, encoding: .utf8)
                try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path)
            } catch {
                connectionError = "Ошибка записи профиля: \(error.localizedDescription)"
                return
            }
            NSWorkspace.shared.open(URL(fileURLWithPath: path))
        }

        needsProfileInstall = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) { [weak self] in
            self?.openProfileSettings()
        }
    }

    /// Open System Settings → Profiles
    func openProfileSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.Profiles-Settings.extension") {
            NSWorkspace.shared.open(url)
        }
    }

    func checkProfileInstalled() {
        if useNEVPN {
            // NEVPNManager — check config exists
            neManager.loadFromPreferences { [weak self] _ in
                Task { @MainActor in
                    guard let self else { return }
                    let configured = self.neManager.protocolConfiguration != nil
                    self.isProfileInstalled = configured
                    self.isConfigured = configured
                }
            }
            return
        }

        // Mobileconfig fallback — check via scutil
        DispatchQueue.global().async { [weak self] in
            let output = Self.runProcess("/usr/sbin/scutil", args: ["--nc", "list"])
            let hasMontana = output.contains("Montana VPN")
            Task { @MainActor in
                self?.isProfileInstalled = hasMontana
                self?.isConfigured = hasMontana
            }
        }
    }

    // MARK: - Path Monitor

    private func startPathMonitor() {
        pathMonitor?.cancel()
        pathMonitor = NWPathMonitor()
        pathMonitor?.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                guard let self else { return }
                if path.status != .satisfied && self.isConnected {
                    self.isConnected = false
                    self.vpnIP = ""
                    self.pingMs = 0
                    self.bytesIn = 0
                    self.bytesOut = 0
                    self.sessionStart = nil
                    self.sessionTimer?.invalidate()
                    self.sessionTimer = nil
                }
                // For mobileconfig mode, check status on network changes
                if !self.useNEVPN {
                    self.checkVPNStatus()
                    self.detectConflictingVPNs()
                }
            }
        }
        pathMonitor?.start(queue: DispatchQueue(label: "network.montana.vpn.monitor"))
    }

    // MARK: - Status Polling

    private func startStatusPolling() {
        checkTimer?.invalidate()
        checkTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                if self.useNEVPN {
                    // NEVPNManager — update traffic stats
                    if self.isConnected {
                        self.checkVPNIP()
                    }
                } else {
                    self.checkVPNStatus()
                }
            }
        }
    }

    // MARK: - VPN IP & Traffic (used by both modes)

    private func checkVPNIP() {
        DispatchQueue.global().async { [weak self] in
            guard let self else { return }
            let ifOutput = Self.runProcess("/sbin/ifconfig")

            var detectedIP = ""
            var detectedIface = ""

            if ifOutput.contains(self.ikev2Subnet) {
                detectedIP = self.extractIP(from: ifOutput, subnet: self.ikev2Subnet)
                detectedIface = self.extractInterface(from: ifOutput, subnet: self.ikev2Subnet)
            } else if ifOutput.contains(self.wgSubnet) {
                detectedIP = self.extractIP(from: ifOutput, subnet: self.wgSubnet)
                detectedIface = self.extractInterface(from: ifOutput, subnet: self.wgSubnet)
            }

            var inBytes: Int64 = 0
            var outBytes: Int64 = 0
            if !detectedIface.isEmpty {
                (inBytes, outBytes) = Self.readInterfaceStats(detectedIface)
            }

            Task { @MainActor [weak self] in
                guard let self else { return }
                self.vpnIP = detectedIP
                self.vpnInterface = detectedIface
                self.bytesIn = inBytes
                self.bytesOut = outBytes
            }
        }
    }

    /// Mobileconfig fallback: full status check via ifconfig
    func checkVPNStatus() {
        guard !useNEVPN else { return }
        DispatchQueue.global().async { [weak self] in
            guard let self else { return }
            let ifOutput = Self.runProcess("/sbin/ifconfig")

            let hasIKEv2 = ifOutput.contains(self.ikev2Subnet)
            let hasWG = ifOutput.contains(self.wgSubnet)
            let connected = hasIKEv2 || hasWG

            var detectedIP = ""
            var detectedIface = ""
            if hasIKEv2 {
                detectedIP = self.extractIP(from: ifOutput, subnet: self.ikev2Subnet)
                detectedIface = self.extractInterface(from: ifOutput, subnet: self.ikev2Subnet)
            } else if hasWG {
                detectedIP = self.extractIP(from: ifOutput, subnet: self.wgSubnet)
                detectedIface = self.extractInterface(from: ifOutput, subnet: self.wgSubnet)
            }

            var inBytes: Int64 = 0
            var outBytes: Int64 = 0
            if connected && !detectedIface.isEmpty {
                (inBytes, outBytes) = Self.readInterfaceStats(detectedIface)
            }

            Task { @MainActor in
                let wasConnected = self.isConnected
                self.isConnected = connected
                self.isConnecting = false
                if connected {
                    self.vpnIP = detectedIP
                    self.vpnInterface = detectedIface
                    self.bytesIn = inBytes
                    self.bytesOut = outBytes
                    self.connectionError = nil
                    if !wasConnected {
                        self.sessionStart = Date()
                        self.startSessionTimer()
                        self.measurePing()
                    }
                } else {
                    self.vpnIP = ""
                    self.vpnInterface = ""
                    self.pingMs = 0
                    self.bytesIn = 0
                    self.bytesOut = 0
                    self.sessionStart = nil
                    self.stopSessionTimer()
                }
                UserDefaults.standard.set(connected, forKey: "vpnRelayActive")
            }
        }
    }

    // MARK: - Conflict Detection

    func detectConflictingVPNs() {
        DispatchQueue.global().async { [weak self] in
            let output = Self.runProcess("/usr/sbin/scutil", args: ["--nc", "list"])

            var otherVPNs: [String] = []
            for line in output.components(separatedBy: "\n") {
                if line.contains("Montana VPN") { continue }
                if line.contains("Connected") || line.contains("Connecting") {
                    if let name = Self.extractVPNName(from: line) {
                        otherVPNs.append(name)
                    }
                }
            }

            Task { @MainActor in
                guard let self else { return }
                self.hasConflictingVPN = !otherVPNs.isEmpty
                self.conflictingVPNName = otherVPNs.joined(separator: ", ")
            }
        }
    }

    nonisolated private static func disconnectAllOtherVPNs() {
        let output = runProcess("/usr/sbin/scutil", args: ["--nc", "list"])
        for line in output.components(separatedBy: "\n") {
            if line.contains("Montana VPN") { continue }
            if line.contains("Connected") || line.contains("Connecting"),
               let name = extractVPNName(from: line) {
                _ = runProcess("/usr/sbin/scutil", args: ["--nc", "stop", name])
            }
        }
    }

    // MARK: - Mobileconfig Profile Wait

    private func waitForProfileAndConnect() {
        profileWaitTimer?.invalidate()
        var attempts = 0
        let maxAttempts = 20
        connectionError = "Установите профиль: Настройки → Основные → Профили → Montana VPN → Установить"

        profileWaitTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] timer in
            Task { @MainActor in
                guard let self else { timer.invalidate(); return }
                guard !self.userCancelledConnect else {
                    timer.invalidate()
                    self.profileWaitTimer = nil
                    self.isConnecting = false
                    self.needsProfileInstall = false
                    return
                }

                attempts += 1
                let output = Self.runProcess("/usr/sbin/scutil", args: ["--nc", "list"])
                let installed = output.contains("Montana VPN")

                if installed {
                    timer.invalidate()
                    self.profileWaitTimer = nil
                    self.needsProfileInstall = false
                    self.connectionError = nil
                    self.isProfileInstalled = true
                    self.isConfigured = true

                    DispatchQueue.global().async {
                        Self.startVPNviaScutil(user: self.eapUser, password: self.eapPassword)
                        Thread.sleep(forTimeInterval: 3.0)
                        Task { @MainActor in
                            self.isConnecting = false
                            self.checkVPNStatus()
                            self.detectConflictingVPNs()
                            try? FileManager.default.removeItem(atPath: self.profilePath)
                        }
                    }
                } else if attempts >= maxAttempts {
                    timer.invalidate()
                    self.profileWaitTimer = nil
                    self.isConnecting = false
                    self.needsProfileInstall = false
                    self.connectionError = "Профиль не установлен — откройте Настройки → Основные → Профили"
                    try? FileManager.default.removeItem(atPath: self.profilePath)
                }
            }
        }
    }

    nonisolated private static func startVPNviaScutil(user: String, password: String) {
        _ = runProcess("/usr/sbin/scutil", args: [
            "--nc", "start", "Montana VPN",
            "--user", user,
            "--password", password
        ])
    }

    // MARK: - Open System VPN Settings

    func openVPNSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.NetworkExtensionSettingsUI.NESettingsController") {
            NSWorkspace.shared.open(url)
        }
    }

    // MARK: - Session Timer

    private func startSessionTimer() {
        sessionTimer?.invalidate()
        sessionTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.objectWillChange.send()
            }
        }
    }

    private func stopSessionTimer() {
        sessionTimer?.invalidate()
        sessionTimer = nil
    }

    // MARK: - Ping

    private func measurePing() {
        DispatchQueue.global().async { [weak self] in
            let output = Self.runProcess("/sbin/ping", args: ["-c", "1", "-t", "3", "72.56.102.240"])
            if let range = output.range(of: "time=") {
                let after = output[range.upperBound...]
                if let spaceIdx = after.firstIndex(of: " ") {
                    let msStr = String(after[..<spaceIdx])
                    let ms = Int(Double(msStr) ?? 0)
                    Task { @MainActor in
                        self?.pingMs = ms
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    static func formatBytes(_ bytes: Int64) -> String {
        if bytes < 1024 { return "\(bytes) B" }
        let kb = Double(bytes) / 1024.0
        if kb < 1024 { return String(format: "%.1f KB", kb) }
        let mb = kb / 1024.0
        if mb < 1024 { return String(format: "%.1f MB", mb) }
        let gb = mb / 1024.0
        return String(format: "%.2f GB", gb)
    }

    nonisolated private func extractIP(from output: String, subnet: String) -> String {
        for line in output.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("inet ") && trimmed.contains(subnet) {
                let parts = trimmed.components(separatedBy: " ")
                if parts.count >= 2 { return parts[1] }
            }
        }
        return subnet + ".x"
    }

    nonisolated private func extractInterface(from output: String, subnet: String) -> String {
        var currentIface = ""
        for line in output.components(separatedBy: "\n") {
            if !line.hasPrefix("\t") && !line.hasPrefix(" ") && line.contains(": flags=") {
                if let colon = line.firstIndex(of: ":") {
                    currentIface = String(line[line.startIndex..<colon])
                }
            }
            if line.contains(subnet) && line.contains("inet ") {
                return currentIface
            }
        }
        return ""
    }

    nonisolated private static func readInterfaceStats(_ iface: String) -> (Int64, Int64) {
        let output = runProcess("/usr/sbin/netstat", args: ["-I", iface, "-b"])
        let lines = output.components(separatedBy: "\n")
        guard lines.count >= 2 else { return (0, 0) }
        let headerParts = lines[0].split(separator: " ").map(String.init)
        guard let ibIdx = headerParts.firstIndex(of: "Ibytes"),
              let obIdx = headerParts.firstIndex(of: "Obytes") else { return (0, 0) }

        for line in lines.dropFirst() {
            let parts = line.split(separator: " ").map(String.init)
            guard parts.count > max(ibIdx, obIdx) else { continue }
            let ib = Int64(parts[ibIdx]) ?? 0
            let ob = Int64(parts[obIdx]) ?? 0
            return (ib, ob)
        }
        return (0, 0)
    }

    nonisolated private static func extractVPNName(from line: String) -> String? {
        guard let start = line.firstIndex(of: "\"") else { return nil }
        let afterQuote = line.index(after: start)
        guard let end = line[afterQuote...].firstIndex(of: "\"") else { return nil }
        return String(line[afterQuote..<end])
    }

    nonisolated private static func runProcess(_ path: String, args: [String] = []) -> String {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: path)
        task.arguments = args
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return String(data: data, encoding: .utf8) ?? ""
        } catch {
            return ""
        }
    }

    // MARK: - .mobileconfig Generation (fallback)

    private func generateMobileconfig() -> String {
        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>PayloadDisplayName</key>
            <string>Montana VPN</string>
            <key>PayloadDescription</key>
            <string>Montana Protocol VPN — Amsterdam Node</string>
            <key>PayloadIdentifier</key>
            <string>\(profileIdentifier)</string>
            <key>PayloadOrganization</key>
            <string>Montana Protocol</string>
            <key>PayloadUUID</key>
            <string>\(stableProfileUUID)</string>
            <key>PayloadType</key>
            <string>Configuration</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadRemovalDisallowed</key>
            <false/>
            <key>PayloadContent</key>
            <array>
                <dict>
                    <key>PayloadType</key>
                    <string>com.apple.security.root</string>
                    <key>PayloadUUID</key>
                    <string>\(stableCaUUID)</string>
                    <key>PayloadIdentifier</key>
                    <string>network.montana.vpn.ca</string>
                    <key>PayloadDisplayName</key>
                    <string>Montana Protocol CA</string>
                    <key>PayloadDescription</key>
                    <string>Montana Protocol — Certificate Authority</string>
                    <key>PayloadOrganization</key>
                    <string>Montana Protocol</string>
                    <key>PayloadVersion</key>
                    <integer>1</integer>
                    <key>PayloadContent</key>
                    <data>\(caCertBase64)</data>
                </dict>
                <dict>
                    <key>PayloadType</key>
                    <string>com.apple.vpn.managed</string>
                    <key>PayloadUUID</key>
                    <string>\(stableVpnUUID)</string>
                    <key>PayloadIdentifier</key>
                    <string>network.montana.vpn.ikev2</string>
                    <key>PayloadDisplayName</key>
                    <string>Montana VPN</string>
                    <key>PayloadDescription</key>
                    <string>Montana Protocol — IKEv2 VPN</string>
                    <key>PayloadOrganization</key>
                    <string>Montana Protocol</string>
                    <key>PayloadVersion</key>
                    <integer>1</integer>
                    <key>UserDefinedName</key>
                    <string>Montana VPN</string>
                    <key>VPNType</key>
                    <string>IKEv2</string>
                    <key>IKEv2</key>
                    <dict>
                        <key>RemoteAddress</key>
                        <string>\(serverAddress)</string>
                        <key>RemoteIdentifier</key>
                        <string>\(serverAddress)</string>
                        <key>LocalIdentifier</key>
                        <string>\(eapUser)</string>
                        <key>AuthenticationMethod</key>
                        <string>None</string>
                        <key>ExtendedAuthEnabled</key>
                        <integer>1</integer>
                        <key>AuthName</key>
                        <string>\(eapUser)</string>
                        <key>AuthPassword</key>
                        <string>\(eapPassword)</string>
                        <key>DeadPeerDetectionRate</key>
                        <string>Medium</string>
                        <key>DisableMOBIKE</key>
                        <integer>0</integer>
                        <key>EnablePFS</key>
                        <integer>1</integer>
                        <key>NATKeepAliveInterval</key>
                        <integer>20</integer>
                        <key>ServerCertificateIssuerCommonName</key>
                        <string>Montana Protocol CA</string>
                        <key>ServerCertificateCommonName</key>
                        <string>\(serverAddress)</string>
                        <key>CertificateType</key>
                        <string>RSA</string>
                        <key>DisconnectOnIdle</key>
                        <integer>0</integer>
                        <key>IKESecurityAssociationParameters</key>
                        <dict>
                            <key>EncryptionAlgorithm</key>
                            <string>AES-256</string>
                            <key>IntegrityAlgorithm</key>
                            <string>SHA2-256</string>
                            <key>DiffieHellmanGroup</key>
                            <integer>14</integer>
                        </dict>
                        <key>ChildSecurityAssociationParameters</key>
                        <dict>
                            <key>EncryptionAlgorithm</key>
                            <string>AES-256</string>
                            <key>IntegrityAlgorithm</key>
                            <string>SHA2-256</string>
                            <key>DiffieHellmanGroup</key>
                            <integer>14</integer>
                        </dict>
                    </dict>
                    <key>OnDemandEnabled</key>
                    <integer>0</integer>
                    <key>OnDemandRules</key>
                    <array>
                        <dict>
                            <key>Action</key>
                            <string>Ignore</string>
                        </dict>
                    </array>
                    <key>IPv4</key>
                    <dict>
                        <key>OverridePrimary</key>
                        <integer>0</integer>
                    </dict>
                </dict>
            </array>
        </dict>
        </plist>
        """
    }
}
