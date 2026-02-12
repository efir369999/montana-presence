import SwiftUI

struct TimeChainExplorerView: View {
    @EnvironmentObject var engine: PresenceEngine
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTab = 0
    @State private var events: [[String: Any]] = []
    @State private var addresses: [[String: Any]] = []
    @State private var isLoading = true
    @State private var errorText = ""
    @State private var lastRefresh: Date = .distantPast

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)
    private let cardBg = Color(red: 0.09, green: 0.09, blue: 0.12)

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "cube.transparent")
                    .foregroundColor(cyan)
                Text("\u{041e}\u{0431}\u{043e}\u{0437}\u{0440}\u{0435}\u{0432}\u{0430}\u{0442}\u{0435}\u{043b}\u{044c} TimeChain")
                    .font(.system(size: 14, weight: .bold))
                Spacer()
                Button(action: { loadData() }) {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("\u{041e}\u{0431}\u{043d}\u{043e}\u{0432}\u{0438}\u{0442}\u{044c}")
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 8)

            // Tabs
            HStack(spacing: 0) {
                tabButton("\u{0422}\u{0440}\u{0430}\u{043d}\u{0437}\u{0430}\u{043a}\u{0446}\u{0438}\u{0438}", tab: 0)
                tabButton("\u{0410}\u{0434}\u{0440}\u{0435}\u{0441}\u{0430}", tab: 1)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 8)

            Divider()

            if isLoading {
                Spacer()
                ProgressView()
                    .controlSize(.small)
                Text("\u{0417}\u{0430}\u{0433}\u{0440}\u{0443}\u{0437}\u{043a}\u{0430}...")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
            } else if !errorText.isEmpty {
                Spacer()
                Text(errorText)
                    .font(.caption)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
                    .padding()
                Spacer()
            } else {
                if selectedTab == 0 {
                    eventsTab
                } else {
                    addressesTab
                }
            }
        }
        .frame(width: 360, height: 500)
        .onAppear { loadData() }
    }

    // MARK: - Events Tab

    private var eventsTab: some View {
        ScrollView {
            LazyVStack(spacing: 4) {
                if events.isEmpty {
                    Text("\u{041d}\u{0435}\u{0442} \u{0442}\u{0440}\u{0430}\u{043d}\u{0437}\u{0430}\u{043a}\u{0446}\u{0438}\u{0439}")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.top, 20)
                } else {
                    ForEach(Array(events.enumerated()), id: \.offset) { _, event in
                        eventRow(event)
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
    }

    private func eventRow(_ event: [String: Any]) -> some View {
        let eventType = event["event_type"] as? String ?? ""
        let amount = event["amount"] as? Int ?? 0
        let toAddr = String((event["to_addr"] as? String ?? "").prefix(100))
        let fromAddr = String((event["from_addr"] as? String ?? "").prefix(100))
        let timestamp = event["timestamp"] as? String ?? ""
        let toAlias = event["to_alias"] as? String ?? ""
        let fromAlias = event["from_alias"] as? String ?? ""

        let myAddr = engine.address ?? ""
        let isUserInvolved = (!myAddr.isEmpty) && (fromAddr == myAddr || toAddr == myAddr)

        let color: Color = {
            switch eventType {
            case "EMISSION": return .green
            case "TRANSFER": return cyan
            case "ESCROW": return .orange
            default: return .secondary
            }
        }()

        let icon: String = {
            switch eventType {
            case "EMISSION": return "plus.circle.fill"
            case "TRANSFER": return "arrow.right.circle.fill"
            case "ESCROW": return "lock.circle.fill"
            default: return "questionmark.circle"
            }
        }()

        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.system(size: 12))
                Text(eventType)
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .foregroundColor(color)
                if isUserInvolved {
                    Text("МОЙ")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundColor(cyan)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(cyan.opacity(0.15))
                        .cornerRadius(3)
                }
                Spacer()
                Text(formatAmount(amount))
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(color)
            }

            if eventType == "EMISSION" {
                HStack(spacing: 4) {
                    Text("TIME_BANK")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                    Image(systemName: "arrow.right")
                        .font(.system(size: 8))
                        .foregroundColor(.secondary)
                    Text(displayAddr(toAddr, alias: toAlias))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                }
            } else if eventType == "TRANSFER" {
                HStack(spacing: 4) {
                    Text(displayAddr(fromAddr, alias: fromAlias))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                    Image(systemName: "arrow.right")
                        .font(.system(size: 8))
                        .foregroundColor(.secondary)
                    Text(displayAddr(toAddr, alias: toAlias))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                }
            } else if eventType == "ESCROW" {
                HStack(spacing: 4) {
                    Text(displayAddr(fromAddr, alias: fromAlias))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.secondary)
                    Image(systemName: "arrow.right")
                        .font(.system(size: 8))
                        .foregroundColor(.secondary)
                    Text("ESCROW")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundColor(.orange)
                }
            }

            Text(formatTimestamp(timestamp))
                .font(.system(size: 9))
                .foregroundColor(Color.secondary.opacity(0.7))
        }
        .padding(8)
        .background(isUserInvolved ? cyan.opacity(0.05) : cardBg)
        .cornerRadius(6)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(isUserInvolved ? cyan.opacity(0.3) : Color.clear, lineWidth: 1)
        )
    }

    // MARK: - Addresses Tab

    private var addressesTab: some View {
        ScrollView {
            LazyVStack(spacing: 4) {
                if addresses.isEmpty {
                    Text("\u{041d}\u{0435}\u{0442} \u{0430}\u{0434}\u{0440}\u{0435}\u{0441}\u{043e}\u{0432}")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.top, 20)
                } else {
                    ForEach(Array(addresses.enumerated()), id: \.offset) { _, addr in
                        addressRow(addr)
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
    }

    private func addressRow(_ addr: [String: Any]) -> some View {
        let address = addr["address"] as? String ?? ""
        let balance = addr["balance"] as? Int ?? 0
        let walletType = addr["type"] as? String ?? ""
        let alias = addr["alias"] as? String ?? ""
        let number = addr["number"] as? Int ?? 0

        let isAgent = walletType.contains("agent") || walletType.contains("AI")
        let typeIcon = isAgent ? "cpu" : "person.fill"
        let typeColor: Color = isAgent ? .purple : cyan

        return HStack(spacing: 8) {
            Image(systemName: typeIcon)
                .foregroundColor(typeColor)
                .font(.system(size: 12))
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    if number > 0 {
                        Text("\u{0248}-\(number)")
                            .font(.system(size: 12, weight: .bold, design: .monospaced))
                            .foregroundColor(gold)
                    }
                    if !alias.isEmpty {
                        Text(alias)
                            .font(.system(size: 10))
                            .foregroundColor(.secondary)
                    }
                }
                Text(String(address.prefix(8)) + "..." + String(address.suffix(4)))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(Color.secondary.opacity(0.6))
            }

            Spacer()

            Text(formatAmount(balance))
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundColor(gold)
        }
        .padding(8)
        .background(cardBg)
        .cornerRadius(6)
    }

    // MARK: - Helpers

    private func tabButton(_ title: String, tab: Int) -> some View {
        Button(action: { selectedTab = tab }) {
            Text(title)
                .font(.system(size: 12, weight: selectedTab == tab ? .bold : .regular))
                .foregroundColor(selectedTab == tab ? cyan : .secondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(selectedTab == tab ? cyan.opacity(0.1) : Color.clear)
                .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }

    private func displayAddr(_ addr: String, alias: String) -> String {
        if !alias.isEmpty { return alias }
        guard addr.count > 10 else { return addr }
        return String(addr.prefix(6)) + "..." + String(addr.suffix(4))
    }

    private func formatAmount(_ amount: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        let formatted = formatter.string(from: NSNumber(value: amount)) ?? "\(amount)"
        return "\(formatted) \u{0248}"
    }

    private func formatTimestamp(_ ts: String) -> String {
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: ts) {
            let df = DateFormatter()
            df.dateFormat = "dd.MM.yyyy HH:mm"
            return df.string(from: date)
        }
        // Try without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: ts) {
            let df = DateFormatter()
            df.dateFormat = "dd.MM.yyyy HH:mm"
            return df.string(from: date)
        }
        return String(ts.prefix(19))
    }

    private func loadData() {
        let now = Date()
        guard now.timeIntervalSince(lastRefresh) >= 2.0 || lastRefresh == .distantPast else { return }
        lastRefresh = now
        isLoading = true
        errorText = ""
        Task { @MainActor in
            do {
                async let evts = engine.api.fetchEvents(limit: 50)
                async let addrs = engine.api.fetchAddresses()
                events = try await evts
                addresses = try await addrs
                // Sort addresses by balance descending
                addresses.sort {
                    ($0["balance"] as? Int ?? 0) > ($1["balance"] as? Int ?? 0)
                }
                isLoading = false
            } catch {
                errorText = "Ошибка загрузки. Попробуйте позже"
                isLoading = false
            }
        }
    }
}
