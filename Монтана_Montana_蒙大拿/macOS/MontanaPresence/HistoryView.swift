import SwiftUI

struct HistoryView: View {
    @EnvironmentObject var engine: PresenceEngine
    @Environment(\.dismiss) private var dismiss
    @State private var displayItems: [HistoryItem] = []
    @State private var isLoading = true
    @State private var errorText = ""
    @State private var lastRefresh: Date = .distantPast

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let gold = Color(red: 0.85, green: 0.68, blue: 0.25)
    private let goldLight = Color(red: 0.95, green: 0.82, blue: 0.45)
    private let cardBg = Color(red: 0.09, green: 0.09, blue: 0.12)

    struct HistoryItem: Identifiable {
        let id = UUID()
        var eventType: String       // EMISSION or TRANSFER
        var amount: Int
        var fromAddr: String
        var toAddr: String
        var fromAlias: String
        var toAlias: String
        var timestamp: String
        var emissionCount: Int       // how many emissions consolidated (1 for transfers)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "clock.arrow.circlepath")
                    .foregroundColor(gold)
                Text("\u{0418}\u{0441}\u{0442}\u{043e}\u{0440}\u{0438}\u{044f}")
                    .font(.system(size: 14, weight: .bold))
                Spacer()
                Button(action: { loadHistory() }) {
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
            } else if displayItems.isEmpty {
                Spacer()
                Image(systemName: "tray")
                    .font(.system(size: 28))
                    .foregroundColor(.secondary.opacity(0.5))
                Text("\u{041d}\u{0435}\u{0442} \u{0442}\u{0440}\u{0430}\u{043d}\u{0437}\u{0430}\u{043a}\u{0446}\u{0438}\u{0439}")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.top, 4)
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 4) {
                        ForEach(displayItems) { item in
                            historyRow(item)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
            }
        }
        .frame(width: 360, height: 500)
        .onAppear { loadHistory() }
    }

    private func historyRow(_ item: HistoryItem) -> some View {
        let myAddr = engine.address ?? ""
        let isSent = item.fromAddr == myAddr
        let isReceived = item.toAddr == myAddr
        let isEmission = item.eventType == "EMISSION"

        let directionIcon: String = {
            if isEmission && isReceived { return "arrow.down.circle.fill" }
            if isSent { return "arrow.up.circle.fill" }
            return "arrow.down.circle.fill"
        }()

        let directionColor: Color = {
            if isEmission { return .green }
            if isSent { return .orange }
            return cyan
        }()

        let directionLabel: String = {
            if isEmission && isReceived {
                if item.emissionCount > 1 {
                    return "\u{042d}\u{043c}\u{0438}\u{0441}\u{0441}\u{0438}\u{044f} (10 \u{043c}\u{0438}\u{043d})"
                }
                return "\u{042d}\u{043c}\u{0438}\u{0441}\u{0441}\u{0438}\u{044f}"
            }
            if isSent { return "\u{041e}\u{0442}\u{043f}\u{0440}\u{0430}\u{0432}\u{043b}\u{0435}\u{043d}\u{043e}" }
            return "\u{041f}\u{043e}\u{043b}\u{0443}\u{0447}\u{0435}\u{043d}\u{043e}"
        }()

        let counterparty: String = {
            if isEmission {
                let alias = item.fromAlias.isEmpty ? "\u{0248}-0" : item.fromAlias
                if item.emissionCount > 1 {
                    return "\(alias) \u{00d7}\(item.emissionCount)"
                }
                return alias
            }
            if isSent { return displayAddr(item.toAddr, alias: item.toAlias) }
            return displayAddr(item.fromAddr, alias: item.fromAlias)
        }()

        let amountPrefix: String = {
            if isSent && !isEmission { return "-" }
            return "+"
        }()

        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: directionIcon)
                    .foregroundColor(directionColor)
                    .font(.system(size: 14))

                VStack(alignment: .leading, spacing: 2) {
                    Text(directionLabel)
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(directionColor)
                    HStack(spacing: 4) {
                        if isSent && !isEmission {
                            Image(systemName: "arrow.right")
                                .font(.system(size: 8))
                                .foregroundColor(.secondary)
                        } else if !isEmission {
                            Image(systemName: "arrow.left")
                                .font(.system(size: 8))
                                .foregroundColor(.secondary)
                        }
                        Text(counterparty)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(amountPrefix)\(formatAmount(item.amount))")
                        .font(.system(size: 13, weight: .bold, design: .monospaced))
                        .foregroundColor(directionColor)
                    Text(formatTimestamp(item.timestamp))
                        .font(.system(size: 8, design: .monospaced))
                        .foregroundColor(Color.secondary.opacity(0.6))
                }
            }
        }
        .padding(10)
        .background(cardBg)
        .cornerRadius(6)
    }

    // MARK: - Helpers

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
            df.dateFormat = "dd.MM.yyyy HH:mm"
            return df.string(from: date)
        }

        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: String(parts[0]) + "Z") {
            let df = DateFormatter()
            df.dateFormat = "dd.MM.yyyy HH:mm"
            return df.string(from: date)
        }

        return String(ts.prefix(16))
    }

    private func loadHistory() {
        guard let myAddr = engine.address, !myAddr.isEmpty else {
            errorText = "\u{041a}\u{043e}\u{0448}\u{0435}\u{043b}\u{0451}\u{043a} \u{043d}\u{0435} \u{043d}\u{0430}\u{0441}\u{0442}\u{0440}\u{043e}\u{0435}\u{043d}"
            isLoading = false
            return
        }
        let now = Date()
        guard now.timeIntervalSince(lastRefresh) >= 2.0 || lastRefresh == .distantPast else { return }
        lastRefresh = now
        isLoading = true
        errorText = ""
        Task { @MainActor in
            do {
                let events = try await engine.api.fetchMyEvents(address: myAddr, limit: 200)
                displayItems = consolidateEvents(events)
                isLoading = false
            } catch {
                errorText = "\u{041e}\u{0448}\u{0438}\u{0431}\u{043a}\u{0430} \u{0437}\u{0430}\u{0433}\u{0440}\u{0443}\u{0437}\u{043a}\u{0438}"
                isLoading = false
            }
        }
    }

    /// Consolidate EMISSION events per T2 window (600 sec), keep TRANSFER events as-is.
    /// Result: newest first, transfers always visible between consolidated emission blocks.
    private func consolidateEvents(_ events: [[String: Any]]) -> [HistoryItem] {
        let t2Window: TimeInterval = 600 // 10 minutes

        var items: [HistoryItem] = []
        var emissionBucket: (amount: Int, count: Int, fromAddr: String, toAddr: String,
                             fromAlias: String, toAlias: String, timestamp: String, date: Date)?

        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let isoFallback = ISO8601DateFormatter()
        isoFallback.formatOptions = [.withInternetDateTime]

        func parseDate(_ ts: String) -> Date? {
            isoFormatter.date(from: ts) ?? isoFallback.date(from: ts)
        }

        func flushEmission() {
            if let bucket = emissionBucket {
                items.append(HistoryItem(
                    eventType: "EMISSION",
                    amount: bucket.amount,
                    fromAddr: bucket.fromAddr,
                    toAddr: bucket.toAddr,
                    fromAlias: bucket.fromAlias,
                    toAlias: bucket.toAlias,
                    timestamp: bucket.timestamp,
                    emissionCount: bucket.count
                ))
                emissionBucket = nil
            }
        }

        // Events come newest-first from API
        for event in events {
            let eventType = event["event_type"] as? String ?? ""
            let amount = event["amount"] as? Int ?? 0
            let fromAddr = String((event["from_addr"] as? String ?? "").prefix(100))
            let toAddr = String((event["to_addr"] as? String ?? "").prefix(100))
            let fromAlias = event["from_alias"] as? String ?? ""
            let toAlias = event["to_alias"] as? String ?? ""
            let timestamp = event["timestamp_iso"] as? String ?? (event["timestamp"] as? String ?? "")

            if eventType == "EMISSION" {
                let eventDate = parseDate(timestamp) ?? Date.distantPast
                if let bucket = emissionBucket {
                    // Same T2 window? (within 600 sec of first emission in bucket)
                    if abs(bucket.date.timeIntervalSince(eventDate)) <= t2Window {
                        emissionBucket = (
                            amount: bucket.amount + amount,
                            count: bucket.count + 1,
                            fromAddr: bucket.fromAddr,
                            toAddr: bucket.toAddr,
                            fromAlias: bucket.fromAlias,
                            toAlias: bucket.toAlias,
                            timestamp: bucket.timestamp, // keep newest timestamp
                            date: bucket.date
                        )
                    } else {
                        // Different T2 window — flush previous and start new
                        flushEmission()
                        emissionBucket = (amount, 1, fromAddr, toAddr, fromAlias, toAlias, timestamp, eventDate)
                    }
                } else {
                    emissionBucket = (amount, 1, fromAddr, toAddr, fromAlias, toAlias, timestamp, eventDate)
                }
            } else {
                // TRANSFER — flush any pending emission bucket, then add transfer
                flushEmission()
                items.append(HistoryItem(
                    eventType: eventType,
                    amount: amount,
                    fromAddr: fromAddr,
                    toAddr: toAddr,
                    fromAlias: fromAlias,
                    toAlias: toAlias,
                    timestamp: timestamp,
                    emissionCount: 1
                ))
            }
        }
        flushEmission() // flush remaining

        return items // already newest-first
    }
}
