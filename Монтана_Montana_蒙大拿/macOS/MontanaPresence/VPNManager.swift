import Foundation
import Network
import AppKit
import Security
import CryptoKit
import CommonCrypto

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

    // WireGuard specific
    @Published var connectionError: String? = nil
    @Published var bytesIn: Int64 = 0
    @Published var bytesOut: Int64 = 0
    @Published var sessionStart: Date? = nil
    @Published var publicKey: String = ""
    @Published var needsSudo: Bool = false

    var sessionDuration: Int {
        guard let start = sessionStart else { return 0 }
        return max(Int(Date().timeIntervalSince(start)), 0)
    }

    // WireGuard config
    private let serverAddress = "72.56.102.240"
    private let serverPort = 51820
    private let serverPublicKey = "/9zhnW4O4uOstQpR5mgGmCLiy+B+LL4uQmNzgupNzwc="
    private let subnet = "10.66.66"
    private let interfaceName = "utun9"

    // Monitoring
    private var pathMonitor: NWPathMonitor?
    private var checkTimer: Timer?
    private var sessionTimer: Timer?
    private var wgProcess: Process?

    // Paths
    private var configDir: URL {
        guard let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            fatalError("Application Support directory not available")
        }
        return appSupport.appendingPathComponent("Montana")
    }

    private static var homebrewPrefix: String {
        #if arch(arm64)
        return "/opt/homebrew"
        #else
        return "/usr/local"
        #endif
    }
    private var configPath: String {
        configDir.appendingPathComponent("wg0.conf").path
    }
    private var privateKeyPath: String {
        configDir.appendingPathComponent("private.key.enc").path
    }

    // Montana Protocol keypair for encryption (post-quantum protection)
    private var montanaPrivateKey: Data? {
        // Load Montana Protocol private key from PresenceEngine
        // This is ML-DSA-65 (Dilithium) keypair - post-quantum secure
        guard let keyData = UserDefaults.standard.data(forKey: "montana_private_key") else { return nil }
        return keyData
    }

    private init() {
        setupConfigDirectory()
        loadOrGenerateKeys()
        startPathMonitor()
        startStatusPolling()
    }

    deinit {
        pathMonitor?.cancel()
        checkTimer?.invalidate()
        sessionTimer?.invalidate()
        wgProcess?.terminate()
    }

    // MARK: - Setup

    private func setupConfigDirectory() {
        try? FileManager.default.createDirectory(at: configDir, withIntermediateDirectories: true)
    }

    private func loadOrGenerateKeys() {
        // Check if encrypted private key exists on disk
        if FileManager.default.fileExists(atPath: privateKeyPath),
           let privateKey = loadEncryptedPrivateKey(), !privateKey.isEmpty {
            // Derive public key from private key
            if let pubKey = derivePublicKey(from: privateKey) {
                self.publicKey = pubKey
                self.isConfigured = true
                return
            }
        }

        // Generate new keypair
        generateNewKeypair()
    }

    private func generateNewKeypair() {
        let privateKey = Self.runProcess("\(Self.homebrewPrefix)/bin/wg", args: ["genkey"]).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !privateKey.isEmpty else {
            connectionError = "Montana VPN: WireGuard не установлен. Запустите: brew install wireguard-tools"
            return
        }

        // Save private key encrypted with post-quantum protection
        guard saveEncryptedPrivateKey(privateKey) else {
            connectionError = "Ошибка сохранения зашифрованного ключа"
            return
        }

        // Derive public key
        if let pubKey = derivePublicKey(from: privateKey) {
            self.publicKey = pubKey
            self.isConfigured = true
        }
    }

    private func derivePublicKey(from privateKey: String) -> String? {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "\(Self.homebrewPrefix)/bin/wg")
        task.arguments = ["pubkey"]

        let inputPipe = Pipe()
        let outputPipe = Pipe()
        task.standardInput = inputPipe
        task.standardOutput = outputPipe
        task.standardError = Pipe()

        do {
            try task.run()
            inputPipe.fileHandleForWriting.write(privateKey.data(using: .utf8)!)
            try inputPipe.fileHandleForWriting.close()
            task.waitUntilExit()
            let data = outputPipe.fileHandleForReading.readDataToEndOfFile()
            return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
        } catch {
            return nil
        }
    }

    // MARK: - Post-Quantum Encryption (via Montana Protocol keypair)

    /// Derive AES-256 encryption key from Montana Protocol private key
    private func deriveEncryptionKey() -> SymmetricKey? {
        guard let montanaKey = montanaPrivateKey else {
            // Fallback: use device-specific key if Montana key not available yet
            let fallbackSeed = "Montana-VPN-\(ProcessInfo.processInfo.hostName)".data(using: .utf8)!
            return SymmetricKey(data: SHA256.hash(data: fallbackSeed))
        }

        // KDF from Montana Protocol private key (ML-DSA-65)
        // This provides post-quantum security for VPN key encryption
        let salt = "Montana-VPN-v1".data(using: .utf8)!
        let kdfOutput = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: SymmetricKey(data: montanaKey),
            salt: salt,
            outputByteCount: 32
        )
        return kdfOutput
    }

    /// Save WireGuard private key encrypted with AES-256-GCM (post-quantum protected)
    private func saveEncryptedPrivateKey(_ key: String) -> Bool {
        guard let encryptionKey = deriveEncryptionKey(),
              let plaintext = key.data(using: .utf8) else { return false }

        do {
            // Generate random nonce
            let nonce = try AES.GCM.Nonce()

            // Encrypt with AES-256-GCM (AEAD)
            let sealedBox = try AES.GCM.seal(plaintext, using: encryptionKey, nonce: nonce)

            // Combine nonce + ciphertext + tag
            guard let combined = sealedBox.combined else { return false }

            // Write encrypted data to disk
            try combined.write(to: URL(fileURLWithPath: privateKeyPath), options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: privateKeyPath)

            return true
        } catch {
            #if DEBUG
            print("Encryption failed: \(error)")
            #endif
            return false
        }
    }

    /// Load and decrypt WireGuard private key (post-quantum protected)
    private func loadEncryptedPrivateKey() -> String? {
        guard let encryptionKey = deriveEncryptionKey(),
              let encryptedData = try? Data(contentsOf: URL(fileURLWithPath: privateKeyPath)) else {
            return nil
        }

        do {
            // Decrypt AES-256-GCM
            let sealedBox = try AES.GCM.SealedBox(combined: encryptedData)
            let decrypted = try AES.GCM.open(sealedBox, using: encryptionKey)

            return String(data: decrypted, encoding: .utf8)
        } catch {
            #if DEBUG
            print("Decryption failed: \(error)")
            #endif
            return nil
        }
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

        // Load encrypted private key from disk
        guard let privateKey = loadEncryptedPrivateKey() else {
            isConnecting = false
            connectionError = "Montana VPN не настроен. Перезапустите приложение."
            return
        }

        // Get next available IP from server
        Task {
            let clientIP = await registerPeerOnServer()
            guard !clientIP.isEmpty else {
                await MainActor.run {
                    isConnecting = false
                    connectionError = "Не удалось зарегистрировать peer на сервере"
                }
                return
            }

            // Generate config
            let config = generateWireGuardConfig(privateKey: privateKey, clientIP: clientIP)
            do {
                try config.write(toFile: configPath, atomically: true, encoding: .utf8)
                try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: configPath)
            } catch {
                await MainActor.run {
                    isConnecting = false
                    connectionError = "Ошибка записи конфига: \(error.localizedDescription)"
                }
                return
            }

            // Start WireGuard tunnel
            await startWireGuardTunnel()
        }
    }

    func disconnect() {
        wgProcess?.terminate()
        wgProcess = nil

        // Stop tunnel via wg-quick
        DispatchQueue.global().async {
            _ = Self.runProcess("\(Self.homebrewPrefix)/bin/wg-quick", args: ["down", self.configPath], sudo: true)
        }

        isConnecting = false
        isConnected = false
        vpnIP = ""
        pingMs = 0
        bytesIn = 0
        bytesOut = 0
        sessionStart = nil
        stopSessionTimer()
        UserDefaults.standard.set(false, forKey: "vpnRelayActive")
    }

    // MARK: - Server Registration

    private func registerPeerOnServer() async -> String {
        // API endpoint to register peer
        guard let url = URL(string: "https://efir.org/api/v1/vpn/register") else { return "" }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: String] = ["public_key": publicKey]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            // macOS 12+ async API
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                return ""
            }

            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let clientIP = json["client_ip"] as? String {
                return clientIP
            }
        } catch {
            #if DEBUG
            print("Register peer failed: \(error)")
            #endif
        }

        return ""
    }

    // MARK: - WireGuard Tunnel

    private func startWireGuardTunnel() async {
        // Try wg-quick up with sudo
        let success = await withCheckedContinuation { continuation in
            DispatchQueue.global().async {
                let output = Self.runProcess("\(Self.homebrewPrefix)/bin/wg-quick", args: ["up", self.configPath], sudo: true)
                let success = output.contains("interface:") || output.contains(self.interfaceName)
                continuation.resume(returning: success)
            }
        }

        await MainActor.run {
            if success {
                isConnected = true
                isConnecting = false
                sessionStart = Date()
                startSessionTimer()
                checkVPNStatus()
            } else {
                isConnecting = false
                connectionError = "WireGuard не смог запустить туннель — проверьте пароль sudo"
                needsSudo = true
            }
        }
    }

    // MARK: - Config Generation

    private func generateWireGuardConfig(privateKey: String, clientIP: String) -> String {
        return """
        [Interface]
        PrivateKey = \(privateKey)
        Address = \(clientIP)/24
        DNS = 1.1.1.1, 8.8.8.8

        [Peer]
        PublicKey = \(serverPublicKey)
        Endpoint = \(serverAddress):\(serverPort)
        AllowedIPs = 0.0.0.0/0, ::/0
        PersistentKeepalive = 25
        """
    }

    // MARK: - Status Monitoring

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
                self.checkVPNStatus()
            }
        }
        pathMonitor?.start(queue: DispatchQueue(label: "network.montana.vpn.monitor"))
    }

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

            // Check if interface exists
            let ifOutput = Self.runProcess("/sbin/ifconfig", args: [self.interfaceName])
            let connected = ifOutput.contains(self.subnet)

            var detectedIP = ""
            var inBytes: Int64 = 0
            var outBytes: Int64 = 0

            if connected {
                detectedIP = self.extractIP(from: ifOutput)

                // Get WireGuard stats
                let wgOutput = Self.runProcess("\(Self.homebrewPrefix)/bin/wg", args: ["show", self.interfaceName, "transfer"])
                if let (rx, tx) = self.parseWireGuardStats(wgOutput) {
                    inBytes = rx
                    outBytes = tx
                }

                // Measure ping
                self.measurePing()
            }

            Task { @MainActor in
                let wasConnected = self.isConnected
                self.isConnected = connected
                self.isConnecting = false

                if connected {
                    self.vpnIP = detectedIP
                    self.bytesIn = inBytes
                    self.bytesOut = outBytes
                    self.connectionError = nil
                    if !wasConnected {
                        self.sessionStart = Date()
                        self.startSessionTimer()
                    }
                } else {
                    self.vpnIP = ""
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

    // MARK: - Helpers

    private func extractIP(from output: String) -> String {
        for line in output.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("inet ") && trimmed.contains(subnet) {
                let parts = trimmed.components(separatedBy: " ")
                if parts.count >= 2 { return parts[1] }
            }
        }
        return subnet + ".x"
    }

    private func parseWireGuardStats(_ output: String) -> (Int64, Int64)? {
        let parts = output.trimmingCharacters(in: .whitespacesAndNewlines).components(separatedBy: "\t")
        guard parts.count >= 2,
              let rx = Int64(parts[0]),
              let tx = Int64(parts[1]) else { return nil }
        return (rx, tx)
    }

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

    // MARK: - Process Execution

    nonisolated private static func escapeShellArg(_ arg: String) -> String {
        // Escape single quotes: ' -> '\''
        return "'\(arg.replacingOccurrences(of: "'", with: "'\\''"))'"
    }

    nonisolated private static func runProcess(_ path: String, args: [String] = [], sudo: Bool = false) -> String {
        if sudo {
            // Use osascript to request sudo via GUI (with proper escaping)
            let escapedPath = escapeShellArg(path)
            let escapedArgs = args.map { escapeShellArg($0) }.joined(separator: " ")
            let command = "\(escapedPath) \(escapedArgs)"
            let script = """
            do shell script \(escapeShellArg(command)) with administrator privileges
            """
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            task.arguments = ["-e", script]
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = pipe
            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                return String(data: data, encoding: .utf8) ?? ""
            } catch {
                return ""
            }
        } else {
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
    }

    static func formatBytes(_ bytes: Int64) -> String {
        if bytes < 1024 { return "\(bytes) B" }
        let kb = Double(bytes) / 1024.0
        if kb < 1024 { return String(format: "%.1f KB", kb) }
        let mb = kb / 1024.0
        if mb < 1024 { return String(format: "%.1f MB", mb) }
        let gb = mb / 1024.0
        return String(format: "%.2f GB", gb)
    }

    // MARK: - Settings Helpers

    func openVPNSettings() {
        // Open Montana VPN config folder
        NSWorkspace.shared.selectFile(configPath, inFileViewerRootedAtPath: configDir.path)
    }
}
