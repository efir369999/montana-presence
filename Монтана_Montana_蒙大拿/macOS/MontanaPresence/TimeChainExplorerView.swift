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
    @State private var expandedEvents: Set<Int> = []
    @State private var autoRefresh = true
    @State private var refreshTimer: Timer?
    @State private var eventCount = 100
    @State private var copiedText: String?

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)
    private let cardBg = Color(red: 0.09, green: 0.09, blue: 0.12)
    private let hashColor = Color(red: 0.55, green: 0.55, blue: 0.65)

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "pentagon")
                    .foregroundColor(cyan)
                Text("Цепочка Времени")
                    .font(.system(size: 14, weight: .bold))
                Spacer()

                // Live indicator
                if autoRefresh {
                    HStack(spacing: 3) {
                        Circle()
                            .fill(.green)
                            .frame(width: 6, height: 6)
                        Text("LIVE")
                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                            .foregroundColor(.green)
                    }
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(.green.opacity(0.1))
                    .cornerRadius(4)
                }

                Button(action: { autoRefresh.toggle(); setupTimer() }) {
                    Image(systemName: autoRefresh ? "pause.circle" : "play.circle")
                        .foregroundColor(autoRefresh ? .green : .secondary)
                }
                .buttonStyle(.plain)
                .help(autoRefresh ? "Пауза" : "Авто-обновление")

                Button(action: { loadData() }) {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Обновить")

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
                tabButton("Транзакции (\(events.count))", tab: 0)
                tabButton("Адреса (\(addresses.count))", tab: 1)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 8)

            Divider()

            // Copied toast
            if let copied = copiedText {
                HStack {
                    Image(systemName: "doc.on.doc.fill")
                        .font(.system(size: 9))
                    Text(copied)
                        .font(.system(size: 9, design: .monospaced))
                        .lineLimit(1)
                }
                .foregroundColor(.green)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(.green.opacity(0.1))
                .cornerRadius(4)
                .padding(.top, 4)
                .transition(.opacity)
            }

            if isLoading {
                Spacer()
                ProgressView()
                    .controlSize(.small)
                Text("Загрузка...")
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
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            loadData()
            setupTimer()
        }
        .onDisappear {
            refreshTimer?.invalidate()
            refreshTimer = nil
        }
    }

    // MARK: - Auto-refresh Timer

    private func setupTimer() {
        refreshTimer?.invalidate()
        refreshTimer = nil
        if autoRefresh {
            refreshTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { _ in
                loadData()
            }
        }
    }

    // MARK: - Events Tab

    private var eventsTab: some View {
        ScrollView {
            LazyVStack(spacing: 3) {
                if events.isEmpty {
                    Text("Нет транзакций")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.top, 20)
                } else {
                    ForEach(Array(events.enumerated()), id: \.offset) { idx, event in
                        eventRow(event, index: idx)
                    }
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
        }
    }

    private func eventRow(_ event: [String: Any], index: Int) -> some View {
        let eventType = event["event_type"] as? String ?? ""
        let amount = event["amount"] as? Int ?? 0
        let toAddr = event["to_addr"] as? String ?? ""
        let fromAddr = event["from_addr"] as? String ?? ""
        let timestamp = event["timestamp_iso"] as? String ?? (event["timestamp"] as? String ?? "")
        let toAlias = event["to_alias"] as? String ?? ""
        let fromAlias = event["from_alias"] as? String ?? ""
        let eventId = event["event_id"] as? String ?? ""
        let eventHash = event["event_hash"] as? String ?? ""
        let prevHash = event["prev_hash"] as? String ?? ""
        let nodeId = event["node_id"] as? String ?? ""
        let metadata = event["metadata"] as? [String: Any]
        let isExpanded = expandedEvents.contains(index)

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

        return VStack(alignment: .leading, spacing: 0) {
            // ── Compact row (always visible) ──
            Button(action: {
                withAnimation(.easeInOut(duration: 0.15)) {
                    if expandedEvents.contains(index) {
                        expandedEvents.remove(index)
                    } else {
                        expandedEvents.insert(index)
                    }
                }
            }) {
                VStack(alignment: .leading, spacing: 4) {
                    // Line 1: type + amount + time
                    HStack(spacing: 6) {
                        Image(systemName: icon)
                            .foregroundColor(color)
                            .font(.system(size: 11))
                        Text(eventType)
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(color)
                        if isUserInvolved {
                            Text("МОЙ")
                                .font(.system(size: 7, weight: .bold))
                                .foregroundColor(cyan)
                                .padding(.horizontal, 3)
                                .padding(.vertical, 1)
                                .background(cyan.opacity(0.15))
                                .cornerRadius(3)
                        }
                        if !eventId.isEmpty {
                            Text("#\(shortId(eventId))")
                                .font(.system(size: 8, design: .monospaced))
                                .foregroundColor(hashColor)
                        }
                        Spacer()
                        Text(formatAmount(amount))
                            .font(.system(size: 11, weight: .bold, design: .monospaced))
                            .foregroundColor(color)
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: 8))
                            .foregroundColor(.secondary.opacity(0.5))
                    }

                    // Line 2: from → to
                    HStack(spacing: 4) {
                        if eventType == "EMISSION" {
                            Text("Ɉ-0")
                                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                .foregroundColor(.green.opacity(0.7))
                        } else {
                            addrLabel(fromAddr, alias: fromAlias, isMine: fromAddr == myAddr)
                        }
                        Image(systemName: "arrow.right")
                            .font(.system(size: 7))
                            .foregroundColor(.secondary.opacity(0.5))
                        if eventType == "ESCROW" {
                            Text("ESCROW")
                                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                .foregroundColor(.orange)
                        } else {
                            addrLabel(toAddr, alias: toAlias, isMine: toAddr == myAddr)
                        }
                        Spacer()
                        Text(formatTimestampShort(timestamp))
                            .font(.system(size: 8, design: .monospaced))
                            .foregroundColor(.secondary.opacity(0.6))
                    }
                }
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)

            // ── Expanded detail ──
            if isExpanded {
                Divider()
                    .padding(.horizontal, 8)
                VStack(alignment: .leading, spacing: 5) {
                    // Event ID
                    if !eventId.isEmpty {
                        detailRow(label: "EVENT ID", value: eventId)
                    }

                    // Event Hash
                    if !eventHash.isEmpty {
                        detailRow(label: "HASH", value: eventHash)
                    }

                    // Prev Hash
                    if !prevHash.isEmpty {
                        detailRow(label: "PREV HASH", value: prevHash)
                    }

                    // Node ID
                    if !nodeId.isEmpty {
                        detailRow(label: "NODE", value: nodeId)
                    }

                    // From address (full)
                    if !fromAddr.isEmpty && fromAddr != "EMISSION" {
                        detailRow(label: "FROM", value: fromAddr, extra: fromAlias.isEmpty ? nil : fromAlias)
                    }

                    // To address (full)
                    if !toAddr.isEmpty {
                        detailRow(label: "TO", value: toAddr, extra: toAlias.isEmpty ? nil : toAlias)
                    }

                    // Amount
                    detailRow(label: "AMOUNT", value: "\(amount) Ɉ")

                    // Timestamp full (nanosecond)
                    detailRow(label: "TIME", value: formatTimestampFull(timestamp))

                    // Metadata
                    if let meta = metadata, !meta.isEmpty {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("METADATA")
                                .font(.system(size: 7, weight: .bold, design: .monospaced))
                                .foregroundColor(gold)
                            ForEach(Array(meta.keys.sorted()), id: \.self) { key in
                                HStack(spacing: 4) {
                                    Text(key + ":")
                                        .font(.system(size: 8, design: .monospaced))
                                        .foregroundColor(.secondary)
                                    Text("\(meta[key].map { "\($0)" } ?? "")")
                                        .font(.system(size: 8, design: .monospaced))
                                        .foregroundColor(.white.opacity(0.8))
                                        .lineLimit(2)
                                    Spacer()
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
            }
        }
        .background(isUserInvolved ? cyan.opacity(0.05) : cardBg)
        .cornerRadius(6)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(isUserInvolved ? cyan.opacity(0.3) : Color.white.opacity(0.03), lineWidth: 1)
        )
    }

    // MARK: - Detail Row

    private func detailRow(label: String, value: String, extra: String? = nil) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            HStack(spacing: 4) {
                Text(label)
                    .font(.system(size: 7, weight: .bold, design: .monospaced))
                    .foregroundColor(gold)
                    .frame(width: 62, alignment: .leading)
                if let ex = extra {
                    Text(ex)
                        .font(.system(size: 8, weight: .semibold, design: .monospaced))
                        .foregroundColor(cyan)
                }
                Spacer()
                Button(action: { copyToClipboard(value) }) {
                    Image(systemName: "doc.on.doc")
                        .font(.system(size: 7))
                        .foregroundColor(.secondary.opacity(0.4))
                }
                .buttonStyle(.plain)
                .help("Скопировать")
            }
            Text(value)
                .font(.system(size: 8, design: .monospaced))
                .foregroundColor(.white.opacity(0.7))
                .lineLimit(2)
                .textSelection(.enabled)
        }
    }

    // MARK: - Addresses Tab

    private var addressesTab: some View {
        ScrollView {
            LazyVStack(spacing: 3) {
                if addresses.isEmpty {
                    Text("Нет адресов")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.top, 20)
                } else {
                    // Summary bar
                    HStack {
                        let total = addresses.reduce(0) { $0 + ($1["balance"] as? Int ?? 0) }
                        let agents = addresses.filter {
                            let t = $0["type"] as? String ?? ""
                            return t.contains("agent") || t.contains("AI")
                        }.count
                        let humans = addresses.count - agents
                        Text("\(humans) чел.")
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(cyan)
                        Text("·")
                            .foregroundColor(.secondary)
                        Text("\(agents) агент.")
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(.purple)
                        Text("·")
                            .foregroundColor(.secondary)
                        Text("Σ \(formatAmount(total))")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(gold)
                        Spacer()
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(cardBg)
                    .cornerRadius(4)

                    ForEach(Array(addresses.enumerated()), id: \.offset) { idx, addr in
                        addressRow(addr, rank: idx + 1)
                    }
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
        }
    }

    private func addressRow(_ addr: [String: Any], rank: Int) -> some View {
        let address = addr["address"] as? String ?? ""
        let balance = addr["balance"] as? Int ?? 0
        let walletType = addr["type"] as? String ?? ""
        let alias = addr["alias"] as? String ?? ""
        let customAlias = addr["custom_alias"] as? String ?? ""
        let agentName = addr["agent_name"] as? String ?? ""

        let isAgent = walletType.contains("agent") || walletType.contains("AI")
        let typeIcon = isAgent ? "cpu" : "person.fill"
        let typeColor: Color = isAgent ? .purple : cyan

        let myAddr = engine.address ?? ""
        let isMine = address == myAddr

        return HStack(spacing: 6) {
            // Rank
            Text("#\(rank)")
                .font(.system(size: 8, weight: .bold, design: .monospaced))
                .foregroundColor(.secondary.opacity(0.5))
                .frame(width: 22, alignment: .trailing)

            Image(systemName: typeIcon)
                .foregroundColor(typeColor)
                .font(.system(size: 11))
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    if !alias.isEmpty {
                        Text(alias)
                            .font(.system(size: 11, weight: .bold, design: .monospaced))
                            .foregroundColor(gold)
                    }
                    if !customAlias.isEmpty {
                        Text(customAlias)
                            .font(.system(size: 9, weight: .medium))
                            .foregroundColor(cyan)
                    } else if !agentName.isEmpty {
                        Text(agentName)
                            .font(.system(size: 9, weight: .medium))
                            .foregroundColor(.purple.opacity(0.8))
                    }
                    if isMine {
                        Text("МОЙ")
                            .font(.system(size: 7, weight: .bold))
                            .foregroundColor(cyan)
                            .padding(.horizontal, 3)
                            .padding(.vertical, 1)
                            .background(cyan.opacity(0.15))
                            .cornerRadius(3)
                    }
                }
                Text(address)
                    .font(.system(size: 8, design: .monospaced))
                    .foregroundColor(.secondary.opacity(0.5))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            Spacer()

            Text(formatAmount(balance))
                .font(.system(size: 11, weight: .bold, design: .monospaced))
                .foregroundColor(gold)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(isMine ? cyan.opacity(0.05) : cardBg)
        .cornerRadius(6)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(isMine ? cyan.opacity(0.3) : Color.clear, lineWidth: 1)
        )
    }

    // MARK: - Helpers

    private func addrLabel(_ addr: String, alias: String, isMine: Bool) -> some View {
        Group {
            if !alias.isEmpty {
                Text(alias)
                    .font(.system(size: 9, weight: .semibold, design: .monospaced))
                    .foregroundColor(isMine ? cyan : gold)
            } else if addr.count > 12 {
                Text(String(addr.prefix(6)) + "…" + String(addr.suffix(4)))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(isMine ? cyan : .secondary)
            } else {
                Text(addr)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(.secondary)
            }
        }
    }

    private func shortId(_ id: String) -> String {
        if id.count > 12 {
            return String(id.prefix(6)) + "…" + String(id.suffix(4))
        }
        return id
    }

    private func tabButton(_ title: String, tab: Int) -> some View {
        Button(action: { selectedTab = tab }) {
            Text(title)
                .font(.system(size: 11, weight: selectedTab == tab ? .bold : .regular))
                .foregroundColor(selectedTab == tab ? cyan : .secondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(selectedTab == tab ? cyan.opacity(0.1) : Color.clear)
                .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }

    private func formatAmount(_ amount: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        let formatted = formatter.string(from: NSNumber(value: amount)) ?? "\(amount)"
        return "\(formatted) Ɉ"
    }

    private func formatTimestampShort(_ ts: String) -> String {
        // "2026-02-12T15:30:45.123Z" → "12.02 15:30:45"
        guard ts.count >= 16 else { return ts }
        let parts = ts.split(separator: ".", maxSplits: 1)
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: ts) {
            let df = DateFormatter()
            df.dateFormat = "dd.MM HH:mm:ss"
            return df.string(from: date)
        }
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: String(parts[0]) + "Z") {
            let df = DateFormatter()
            df.dateFormat = "dd.MM HH:mm:ss"
            return df.string(from: date)
        }
        return String(ts.prefix(19))
    }

    private func formatTimestampFull(_ ts: String) -> String {
        // Full with nanoseconds: "12.02.2026 15:30:45.123456789"
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

    private func copyToClipboard(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        withAnimation { copiedText = String(text.prefix(30)) + (text.count > 30 ? "…" : "") }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            withAnimation { copiedText = nil }
        }
    }

    private func loadData() {
        let now = Date()
        guard now.timeIntervalSince(lastRefresh) >= 2.0 || lastRefresh == .distantPast else { return }
        lastRefresh = now
        if events.isEmpty { isLoading = true }
        errorText = ""
        Task { @MainActor in
            do {
                async let evts = engine.api.fetchEvents(limit: eventCount)
                async let addrs = engine.api.fetchAddresses()
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
                if events.isEmpty {
                    errorText = "Ошибка загрузки. Попробуйте позже"
                }
                isLoading = false
            }
        }
    }
}
