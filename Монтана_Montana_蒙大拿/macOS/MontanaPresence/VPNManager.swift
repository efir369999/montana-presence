import Foundation

@MainActor
class VPNManager: ObservableObject {
    static let shared = VPNManager()

    @Published var isConnected = false
    @Published var isConnecting = false
    @Published var isConfigured = false
    @Published var vpnIP: String = ""
    @Published var pingMs: Int = 0
    @Published var serverLocation: String = "Amsterdam"

    private var checkTimer: Timer?
    private let wgQuickPath = "/opt/homebrew/bin/wg-quick"
    private let confName = "montana"

    private init() {
        checkConfigured()
    }

    private func checkConfigured() {
        let fm = FileManager.default
        let hasWg = fm.fileExists(atPath: "/opt/homebrew/bin/wg-quick") || fm.fileExists(atPath: "/usr/local/bin/wg-quick")
        let hasConf = fm.fileExists(atPath: "/etc/wireguard/montana.conf") || fm.fileExists(atPath: "/opt/homebrew/etc/wireguard/montana.conf")
        isConfigured = hasWg && hasConf
    }

    func startMonitoring() {
        checkTimer?.invalidate()
        checkTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            DispatchQueue.global().async {
                self?.checkStatusAsync()
            }
        }
    }

    nonisolated private func checkStatusAsync() {
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
            let connected = output.contains("10.66.66.3")

            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                let wasConnected = self.isConnected
                self.isConnected = connected
                if connected {
                    self.vpnIP = "10.66.66.3"
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
            DispatchQueue.main.async { [weak self] in
                self?.isConnected = false
            }
        }
    }

    func checkStatus() {
        DispatchQueue.global().async { [weak self] in
            self?.checkStatusAsync()
        }
    }

    func connect() {
        guard !isConnected, !isConnecting else { return }
        isConnecting = true
        startMonitoring()

        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/sudo")
            task.arguments = ["-n", "/opt/homebrew/bin/wg-quick", "up", "montana"]
            task.standardOutput = Pipe()
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
            } catch {}

            DispatchQueue.main.async {
                self?.isConnecting = false
                self?.checkStatus()
            }
        }
    }

    func disconnect() {
        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/sudo")
            task.arguments = ["-n", "/opt/homebrew/bin/wg-quick", "down", "montana"]
            task.standardOutput = Pipe()
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
            } catch {}

            DispatchQueue.main.async {
                self?.isConnected = false
                self?.vpnIP = ""
                self?.pingMs = 0
                UserDefaults.standard.set(false, forKey: "vpnRelayActive")
            }
        }
    }

    func toggle() {
        if isConnected {
            disconnect()
        } else {
            connect()
        }
    }

    private func measurePing() {
        DispatchQueue.global().async { [weak self] in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/sbin/ping")
            task.arguments = ["-c", "1", "-t", "3", "10.66.66.1"]
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = Pipe()

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
                // Parse "time=55.123 ms"
                if let range = output.range(of: "time=") {
                    let after = output[range.upperBound...]
                    if let spaceIdx = after.firstIndex(of: " ") {
                        let msStr = String(after[..<spaceIdx])
                        let ms = Int(Double(msStr) ?? 0)
                        DispatchQueue.main.async {
                            self?.pingMs = ms
                        }
                    }
                }
            } catch {}
        }
    }
}
