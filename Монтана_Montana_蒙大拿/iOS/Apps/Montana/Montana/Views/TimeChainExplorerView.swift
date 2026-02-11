//
//  TimeChainExplorerView.swift
//  Montana — TimeChain Explorer
//
//  Просмотр блоков TimeChain v3.1-PQ-NTS
//  Атомные метки времени с NTS синхронизацией
//

import SwiftUI

// MARK: - TimeChain Block Model

struct TimeChainBlock: Identifiable, Codable {
    let id: Int
    let timestamp: String
    let address: String
    let seconds: Int
    let prevHash: String
    let blockHash: String
    let nodePubkey: String?
    let signature: String?
    let ntsVerified: Bool?
    let ntsEncrypted: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        case timestamp
        case address
        case seconds
        case prevHash = "prev_hash"
        case blockHash = "block_hash"
        case nodePubkey = "node_pubkey"
        case signature
        case ntsVerified = "nts_verified"
        case ntsEncrypted = "nts_encrypted"
    }

    var shortHash: String {
        String(blockHash.prefix(8)) + "..." + String(blockHash.suffix(6))
    }

    var shortAddress: String {
        guard address.count > 12 else { return address }
        return String(address.prefix(8)) + "..." + String(address.suffix(4))
    }

    var formattedTime: String {
        // Parse ISO 8601 with nanoseconds: 2026-01-30T14:31:11.123456789Z
        let parts = timestamp.split(separator: "T")
        guard parts.count == 2 else { return timestamp }

        let datePart = parts[0]
        let timePart = parts[1].dropLast() // Remove Z
        let timeComponents = timePart.split(separator: ".")
        let time = timeComponents.first ?? ""

        return "\(datePart) \(time)"
    }

    var postQuantum: Bool {
        signature != nil && !signature!.isEmpty
    }
}

// MARK: - TimeChain Stats Model

struct TimeChainStats: Codable {
    let version: String
    let totalBlocks: Int
    let signedBlocks: Int
    let uniqueAddresses: Int
    let registeredAliases: Int
    let lastMtNumber: Int
    let mlDsa65: Bool
    let ntsModule: Bool
    let ntsSynchronized: Bool?
    let ntsEncrypted: Bool?
    let poolSize: Int?

    enum CodingKeys: String, CodingKey {
        case version
        case totalBlocks = "total_blocks"
        case signedBlocks = "signed_blocks"
        case uniqueAddresses = "unique_addresses"
        case registeredAliases = "registered_aliases"
        case lastMtNumber = "last_mt_number"
        case mlDsa65 = "ml_dsa_65"
        case ntsModule = "nts_module"
        case ntsSynchronized = "nts_synchronized"
        case ntsEncrypted = "nts_encrypted"
        case poolSize = "pool_size"
    }
}

// MARK: - TimeChain Service

@MainActor
class TimeChainService: ObservableObject {
    static let shared = TimeChainService()

    @Published var stats: TimeChainStats?
    @Published var blocks: [TimeChainBlock] = []
    @Published var isLoading = false
    @Published var error: String?

    private let baseURL = "https://1394793-cy33234.tw1.ru"

    func loadStats() async {
        isLoading = true
        error = nil

        guard let url = URL(string: "\(baseURL)/api/timechain/stats") else {
            error = "Invalid URL"
            isLoading = false
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                error = "Server error"
                isLoading = false
                return
            }

            let decoder = JSONDecoder()
            stats = try decoder.decode(TimeChainStats.self, from: data)
        } catch {
            self.error = "Failed to load stats"
            print("[TimeChain] Stats error: \(error)")
        }

        isLoading = false
    }

    func loadBlocks(address: String? = nil, limit: Int = 50) async {
        isLoading = true
        error = nil

        var urlString = "\(baseURL)/api/timechain/blocks?limit=\(limit)"
        if let addr = address {
            urlString += "&address=\(addr)"
        }

        guard let url = URL(string: urlString) else {
            error = "Invalid URL"
            isLoading = false
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                error = "Server error"
                isLoading = false
                return
            }

            let decoder = JSONDecoder()
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let blocksArray = json["blocks"] as? [[String: Any]] {
                let blocksData = try JSONSerialization.data(withJSONObject: blocksArray)
                blocks = try decoder.decode([TimeChainBlock].self, from: blocksData)
            }
        } catch {
            self.error = "Failed to load blocks"
            print("[TimeChain] Blocks error: \(error)")
        }

        isLoading = false
    }
}

// MARK: - TimeChain Explorer View

struct TimeChainExplorerView: View {
    @StateObject private var service = TimeChainService.shared
    @State private var searchAddress = ""
    @State private var showStats = true

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // Stats Card
                        if showStats, let stats = service.stats {
                            StatsCard(stats: stats)
                        }

                        // Search
                        SearchBar(text: $searchAddress, onSearch: {
                            Task {
                                if searchAddress.isEmpty {
                                    await service.loadBlocks()
                                } else {
                                    await service.loadBlocks(address: searchAddress)
                                }
                            }
                        })

                        // Loading
                        if service.isLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: Color(hex: "10B981")))
                                .padding()
                        }

                        // Error
                        if let error = service.error {
                            Text(error)
                                .foregroundColor(.red)
                                .font(.caption)
                                .padding()
                        }

                        // Blocks List
                        LazyVStack(spacing: 12) {
                            ForEach(service.blocks) { block in
                                BlockCard(block: block)
                            }
                        }
                        .padding(.horizontal)
                    }
                    .padding(.vertical)
                }
            }
            .navigationTitle("TimeChain")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        Task {
                            await service.loadStats()
                            await service.loadBlocks()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(Color(hex: "10B981"))
                    }
                }
            }
            .task {
                await service.loadStats()
                await service.loadBlocks()
            }
        }
    }
}

