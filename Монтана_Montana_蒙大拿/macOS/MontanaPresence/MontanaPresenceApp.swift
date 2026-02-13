import SwiftUI
import ServiceManagement
import AVFoundation
import IOKit

@main
struct MontanaPresenceApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        // Settings scene doesn't create windows - perfect for menu bar apps
        Settings {
            EmptyView()
        }
    }
}

@MainActor
class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var mainWindow: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // ╔══════════════════════════════════════════════════════════════════╗
        // ║  SINGLE INSTANCE ENFORCEMENT                                    ║
        // ║  1 устройство = 1 Montana. Строго.                              ║
        // ║  Автоматически убивает все дубликаты.                           ║
        // ╚══════════════════════════════════════════════════════════════════╝
        terminateOtherInstances()

        // ╔══════════════════════════════════════════════════════════════════╗
        // ║  DEVICE ID LOCK                                                 ║
        // ║  Привязка к hardware UUID. Строго.                              ║
        // ╚══════════════════════════════════════════════════════════════════╝
        checkDeviceBinding()

        setupStatusItem()
        setupMainWindow()

        // Show window on launch
        mainWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        // Menu bar label syncs directly from tick() — same call stack, zero lag
        PresenceEngine.shared.onTick = { [weak self] in
            self?.updateLabel()
        }

        Task { @MainActor in
            UpdateManager.shared.startChecking()
            // Tracking disabled by default — user must click START manually
        }
    }

    // Dock / Launchpad icon click — ALWAYS show window
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        guard let window = mainWindow else { return false }
        if window.isMiniaturized {
            window.deminiaturize(nil)
        }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        return true
    }

    // MARK: - Single Instance Protection (NSRunningApplication API)

    private func terminateOtherInstances() {
        let bundleID = Bundle.main.bundleIdentifier!
        let currentPID = ProcessInfo.processInfo.processIdentifier

        let runningInstances = NSWorkspace.shared.runningApplications.filter {
            $0.bundleIdentifier == bundleID && $0.processIdentifier != currentPID
        }

        if !runningInstances.isEmpty {
            print("⚠️ Found \(runningInstances.count) other Montana instances. Terminating...")
            for app in runningInstances {
                print("   Killing PID \(app.processIdentifier)")
                app.terminate()
                // Force kill if terminate() doesn't work
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                    if app.isActive {
                        app.forceTerminate()
                    }
                }
            }
        }
    }


    // MARK: - Device Binding

    private func getHardwareUUID() -> String? {
        let platformExpert = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOPlatformExpertDevice"))
        guard platformExpert != 0 else { return nil }
        defer { IOObjectRelease(platformExpert) }

        guard let serialNumberAsCFString = IORegistryEntryCreateCFProperty(
            platformExpert,
            kIOPlatformUUIDKey as CFString,
            kCFAllocatorDefault,
            0
        )?.takeRetainedValue() as? String else {
            return nil
        }

        return serialNumberAsCFString
    }

    private func checkDeviceBinding() {
        guard let currentDeviceID = getHardwareUUID() else {
            // Cannot get hardware UUID — allow (fallback)
            return
        }

        let savedDeviceID = UserDefaults.standard.string(forKey: "montana_device_id")

        if let saved = savedDeviceID {
            // Device already bound — check if matches
            if saved != currentDeviceID {
                let alert = NSAlert()
                alert.messageText = "Montana привязан к другому устройству"
                alert.informativeText = """
                Montana Protocol строго привязан к устройству при первом запуске.

                Это приложение настроено для другого Mac.

                Если вы хотите использовать Montana на этом устройстве:
                1. Экспортируйте кошелёк (адрес + ключи) на старом устройстве
                2. Удалите Montana.app
                3. Переустановите Montana на этом Mac
                4. Импортируйте кошелёк

                Device ID (этот Mac): \(currentDeviceID.prefix(16))...
                Device ID (привязан): \(saved.prefix(16))...
                """
                alert.alertStyle = .critical
                alert.addButton(withTitle: "Закрыть")
                alert.runModal()
                NSApp.terminate(nil)
                return
            }
        } else {
            // First run — bind to this device
            UserDefaults.standard.set(currentDeviceID, forKey: "montana_device_id")
            print("Montana bound to device: \(currentDeviceID)")
        }
    }

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .medium)
            button.title = "\u{0248}"
            button.target = self
            button.action = #selector(handleClick(_:))
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
        updateLabel()
    }

    private func setupMainWindow() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 800, height: 650),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Montana Protocol Ɉ"
        window.center()
        window.setFrameAutosaveName("MontanaMainWindow")
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .darkAqua)
        window.minSize = NSSize(width: 600, height: 500)

        let contentView = MainWindowView()
            .environmentObject(PresenceEngine.shared)
            .environmentObject(CameraManager.shared)
            .environmentObject(UpdateManager.shared)
            .environmentObject(VPNManager.shared)

        window.contentViewController = NSHostingController(rootView: contentView)
        mainWindow = window
    }

    @MainActor
    private func updateLabel() {
        let engine = PresenceEngine.shared
        var parts: [String] = []
        if engine.showBalanceInMenuBar {
            let formatter = NumberFormatter()
            formatter.numberStyle = .decimal
            formatter.groupingSeparator = ","
            let s = formatter.string(from: NSNumber(value: engine.displayBalance)) ?? "\(engine.displayBalance)"
            parts.append(s)
        }
        if engine.showSymbolInMenuBar {
            parts.append("\u{0248}")
        }
        if engine.showWeightInMenuBar {
            parts.append("x\(engine.weight)")
        }
        // Always show at least Ɉ so status item remains clickable
        statusItem.button?.title = parts.isEmpty ? "\u{0248}" : parts.joined(separator: " ")
    }

    // Left click → main window, Right click → context menu
    @objc func handleClick(_ sender: NSStatusBarButton) {
        guard let event = NSApp.currentEvent else { return }
        if event.type == .rightMouseUp {
            showContextMenu()
        } else {
            toggleMainWindow()
        }
    }

    private func toggleMainWindow() {
        guard let window = mainWindow else { return }
        if window.isVisible {
            window.orderOut(nil)
        } else {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    private func showContextMenu() {
        let menu = NSMenu()

        let settingsItem = NSMenuItem(title: "\u{041d}\u{0430}\u{0441}\u{0442}\u{0440}\u{043e}\u{0439}\u{043a}\u{0438}", action: #selector(openSettings), keyEquivalent: ",")
        settingsItem.target = self
        menu.addItem(settingsItem)

        let aboutItem = NSMenuItem(title: "\u{041e} \u{043f}\u{0440}\u{043e}\u{0433}\u{0440}\u{0430}\u{043c}\u{043c}\u{0435}", action: #selector(showAbout), keyEquivalent: "")
        aboutItem.target = self
        menu.addItem(aboutItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "\u{0412}\u{044b}\u{0439}\u{0442}\u{0438}", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
        statusItem.button?.performClick(nil)
        statusItem.menu = nil
    }

    @objc func openSettings() {
        guard let window = mainWindow else { return }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        // Switch to Settings tab
        NotificationCenter.default.post(name: .switchToSettingsTab, object: nil)
    }

    @objc func showAbout() {
        NSApp.activate(ignoringOtherApps: true)
        NSApp.orderFrontStandardAboutPanel(nil)
    }

    @objc func quitApp() {
        PresenceEngine.shared.stopTracking()
        NSApp.terminate(nil)
    }
}
