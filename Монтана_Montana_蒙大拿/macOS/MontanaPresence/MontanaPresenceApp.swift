import SwiftUI
import ServiceManagement
import AVFoundation

@main
struct MontanaPresenceApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            SettingsView()
                .environmentObject(PresenceEngine.shared)
                .environmentObject(UpdateManager.shared)
                .environmentObject(VPNManager.shared)
        }
    }
}

@MainActor
class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var popover: NSPopover!

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        setupPopover()

        // Menu bar label syncs directly from tick() — same call stack, zero lag
        PresenceEngine.shared.onTick = { [weak self] in
            self?.updateLabel()
        }

        try? SMAppService.mainApp.register()
        Task { @MainActor in
            UpdateManager.shared.startChecking()
            PresenceEngine.shared.autoStart()
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

    private func setupPopover() {
        popover = NSPopover()
        popover.contentSize = NSSize(width: 320, height: 720)
        popover.behavior = .transient
        popover.animates = false
        popover.appearance = NSAppearance(named: .darkAqua)

        let hostingController = NSHostingController(
            rootView: MenuBarView()
                .environmentObject(PresenceEngine.shared)
                .environmentObject(CameraManager.shared)
                .environmentObject(UpdateManager.shared)
                .environmentObject(VPNManager.shared)
        )
        popover.contentViewController = hostingController
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
            parts.append("\(s) \u{0248}")
        } else {
            parts.append("\u{0248}")
        }
        if engine.showWeightInMenuBar {
            parts.append("x\(engine.weight)")
        }
        statusItem.button?.title = parts.joined(separator: " ")
    }

    // Left click → popover, Right click → context menu
    @objc func handleClick(_ sender: NSStatusBarButton) {
        guard let event = NSApp.currentEvent else { return }
        if event.type == .rightMouseUp {
            showContextMenu()
        } else {
            togglePopover(sender)
        }
    }

    private func togglePopover(_ sender: NSStatusBarButton) {
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: sender.bounds, of: sender, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
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
        NSApp.activate(ignoringOtherApps: true)
        if #available(macOS 14.0, *) {
            NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
        } else {
            NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
        }
    }

    @objc func showAbout() {
        NSApp.activate(ignoringOtherApps: true)
        NSApp.orderFrontStandardAboutPanel(nil)
    }

    @objc func quitApp() {
        PresenceEngine.shared.stopTracking()
        NSApp.terminate(nil)
    }

    // TimeChain Explorer window
    func openTimeChainExplorer() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 900, height: 700),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "TimeChain Explorer — Montana Protocol"
        window.center()
        window.setFrameAutosaveName("TimeChainExplorer")
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .darkAqua)

        let contentView = TimeChainExplorerView()
            .environmentObject(PresenceEngine.shared)
            .frame(minWidth: 700, minHeight: 500)

        let hostingController = NSHostingController(rootView: contentView)
        window.contentViewController = hostingController
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