// MARK: - Stats Card

struct StatsCard: View {
    let stats: TimeChainStats

    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("TimeChain")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)

                    Text("v\(stats.version)")
                        .font(.caption)
                        .foregroundColor(Color(hex: "10B981"))
                }

                Spacer()

                // Status badges
                HStack(spacing: 8) {
                    if stats.mlDsa65 {
                        StatusBadge(text: "ML-DSA-65", color: Color(hex: "10B981"))
                    }
                    if stats.ntsModule {
                        StatusBadge(text: "NTS", color: Color(hex: "D4AF37"))
                    }
                }
            }

            Divider()
                .background(Color.white.opacity(0.1))

            // Stats Grid
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 16) {
                StatItem(value: "\(stats.totalBlocks)", label: "Блоков")
                StatItem(value: "\(stats.signedBlocks)", label: "Подписано")
                StatItem(value: "\(stats.uniqueAddresses)", label: "Адресов")
                StatItem(value: "\(stats.registeredAliases)", label: "Алиасов")
                StatItem(value: "Ɉ-\(stats.lastMtNumber)", label: "Последний")
                if let poolSize = stats.poolSize {
                    StatItem(value: "\(poolSize)", label: "Pool Size")
                }
            }

            // NTS Status
            if let ntsSynced = stats.ntsSynchronized {
                HStack {
                    Circle()
                        .fill(ntsSynced ? Color(hex: "10B981") : Color.orange)
                        .frame(width: 8, height: 8)

                    Text(ntsSynced ? "NTS Синхронизировано" : "NTS Синхронизация...")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))

                    if stats.ntsEncrypted == true {
                        Text("• TLS 1.3")
                            .font(.caption)
                            .foregroundColor(Color(hex: "D4AF37"))
                    }

                    Spacer()
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.white.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color(hex: "10B981").opacity(0.3), lineWidth: 1)
                )
        )
        .padding(.horizontal)
    }
}

// MARK: - Status Badge

struct StatusBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .semibold))
            .foregroundColor(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Capsule()
                    .fill(color.opacity(0.2))
            )
    }
}

// MARK: - Stat Item

struct StatItem: View {
    let value: String
    let label: String

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 18, weight: .semibold, design: .monospaced))
                .foregroundColor(.white)

            Text(label)
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
    }
}

// MARK: - Search Bar

struct SearchBar: View {
    @Binding var text: String
    let onSearch: () -> Void

    var body: some View {
        HStack {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.white.opacity(0.5))

            TextField("Поиск по адресу (mt...)", text: $text)
                .foregroundColor(.white)
                .autocapitalization(.none)
                .autocorrectionDisabled()
                .onSubmit {
                    onSearch()
                }

            if !text.isEmpty {
                Button {
                    text = ""
                    onSearch()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.white.opacity(0.5))
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.white.opacity(0.08))
        )
        .padding(.horizontal)
    }
}

// MARK: - Block Card

struct BlockCard: View {
    let block: TimeChainBlock
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                // Block ID
                Text("#\(block.id)")
                    .font(.system(size: 14, weight: .bold, design: .monospaced))
                    .foregroundColor(Color(hex: "10B981"))

                Spacer()

                // Timestamp
                Text(block.formattedTime)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))

                // PQ Badge
                if block.postQuantum {
                    Image(systemName: "checkmark.shield.fill")
                        .foregroundColor(Color(hex: "10B981"))
                        .font(.caption)
                }

                // NTS Badge
                if block.ntsVerified == true {
                    Image(systemName: "clock.badge.checkmark.fill")
                        .foregroundColor(Color(hex: "D4AF37"))
                        .font(.caption)
                }
            }

            // Address & Seconds
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Адрес")
                        .font(.system(size: 10))
                        .foregroundColor(.white.opacity(0.4))

                    Text(block.shortAddress)
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text("Секунды")
                        .font(.system(size: 10))
                        .foregroundColor(.white.opacity(0.4))

                    Text("+\(block.seconds) Ɉ")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(Color(hex: "10B981"))
                }
            }

            // Hash (expandable)
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    expanded.toggle()
                }
            } label: {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Block Hash")
                        .font(.system(size: 10))
                        .foregroundColor(.white.opacity(0.4))

                    Text(expanded ? block.blockHash : block.shortHash)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundColor(Color(hex: "D4AF37"))
                        .lineLimit(expanded ? nil : 1)
                }
            }
            .buttonStyle(.plain)

            // Expanded details
            if expanded {
                VStack(alignment: .leading, spacing: 8) {
                    Divider()
                        .background(Color.white.opacity(0.1))

                    // Previous Hash
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Previous Hash")
                            .font(.system(size: 10))
                            .foregroundColor(.white.opacity(0.4))

                        Text(block.prevHash)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(.white.opacity(0.6))
                    }

                    // Full timestamp
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Full Timestamp (nanoseconds)")
                            .font(.system(size: 10))
                            .foregroundColor(.white.opacity(0.4))

                        Text(block.timestamp)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(.white.opacity(0.6))
                    }

                    // Signature status
                    if let sig = block.signature, !sig.isEmpty {
                        HStack {
                            Image(systemName: "signature")
                                .foregroundColor(Color(hex: "10B981"))
                            Text("ML-DSA-65 Подпись")
                                .font(.caption)
                                .foregroundColor(Color(hex: "10B981"))
                        }
                    }
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.white.opacity(0.05))
        )
    }
}

// MARK: - Preview

#Preview {
    TimeChainExplorerView()
        .preferredColorScheme(.dark)
}
