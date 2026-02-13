//
//  TimeChainExplorerView.swift
//  Montana — Цепочка Времени (Event Ledger)
//
//  Matches macOS v2.25.0: events + addresses tabs, pentagon icon
//

import SwiftUI

struct TimeChainExplorerView: View {
    @ObservedObject var wallet = WalletService.shared
    @State private var selectedTab = 0
    @State private var events: [[String: Any]] = []
    @State private var addresses: [[String: Any]] = []
    @State private var isLoading = true
    @State private var errorText = ""

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let gold = Color(hex: "D4AF37")
    private let cardBg = Color.white.opacity(0.05)

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 0) {
                // Tabs
                HStack(spacing: 0) {
                    tabButton("Транзакции", tab: 0)
                    tabButton("Адреса", tab: 1)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

                Divider()
                    .background(Color.white.opacity(0.1))

                if isLoading {
                    Spacer()
                    ProgressView()
                        .tint(cyan)
                    Text("Загрузка...")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                        .padding(.top, 8)
                    Spacer()
                } else if !errorText.isEmpty {
                    Spacer()
                    Text(errorText)
                        .font(.callout)
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
        }
        .navigationTitle("Цепочка Времени")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { Task { await loadData() } } label: {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(cyan)
                }
            }
        }
        .task { await loadData() }
    }

    // MARK: - Events Tab

    private var eventsTab: some View {
        ScrollView {
            LazyVStack(spacing: 6) {
                if events.isEmpty {
                    Text("Нет транзакций")
                        .font(.callout)
                        .foregroundColor(.white.opacity(0.4))
                        .padding(.top, 40)
                } else {
                    ForEach(Array(events.enumerated()), id: \.offset) { _, event in
                        eventRow(event)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
        .refreshable { await loadData() }
    }

    private func eventRow(_ event: [String: Any]) -> some View {
        let eventType = event["event_type"] as? String ?? ""
        let amount = event["amount"] as? Int ?? 0
        let toAddr = String((event["to_addr"] as? String ?? "").prefix(100))
        let fromAddr = String((event["from_addr"] as? String ?? "").prefix(100))
        let timestamp = event["timestamp_iso"] as? String ?? (event["timestamp"] as? String ?? "")
        let toAlias = event["to_alias"] as? String ?? ""
        let fromAlias = event["from_alias"] as? String ?? ""

        let myAddr = UserDefaults.standard.string(forKey: "montana_address") ?? ""
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

        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.system(size: 14))
                Text(eventType)
                    .font(.system(size: 13, weight: .bold, design: .monospaced))
                    .foregroundColor(color)
                if isUserInvolved {
                    Text("МОЙ")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(cyan)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .background(cyan.opacity(0.15))
                        .cornerRadius(4)
                }
                Spacer()
                Text(formatAmount(amount))
                    .font(.system(size: 14, weight: .bold, design: .monospaced))
                    .foregroundColor(color)
            }

            if eventType == "EMISSION" {
                HStack(spacing: 4) {
                    Text(fromAlias.isEmpty ? "Ɉ-0" : fromAlias)
                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                        .foregroundColor(.green.opacity(0.7))
                    Image(systemName: "arrow.right")
                        .font(.system(size: 9))
                        .foregroundColor(.white.opacity(0.3))
                    Text(displayAddr(toAddr, alias: toAlias))
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white.opacity(0.5))
                }
            } else if eventType == "TRANSFER" {
                HStack(spacing: 4) {
                    Text(displayAddr(fromAddr, alias: fromAlias))
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white.opacity(0.5))
                    Image(systemName: "arrow.right")
                        .font(.system(size: 9))
                        .foregroundColor(.white.opacity(0.3))
                    Text(displayAddr(toAddr, alias: toAlias))
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white.opacity(0.5))
                }
            } else if eventType == "ESCROW" {
                HStack(spacing: 4) {
                    Text(displayAddr(fromAddr, alias: fromAlias))
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white.opacity(0.5))
                    Image(systemName: "arrow.right")
                        .font(.system(size: 9))
                        .foregroundColor(.white.opacity(0.3))
                    Text("ESCROW")
                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                        .foregroundColor(.orange)
                }
            }

            Text(formatTimestamp(timestamp))
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(.white.opacity(0.3))
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(isUserInvolved ? cyan.opacity(0.05) : cardBg)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(isUserInvolved ? cyan.opacity(0.3) : Color.clear, lineWidth: 1)
        )
    }

    // MARK: - Addresses Tab

    private var addressesTab: some View {
        ScrollView {
            LazyVStack(spacing: 6) {
                if addresses.isEmpty {
                    Text("Нет адресов")
                        .font(.callout)
                        .foregroundColor(.white.opacity(0.4))
                        .padding(.top, 40)
                } else {
                    ForEach(Array(addresses.enumerated()), id: \.offset) { _, addr in
                        addressRow(addr)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
        .refreshable { await loadData() }
    }

    private func addressRow(_ addr: [String: Any]) -> some View {
        let address = addr["address"] as? String ?? ""
        let balance = addr["balance"] as? Int ?? 0
        let walletType = addr["type"] as? String ?? ""
        let alias = addr["alias"] as? String ?? ""
        let customAlias = addr["custom_alias"] as? String ?? ""
        let agentName = addr["agent_name"] as? String ?? ""

        let isAgent = walletType.contains("agent") || walletType.contains("AI")
        let typeIcon = isAgent ? "cpu" : "person.fill"
        let typeColor: Color = isAgent ? .purple : cyan

        return HStack(spacing: 12) {
            Image(systemName: typeIcon)
                .foregroundColor(typeColor)
                .font(.system(size: 16))
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    if !alias.isEmpty {
                        Text(alias)
                            .font(.system(size: 14, weight: .bold, design: .monospaced))
                            .foregroundColor(gold)
                    }
                    if !customAlias.isEmpty {
                        Text(customAlias)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(cyan)
                    } else if !agentName.isEmpty {
                        Text(agentName)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(.purple.opacity(0.8))
                    }
                }
                Text(String(address.prefix(8)) + "..." + String(address.suffix(4)))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.white.opacity(0.4))
            }

            Spacer()

            Text(formatAmount(balance))
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundColor(gold)
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(cardBg)
        )
    }

    // MARK: - Helpers

    private func tabButton(_ title: String, tab: Int) -> some View {
        Button(action: { selectedTab = tab }) {
            Text(title)
                .font(.system(size: 14, weight: selectedTab == tab ? .bold : .regular))
                .foregroundColor(selectedTab == tab ? cyan : .white.opacity(0.5))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(selectedTab == tab ? cyan.opacity(0.1) : Color.clear)
                .cornerRadius(8)
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
        guard ts.count >= 20 else { return ts }
        let parts = ts.split(separator: ".", maxSplits: 1)
        guard parts.count >= 1 else { return ts }

        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: ts) {
            let df = DateFormatter()
            df.dateFormat = "dd.MM.yyyy HH:mm:ss"
            let base = df.string(from: date)

            if parts.count == 2 {
                let fracPart = String(parts[1]).replacingOccurrences(of: "Z", with: "")
                let nanos = fracPart.padding(toLength: 9, withPad: "0", startingAt: 0)
                return "\(base).\(nanos)"
            }
            return base
        }

        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: String(parts[0]) + "Z") {
            let df = DateFormatter()
            df.dateFormat = "dd.MM.yyyy HH:mm:ss"
            let base = df.string(from: date)
            if parts.count == 2 {
                let fracPart = String(parts[1]).replacingOccurrences(of: "Z", with: "")
                let nanos = fracPart.padding(toLength: 9, withPad: "0", startingAt: 0)
                return "\(base).\(nanos)"
            }
            return base
        }

        return String(ts.prefix(30))
    }

    private func loadData() async {
        isLoading = true
        errorText = ""
        do {
            async let evts = wallet.fetchEvents(limit: 50)
            async let addrs = wallet.fetchAddresses()
            var fetchedEvents = try await evts
            addresses = try await addrs

            // КРИТИЧНО: Сортировка по timestamp_ns (наносекунды) — newest first
            fetchedEvents.sort { evt1, evt2 in
                // [FIX] Fallback на timestamp * 1e9 для старых событий (как в Python)
                let ts1 = evt1["timestamp_ns"] as? Int ?? Int((evt1["timestamp"] as? Double ?? 0) * 1e9)
                let ts2 = evt2["timestamp_ns"] as? Int ?? Int((evt2["timestamp"] as? Double ?? 0) * 1e9)
                return ts1 > ts2
            }
            events = fetchedEvents

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
