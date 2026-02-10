import Foundation
import Combine

@MainActor
class PresenceEngine: ObservableObject {
    static let shared = PresenceEngine()

    // Published state
    @Published var isTracking = false
    @Published var isPresent = false
    @Published var sessionSeconds: Int = 0
    @Published var pendingSeconds: Int = 0
    @Published var serverBalance: Int = 0
    @Published var isOnline = false

    var displayBalance: Int {
        serverBalance + pendingSeconds
    }

    // Timers
    private var tickTimer: Timer?
    private var reportTimer: Timer?

    // Face detection tracking
    private var consecutiveMisses = 0
    private let missThreshold = 2

    // Persistence keys
    private let pendingKey = "montana_presence_pending"
    private let balanceKey = "montana_presence_balance"
    private let totalKey = "montana_presence_total"

    // API
    private let api = MontanaAPIClient()

    private init() {
        pendingSeconds = UserDefaults.standard.integer(forKey: pendingKey)
        serverBalance = UserDefaults.standard.integer(forKey: balanceKey)
    }

    // MARK: - Address

    var address: String? {
        get { UserDefaults.standard.string(forKey: "montana_address") }
        set {
            UserDefaults.standard.set(newValue, forKey: "montana_address")
        }
    }

    // MARK: - Tracking Control

    func startTracking() {
        guard address != nil else { return }
        guard !isTracking else { return }

        isTracking = true
        sessionSeconds = 0
        consecutiveMisses = 0

        CameraManager.shared.startCamera()

        tickTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.tick()
            }
        }

        reportTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.reportToServer()
            }
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

    // MARK: - Face Detection Callback

    func faceDetectionResult(_ detected: Bool) {
        if detected {
            consecutiveMisses = 0
            if !isPresent {
                isPresent = true
            }
        } else {
            consecutiveMisses += 1
            if consecutiveMisses >= missThreshold {
                isPresent = false
            }
        }
    }

    // MARK: - Tick (every second)

    private func tick() {
        guard isTracking, isPresent else { return }

        sessionSeconds += 1
        pendingSeconds += 1

        if sessionSeconds % 10 == 0 {
            UserDefaults.standard.set(pendingSeconds, forKey: pendingKey)
        }
    }

    // MARK: - Server Communication

    func reportToServer() async {
        guard let addr = address, !addr.isEmpty else { return }
        guard pendingSeconds > 0 else { return }

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
    }
}
