import SwiftUI

/// Montana Calls — Audio & Video
/// Управление звонками (1 Ɉ/сек для владельцев номеров)
struct CallsView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var recipientInput = ""
    @State private var callType: CallType = .audio
    @State private var callHistory: [CallRecord] = []

    enum CallType: String, CaseIterable {
        case audio = "Аудио"
        case video = "Видео"
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            Divider()

            // Main content
            ScrollView {
                VStack(spacing: 24) {
                    // Call interface
                    callCard

                    // Pricing info
                    pricingCard

                    // Call history
                    if !callHistory.isEmpty {
                        historySection
                    }
                }
                .padding()
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear {
            loadCallHistory()
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            // Call icon
            Circle()
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.0, green: 0.83, blue: 1.0),   // #00d4ff cyan
                            Color(red: 0.48, green: 0.18, blue: 1.0)   // #7b2fff purple
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 40, height: 40)
                .overlay(
                    Image(systemName: "phone.fill")
                        .font(.system(size: 18))
                        .foregroundColor(.white)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Звонки Montana")
                    .font(.headline)
                Text("Аудио и видео звонки")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()
        }
        .padding()
    }

    // MARK: - Call Card

    private var callCard: some View {
        VStack(spacing: 16) {
            Text("Совершить звонок")
                .font(.title3)
                .fontWeight(.semibold)

            // Recipient input
            HStack(spacing: 8) {
                TextField("alice@montana.network", text: $recipientInput)
                    .textFieldStyle(.plain)
                    .font(.system(size: 16))
                    .padding(10)
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(8)

                Text("или")
                    .foregroundColor(.secondary)
                    .font(.caption)

                TextField("+montana-000042", text: $recipientInput)
                    .textFieldStyle(.plain)
                    .font(.system(size: 16, design: .monospaced))
                    .padding(10)
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(8)
            }

            // Call type picker
            Picker("Тип звонка", selection: $callType) {
                ForEach(CallType.allCases, id: \.self) { type in
                    HStack {
                        Image(systemName: type == .audio ? "mic.fill" : "video.fill")
                        Text(type.rawValue)
                    }
                    .tag(type)
                }
            }
            .pickerStyle(.segmented)

            // Call button
            Button(action: initiateCall) {
                HStack(spacing: 8) {
                    Image(systemName: callType == .audio ? "phone.fill" : "video.fill")
                    Text("Позвонить")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(recipientInput.isEmpty ? Color.gray : Color.green)
                .foregroundColor(.white)
                .cornerRadius(8)
            }
            .buttonStyle(.plain)
            .disabled(recipientInput.isEmpty)
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Pricing Card

    private var pricingCard: some View {
        VStack(spacing: 16) {
            Text("💰 Стоимость звонков")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(spacing: 12) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Аудио звонки")
                            .font(.headline)
                        Text("Голосовая связь")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    HStack(spacing: 4) {
                        Text("1")
                            .font(.title2)
                            .fontWeight(.bold)
                        Text("Ɉ/сек")
                            .font(.title3)
                    }
                    .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)

                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Видео звонки")
                            .font(.headline)
                        Text("Видеосвязь HD")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    HStack(spacing: 4) {
                        Text("1")
                            .font(.title2)
                            .fontWeight(.bold)
                        Text("Ɉ/сек")
                            .font(.title3)
                    }
                    .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
            }

            Text("⚠️ Для звонков нужен Montana номер")
                .font(.caption)
                .foregroundColor(.orange)
        }
        .padding()
        .background(Color.green.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - History Section

    private var historySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("История звонков")
                .font(.title3)
                .fontWeight(.semibold)

            ForEach(callHistory) { record in
                HStack {
                    Image(systemName: record.type == .audio ? "phone.fill" : "video.fill")
                        .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))

                    VStack(alignment: .leading, spacing: 2) {
                        Text(record.recipient)
                            .font(.system(.body, design: .monospaced))
                        Text(record.timestamp, style: .relative)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: 2) {
                        Text(formatDuration(record.duration))
                            .font(.caption)
                        Text("\(record.cost) Ɉ")
                            .font(.caption)
                            .fontWeight(.semibold)
                    }
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
            }
        }
    }

    // MARK: - Actions

    private func loadCallHistory() {
        // TODO: Load from API
        callHistory = []
    }

    private func initiateCall() {
        // TODO: WebRTC implementation
        let cost = 0 // Will be calculated based on duration
        let record = CallRecord(
            recipient: recipientInput,
            type: callType,
            duration: 0,
            cost: cost,
            timestamp: Date()
        )
        callHistory.insert(record, at: 0)
    }

    private func formatDuration(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let secs = seconds % 60
        return String(format: "%d:%02d", minutes, secs)
    }
}

// MARK: - Models

struct CallRecord: Identifiable {
    let id = UUID()
    let recipient: String
    let type: CallsView.CallType
    let duration: Int  // seconds
    let cost: Int      // Ɉ
    let timestamp: Date
}

// MARK: - Preview

#Preview {
    CallsView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
