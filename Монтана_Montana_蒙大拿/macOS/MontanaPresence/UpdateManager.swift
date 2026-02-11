import Foundation
import AppKit

@MainActor
class UpdateManager: ObservableObject {
    static let shared = UpdateManager()

    @Published var updateAvailable = false
    @Published var latestVersion: String = ""
    @Published var updateNotes: String = ""
    @Published var isDownloading = false
    @Published var downloadProgress: Double = 0

    private var checkTimer: Timer?
    private var downloadURL: String = ""

    private let endpoints: [String] = [
        "https://efir.org",
        "http://72.56.102.240:5000",
        "http://176.124.208.93:8889",
        "http://91.200.148.93:5000"
    ]

    var currentVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.0.0"
    }

    var currentBuild: Int {
        Int(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "0") ?? 0
    }

    private init() {}

    // MARK: - Check Schedule

    func startChecking() {
        Task { await checkForUpdate() }

        checkTimer = Timer.scheduledTimer(withTimeInterval: 4 * 3600, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.checkForUpdate()
            }
        }
    }

    func stopChecking() {
        checkTimer?.invalidate()
        checkTimer = nil
    }

    // MARK: - Version Check

    func checkForUpdate() async {
        for endpoint in endpoints {
            do {
                guard let url = URL(string: "\(endpoint)/api/version/macos") else { continue }

                var request = URLRequest(url: url)
                request.timeoutInterval = 10

                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let version = json["version"] as? String else {
                    continue
                }

                let serverBuild = json["build"] as? Int ?? 0
                let notes = json["notes"] as? String ?? ""
                let dlURL = json["url"] as? String ?? ""

                if isNewer(server: version, serverBuild: serverBuild) {
                    latestVersion = version
                    updateNotes = notes
                    downloadURL = dlURL
                    updateAvailable = true
                }
                return
            } catch {
                continue
            }
        }
    }

    // MARK: - Version Comparison

    private func isNewer(server: String, serverBuild: Int) -> Bool {
        let current = currentVersion.split(separator: ".").compactMap { Int($0) }
        let remote = server.split(separator: ".").compactMap { Int($0) }

        let c = current + Array(repeating: 0, count: max(0, 3 - current.count))
        let r = remote + Array(repeating: 0, count: max(0, 3 - remote.count))

        for i in 0..<3 {
            if r[i] > c[i] { return true }
            if r[i] < c[i] { return false }
        }

        return serverBuild > currentBuild
    }

    // MARK: - Download & Install

    func downloadAndInstall() async {
        guard !downloadURL.isEmpty, let url = URL(string: downloadURL) else { return }

        isDownloading = true
        downloadProgress = 0

        let tmpDir = "/tmp/MontanaUpdate"

        do {
            // Clean temp
            try? FileManager.default.removeItem(atPath: tmpDir)
            try FileManager.default.createDirectory(atPath: tmpDir, withIntermediateDirectories: true)

            // Download (max 50 MB to prevent DoS)
            downloadProgress = 0.1
            let (zipData, response) = try await URLSession.shared.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  zipData.count < 50 * 1024 * 1024 else {
                isDownloading = false
                return
            }

            downloadProgress = 0.5

            // Write zip
            let zipPath = "\(tmpDir)/Montana.app.zip"
            try zipData.write(to: URL(fileURLWithPath: zipPath))

            downloadProgress = 0.6

            // Unzip
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/unzip")
            process.arguments = ["-o", zipPath, "-d", tmpDir]
            process.standardOutput = FileHandle.nullDevice
            process.standardError = FileHandle.nullDevice
            try process.run()
            process.waitUntilExit()

            guard process.terminationStatus == 0 else {
                isDownloading = false
                return
            }

            downloadProgress = 0.8

            // Replace current app (safe swap)
            let currentAppPath = Bundle.main.bundlePath
            let newAppPath = "\(tmpDir)/Montana.app"
            let backupPath = "\(tmpDir)/Montana.app.backup"

            guard FileManager.default.fileExists(atPath: newAppPath),
                  FileManager.default.fileExists(atPath: "\(newAppPath)/Contents/MacOS/MontanaPresence") else {
                isDownloading = false
                return
            }

            // Backup current before removing
            try? FileManager.default.removeItem(atPath: backupPath)
            try FileManager.default.copyItem(atPath: currentAppPath, toPath: backupPath)
            try FileManager.default.removeItem(atPath: currentAppPath)
            do {
                try FileManager.default.copyItem(atPath: newAppPath, toPath: currentAppPath)
            } catch {
                // Restore backup if copy fails
                try? FileManager.default.copyItem(atPath: backupPath, toPath: currentAppPath)
                isDownloading = false
                return
            }

            downloadProgress = 1.0

            // Relaunch
            let reopenProcess = Process()
            reopenProcess.executableURL = URL(fileURLWithPath: "/usr/bin/open")
            reopenProcess.arguments = [currentAppPath]
            try reopenProcess.run()

            // Clean temp
            try? FileManager.default.removeItem(atPath: tmpDir)

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                exit(0)
            }

        } catch {
            isDownloading = false
            downloadProgress = 0
        }
    }
}
