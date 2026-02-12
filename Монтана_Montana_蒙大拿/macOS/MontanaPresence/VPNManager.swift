import Foundation
import Network
import AppKit
import Security

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

    // IKEv2 config
    private let serverAddress = "72.56.102.240"
    private let ikev2Subnet = "10.77.77"
    private let wgSubnet = "10.66.66"
    private let profileIdentifier = "network.montana.vpn.profile"
    private let eapUser = "montana"

    // Monitoring
    private var pathMonitor: NWPathMonitor?
    private var checkTimer: Timer?
    private var lastStatusCheck: Date = .distantPast
    private let statusCheckDebounce: TimeInterval = 1.0

    // Embedded CA certificate (PEM base64)
    private let caCertBase64 = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUU5akNDQXQ2Z0F3SUJBZ0lJQlF0eE8yM3VpaW93RFFZSktvWklodmNOQVFFTUJRQXdHVEVYTUJVR0ExVUUKQXhNT1RXOXVkR0Z1WSBXU1VFNGdRMEV3SGhjTk1qWXdNakV5TVRVMU5UVTBXaGNOTXpZd01qRXdNVFUxTlRVMApXakFaTVJjd0ZRWURWUVFERXc1TmIyNTBZVzVoSUZaUVRpQkRRVENDQWlJd0RRWUpLb1pJaHZjTkFRRUJCUUFECmdnSVBBRENDQWdvQ2dnSUJBSlNJbDlUVHJFQmRpakM3TlJGaXd2Z3AxZkM4WGRKNDFlclNFdkhRTDlPaHpXK0wKSmRFOXBERGlzd0lHbjliSHFPVWp3ZW9oSGxwZ2lkZlJ1VXlHSGZkRWZFSDV2eUVzTVE1TTlMbXErVldZanBPdgpSc3MrM01VTTJNVTJSMHNiMzB6VDJNSHc4TEVhbGNYV0h3b25PKzJYVEVZWEtOUjk0Y3NIeldQV0toaWVGS3BrCkJTSjFVa1c5RFdQSkw5ZTN2T1o1bzcrUmpHM1hYVURUVHlXd3V5dnRPWTA5dlpJVVZmc2dlYzdDZElqRUh6eEYKMXFRTFdIZTlZUHFxeGZ0RTc1YVhiY0Z1Y25rc2NkMTFxRmR4ZTlneTMxQTd3Rkp5Tks5RWExZnFNY3VoWXA1dgplc2ZJU21kWHliSlozUnMyUDlDZWtnTFVObE8zbUZ3S1EyUG9NaTlUWk8vWnF0Rmx0ZEUzNlZTcXVSb3lhdEtlCnp4dURiQitMQzFiYTNxRFdSTXBVcmtJWGN0b21xeEc5Vno2V0NldFhxRlBKaklweU9BeUFKNHFqRW13N3l6Z1YKYXdYM3RUL2JYRnRCQTVqN1NxR3BycXFmdlFNQWY1YXdHckNzMmNtL2h3NzJUakxYaFI2eWdxbW50MkQ2Ky9TdwpQcE1kVEZ3VC9oaDkrVFhNeTRRb2JERU9nS1o0ekJjWEJTY2g4c0FaWER2bmVoY2t4WnRHRnUyVmk2bUpkYTQ5CjQ1UERDa2R4MFNUdUEzWlVPMVBqVVlGRXFtWm5qVTVvVFNWMTJ2ZVV2QnZpalRHQXM5YzBCZy9mbmRIbjhlMm0KRjRGNjFrQ3U1NHlERmlGT2VTMktWQ25iTlN1ZDNPajhiWnphTkRlbDJqZ1dUMzR4c3o1ODU4SmsrVXNWQWdNQgpBQUdqUWpCQU1BOEdBMVVkRXdFQi93UUZNQU1CQWY4d0RnWURWUjBQQVFIL0JBUURBZ0VHTUIwR0ExVWREZ1FXCkJCVDV4MVE5TnBDcGE1S2RmTk9zOXBKb0IyakRWREFOQmdrcWhraUc5dzBCQVF3RkFBT0NBZ0VBUVNpUkcrVWYKcHh4NWM1ci9xVUNleEE4bnIzVGd0di9tWFNFQlFXbzM5N3NZRStPODE3akFyY2VSWERIQWRpcHJMMkp1djlOawpIT2VqUnQxUlk4RlNENzNOVFY2L2dvRVQrQ0RxMnFWQTZkemlOaGJVc3dVRFdISnNpSmk2bzlycUdTV2VSNXZqCkN3MnRraEM2UTdEb1d3ZGVrbHI3K1IwclZSVXNSOXBxUmU4Q1JwZk93N1ZBL1F2aHY3dGVzYVJJUmNHWUNyTmkKcnR2by83TUV1LzRKMFJuOHZlb1p6bHFzanNkT2E1VG9ucWx2OG4wTHZHVzMxb2JoakltQXVsQ1FlMFpyZm1TUgpRUDdqMG10OWQ1bnFBZHdubVdKMGJueFNqTWtXcmphelFzVDBlcXdjZjhTZzhUN0ZaWklkdTJrUWhRanFCSjlGCnQzMWZKRVJ4bzNKdnc5VjlyQmZWc0dOZ1NuUlljVWxBcmtGblpwNW9YbkphZ0ZUOHIyK0tYYkYzS0JBL241NkgKVklCSXJXOTgreEJ0T2NXNFByaUJnSVNWZ2l4bHpVYmVnemlZSkFYRjB5enFLSyt5SUtWQ3c2UzZ6R0N2UHRmVgpVRlhPRCtnbjJrMHlhdjI5c0JPakZjL1h3NmV6NGMyVWxzSTA0djIzZXVBbWRpUlBTWkxOcDVsZnAxMm12UGhFCmd2Z1RpUUdKdHZyZ2FQUTRkdTh0bmFDUEVORWIwUmJyR2hYb1dueXZZNW03cmpwLy95di9kSzZ2L3JlZWRZRncKR1ZuVWxaWnFGYW9MSjFhakFBUlBOUFE2dkQvSzJjbVhHcXl0N2FqWkdxVXFCSGVvOVcxY09lL1lhSUlvMVEvRQpkZXVmUmpwcDJRaFlkNjJlSjgyU2JyZUNNRnh3TDF2cjhyUT0KLS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQo="

    private init() {
        ensureKeychainPassword()
        checkProfileInstalled()
        detectConflictingVPNs()
        startPathMonitor()
        startStatusPolling()
    }

    deinit {
        pathMonitor?.cancel()
        checkTimer?.invalidate()
    }

    // MARK: - Keychain (EAP password stored securely)

    private static let keychainService = "network.montana.vpn"
    private static let keychainAccount = "eap-password"

    private func ensureKeychainPassword() {
        if readPasswordFromKeychain() == nil {
            savePasswordToKeychain("M0ntana!VPN#2026")
        }
    }

    nonisolated private func readPasswordFromKeychain() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: VPNManager.keychainService,
            kSecAttrAccount as String: VPNManager.keychainAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    nonisolated private func savePasswordToKeychain(_ password: String) {
        let data = password.data(using: .utf8)!
        // Delete existing
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: VPNManager.keychainService,
            kSecAttrAccount as String: VPNManager.keychainAccount
        ]
        SecItemDelete(deleteQuery as CFDictionary)
        // Add new
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: VPNManager.keychainService,
            kSecAttrAccount as String: VPNManager.keychainAccount,
            kSecValueData as String: data
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
    }

    private var eapPassword: String {
        readPasswordFromKeychain() ?? ""
    }

    // MARK: - Path Monitor (event-driven connectivity with debounce)

    private func startPathMonitor() {
        pathMonitor?.cancel()
        pathMonitor = NWPathMonitor()
        pathMonitor?.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                guard let self else { return }
                if path.status != .satisfied {
                    if self.isConnected {
                        self.isConnected = false
                        self.vpnIP = ""
                        self.pingMs = 0
                    }
                }
                self.debouncedCheckVPNStatus()
            }
        }
        pathMonitor?.start(queue: DispatchQueue(label: "network.montana.vpn.monitor"))
    }

    // MARK: - Debounced Status Check

    private func debouncedCheckVPNStatus() {
        let now = Date()
        guard now.timeIntervalSince(lastStatusCheck) >= statusCheckDebounce else { return }
        lastStatusCheck = now
        checkVPNStatus()
        detectConflictingVPNs()
    }

    // MARK: - Status Polling (5s interval)

    private func startStatusPolling() {
        checkTimer?.invalidate()
        checkTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkVPNStatus()
            }
        }
    }

    func checkVPNStatus() {
        DispatchQueue.global().async { [weak self] in
            guard let self else { return }
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/sbin/ifconfig")
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""

                let hasIKEv2 = output.contains(self.ikev2Subnet)
                let hasWG = output.contains(self.wgSubnet)
                let connected = hasIKEv2 || hasWG

                var detectedIP = ""
                if hasIKEv2 {
                    detectedIP = self.extractIP(from: output, subnet: self.ikev2Subnet)
                } else if hasWG {
                    detectedIP = self.extractIP(from: output, subnet: self.wgSubnet)
                }

                Task { @MainActor in
                    let wasConnected = self.isConnected
                    self.isConnected = connected
                    self.isConnecting = false
                    if connected {
                        self.vpnIP = detectedIP
                        self.connectionError = nil
                        if !wasConnected || self.pingMs == 0 {
                            self.measurePing()
                        }
                    } else {
                        self.vpnIP = ""
                        self.pingMs = 0
                    }
                    UserDefaults.standard.set(connected, forKey: "vpnRelayActive")
                }
            } catch {
                Task { @MainActor in
                    self.isConnected = false
                    self.vpnIP = ""
                }
            }
        }
    }

    nonisolated private func extractIP(from output: String, subnet: String) -> String {
        let lines = output.components(separatedBy: "\n")
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("inet ") && trimmed.contains(subnet) {
                let parts = trimmed.components(separatedBy: " ")
                if parts.count >= 2 {
                    return parts[1]
                }
            }
        }
        return subnet + ".x"
    }

    // MARK: - Profile Installation

    func installProfile() {
        let profile = generateMobileconfig()
        let path = NSTemporaryDirectory() + "MontanaVPN.mobileconfig"
        do {
            try profile.write(toFile: path, atomically: true, encoding: .utf8)
            NSWorkspace.shared.open(URL(fileURLWithPath: path))
            // Cleanup temp file after macOS reads it + check installation
            DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
                try? FileManager.default.removeItem(atPath: path)
                self?.checkProfileInstalled()
                self?.checkVPNStatus()
            }
        } catch {}
    }

    func checkProfileInstalled() {
        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/sbin/scutil")
            task.arguments = ["--nc", "list"]
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
                let hasMontana = output.contains("Montana VPN")

                Task { @MainActor in
                    self?.isProfileInstalled = hasMontana
                    self?.isConfigured = hasMontana
                }
            } catch {
                Task { @MainActor in
                    self?.isProfileInstalled = false
                    self?.isConfigured = false
                }
            }
        }
    }

    // MARK: - Conflict Detection

    func detectConflictingVPNs() {
        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/sbin/scutil")
            task.arguments = ["--nc", "list"]
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""

                var otherVPNs: [String] = []
                let lines = output.components(separatedBy: "\n")
                for line in lines {
                    if line.contains("Montana VPN") { continue }
                    if line.contains("Connected") {
                        if let start = line.firstIndex(of: "\""),
                           let end = line[line.index(after: start)...].firstIndex(of: "\"") {
                            let name = String(line[line.index(after: start)..<end])
                            otherVPNs.append(name)
                        }
                    }
                }

                Task { @MainActor in
                    guard let self else { return }
                    self.hasConflictingVPN = !otherVPNs.isEmpty
                    self.conflictingVPNName = otherVPNs.joined(separator: ", ")
                }
            } catch {}
        }
    }

    // MARK: - Toggle (connect/disconnect via scutil)

    func toggle() {
        if isConnected {
            disconnect()
        } else {
            connect()
        }
    }

    func connect() {
        guard isProfileInstalled, !isConnected, !isConnecting else {
            if !isProfileInstalled {
                installProfile()
            }
            return
        }
        isConnecting = true
        connectionError = nil

        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/sbin/scutil")
            task.arguments = ["--nc", "start", "Montana VPN"]
            let errPipe = Pipe()
            task.standardOutput = Pipe()
            task.standardError = errPipe

            do {
                try task.run()
                task.waitUntilExit()
                if task.terminationStatus != 0 {
                    let errData = errPipe.fileHandleForReading.readDataToEndOfFile()
                    let errStr = String(data: errData, encoding: .utf8) ?? ""
                    Task { @MainActor in
                        self?.connectionError = errStr.isEmpty ? nil : errStr
                    }
                }
            } catch {
                Task { @MainActor in
                    self?.connectionError = error.localizedDescription
                }
            }

            Thread.sleep(forTimeInterval: 3.0)
            Task { @MainActor in
                self?.isConnecting = false
                self?.checkVPNStatus()
                // If still not connected after 3s, show error
                if self?.isConnected == false && self?.connectionError == nil {
                    self?.connectionError = "\u{041d}\u{0435} \u{0443}\u{0434}\u{0430}\u{043b}\u{043e}\u{0441}\u{044c} \u{043f}\u{043e}\u{0434}\u{043a}\u{043b}\u{044e}\u{0447}\u{0438}\u{0442}\u{044c}\u{0441}\u{044f}"
                }
            }
        }
    }

    func disconnect() {
        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/sbin/scutil")
            task.arguments = ["--nc", "stop", "Montana VPN"]
            task.standardOutput = Pipe()
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
            } catch {}

            Task { @MainActor in
                self?.isConnected = false
                self?.vpnIP = ""
                self?.pingMs = 0
                self?.connectionError = nil
                UserDefaults.standard.set(false, forKey: "vpnRelayActive")
            }
        }
    }

    // MARK: - Open System VPN Settings

    func openVPNSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.NetworkExtensionSettingsUI.NESettingsController") {
            NSWorkspace.shared.open(url)
        }
    }

    // MARK: - Ping

    private func measurePing() {
        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/sbin/ping")
            task.arguments = ["-c", "1", "-t", "3", "72.56.102.240"]
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
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
            } catch {}
        }
    }

    // MARK: - .mobileconfig Generation

    private func generateMobileconfig() -> String {
        let profileUUID = UUID().uuidString.uppercased()
        let caUUID = UUID().uuidString.uppercased()
        let vpnUUID = UUID().uuidString.uppercased()
        let password = eapPassword

        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>PayloadDisplayName</key>
            <string>Montana VPN</string>
            <key>PayloadIdentifier</key>
            <string>\(profileIdentifier)</string>
            <key>PayloadUUID</key>
            <string>\(profileUUID)</string>
            <key>PayloadType</key>
            <string>Configuration</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadContent</key>
            <array>
                <dict>
                    <key>PayloadType</key>
                    <string>com.apple.security.root</string>
                    <key>PayloadUUID</key>
                    <string>\(caUUID)</string>
                    <key>PayloadIdentifier</key>
                    <string>network.montana.vpn.ca</string>
                    <key>PayloadDisplayName</key>
                    <string>Montana VPN CA</string>
                    <key>PayloadVersion</key>
                    <integer>1</integer>
                    <key>PayloadContent</key>
                    <data>\(caCertBase64)</data>
                </dict>
                <dict>
                    <key>PayloadType</key>
                    <string>com.apple.vpn.managed</string>
                    <key>PayloadUUID</key>
                    <string>\(vpnUUID)</string>
                    <key>PayloadIdentifier</key>
                    <string>network.montana.vpn.ikev2</string>
                    <key>PayloadDisplayName</key>
                    <string>Montana VPN</string>
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
                        <string>\(password)</string>
                        <key>ServerCertificateIssuerCommonName</key>
                        <string>Montana VPN CA</string>
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
                </dict>
            </array>
        </dict>
        </plist>
        """
    }
}
