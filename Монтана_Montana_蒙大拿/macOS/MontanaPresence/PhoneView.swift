import SwiftUI

/// Montana Phone Service
/// Виртуальные номера + привязка реальных номеров
struct PhoneView: View {
    @EnvironmentObject var engine: PresenceEngine
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            Divider()

            // Tab selector
            Picker("", selection: $selectedTab) {
                Text("Виртуальные").tag(0)
                Text("Реальные").tag(1)
            }
            .pickerStyle(.segmented)
            .padding()

            // Content
            TabView(selection: $selectedTab) {
                VirtualPhoneView()
                    .tag(0)

                RealPhoneView()
                    .tag(1)
            }
            .tabViewStyle(.automatic)
        }
        .background(Color(NSColor.windowBackgroundColor))
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 12) {
            // Phone icon
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
                    Text("📞")
                        .font(.system(size: 20))
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Телефонные номера")
                    .font(.headline)
                Text("Виртуальные и реальные номера Montana")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()
        }
        .padding()
    }
}

// MARK: - Virtual Phone View

struct VirtualPhoneView: View {
    @State private var currentPrice = 1
    @State private var isLoading = false
    @State private var statusMessage = ""
    @State private var ownedNumbers: [OwnedNumber] = []

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Registration card
                registrationCard

                // Owned numbers
                if !ownedNumbers.isEmpty {
                    ownedNumbersSection
                }

                // Info section
                infoSection
            }
            .padding()
        }
        .onAppear {
            loadCurrentPrice()
            loadOwnedNumbers()
        }
    }

    private var registrationCard: some View {
        VStack(spacing: 16) {
            Text("Купить виртуальный номер")
                .font(.title3)
                .fontWeight(.semibold)

            Text("+montana-\(String(format: "%06d", currentPrice))")
                .font(.system(size: 24, design: .monospaced))
                .fontWeight(.bold)
                .foregroundColor(Color(red: 0.0, green: 0.83, blue: 1.0))

            Text("Цена: \(currentPrice) Ɉ")
                .font(.title2)
                .fontWeight(.semibold)

            if !statusMessage.isEmpty {
                Text(statusMessage)
                    .font(.caption)
                    .foregroundColor(statusMessage.hasPrefix("✓") ? .green : .red)
            }

            Button(action: registerNumber) {
                HStack {
                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.8)
                            .padding(.trailing, 4)
                    }
                    Text("Купить за \(currentPrice) Ɉ")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(isLoading ? Color.gray : Color(red: 0.0, green: 0.83, blue: 1.0))
                .foregroundColor(.white)
                .cornerRadius(8)
            }
            .buttonStyle(.plain)
            .disabled(isLoading)
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
    }

    private var ownedNumbersSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Мои номера")
                .font(.title3)
                .fontWeight(.semibold)

            ForEach(ownedNumbers) { number in
                HStack {
                    Text(number.formatted)
                        .font(.system(.body, design: .monospaced))

                    Spacer()

                    Text("\(number.pricePaid) Ɉ")
                        .foregroundColor(.secondary)
                        .font(.caption)
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
            }
        }
    }

    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("💡 Виртуальные номера")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(alignment: .leading, spacing: 8) {
                InfoRow(icon: "1️⃣", text: "1-й номер: 1 Ɉ")
                InfoRow(icon: "🔢", text: "N-й номер: N Ɉ")
                InfoRow(icon: "📞", text: "Формат: +montana-000042")
                InfoRow(icon: "💰", text: "Звонки: 1 Ɉ/сек для владельцев")
            }
        }
        .padding()
        .background(Color.green.opacity(0.05))
        .cornerRadius(12)
    }

    private func loadCurrentPrice() {
        currentPrice = 1
    }

    private func loadOwnedNumbers() {
        ownedNumbers = []
    }

    private func registerNumber() {
        isLoading = true
        statusMessage = ""

        Task {
            do {
                try await Task.sleep(nanoseconds: 1_000_000_000)

                await MainActor.run {
                    let formatted = "+montana-\(String(format: "%06d", currentPrice))"
                    statusMessage = "✓ Номер \(formatted) зарегистрирован!"
                    ownedNumbers.append(OwnedNumber(number: currentPrice, formatted: formatted, pricePaid: currentPrice))
                    currentPrice += 1
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    statusMessage = "❌ Не удалось зарегистрировать номер"
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - Real Phone View

struct RealPhoneView: View {
    @State private var phoneInput = ""
    @State private var codeInput = ""
    @State private var isVerificationSent = false
    @State private var isLoading = false
    @State private var statusMessage = ""
    @State private var boundPhones: [BoundPhone] = []

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Binding card
                bindingCard

                // Bound phones
                if !boundPhones.isEmpty {
                    boundPhonesSection
                }

                // Info section
                infoSection
            }
            .padding()
        }
        .onAppear {
            loadBoundPhones()
        }
    }

    private var bindingCard: some View {
        VStack(spacing: 16) {
            Text("Привязать реальный номер")
                .font(.title3)
                .fontWeight(.semibold)

            if !isVerificationSent {
                // Step 1: Enter phone number
                VStack(spacing: 12) {
                    TextField("+7-921-123-4567", text: $phoneInput)
                        .textFieldStyle(.plain)
                        .font(.system(size: 16, design: .monospaced))
                        .padding(10)
                        .background(Color(NSColor.controlBackgroundColor))
                        .cornerRadius(8)
                        .disabled(isLoading)

                    Button(action: requestVerification) {
                        HStack {
                            if isLoading {
                                ProgressView()
                                    .scaleEffect(0.8)
                                    .padding(.trailing, 4)
                            }
                            Text("Отправить код")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(phoneInput.isEmpty || isLoading ? Color.gray : Color(red: 0.0, green: 0.83, blue: 1.0))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                    .disabled(phoneInput.isEmpty || isLoading)
                }
            } else {
                // Step 2: Enter verification code
                VStack(spacing: 12) {
                    Text("Код отправлен на \(phoneInput)")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    TextField("000000", text: $codeInput)
                        .textFieldStyle(.plain)
                        .font(.system(size: 20, design: .monospaced))
                        .padding(10)
                        .background(Color(NSColor.controlBackgroundColor))
                        .cornerRadius(8)
                        .disabled(isLoading)

                    Button(action: verifyCode) {
                        HStack {
                            if isLoading {
                                ProgressView()
                                    .scaleEffect(0.8)
                                    .padding(.trailing, 4)
                            }
                            Text("Подтвердить")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(codeInput.count != 6 || isLoading ? Color.gray : Color(red: 0.0, green: 0.83, blue: 1.0))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                    .disabled(codeInput.count != 6 || isLoading)

                    Button("Отменить") {
                        isVerificationSent = false
                        codeInput = ""
                        statusMessage = ""
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.secondary)
                }
            }

            if !statusMessage.isEmpty {
                Text(statusMessage)
                    .font(.caption)
                    .foregroundColor(statusMessage.hasPrefix("✓") ? .green : .red)
            }
        }
        .padding()
        .background(Color.purple.opacity(0.05))
        .cornerRadius(12)
    }

    private var boundPhonesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Привязанные номера")
                .font(.title3)
                .fontWeight(.semibold)

            ForEach(boundPhones) { phone in
                HStack {
                    Text(phone.number)
                        .font(.system(.body, design: .monospaced))

                    Spacer()

                    Text("✓ Проверен")
                        .foregroundColor(.green)
                        .font(.caption)
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
            }
        }
    }

    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("💡 Реальные номера")
                .font(.title3)
                .fontWeight(.semibold)

            VStack(alignment: .leading, spacing: 8) {
                InfoRow(icon: "📱", text: "Привяжи свой реальный номер")
                InfoRow(icon: "💬", text: "SMS верификация")
                InfoRow(icon: "🔐", text: "Номер = кошелек Montana")
                InfoRow(icon: "📞", text: "Звонки по 1 Ɉ/сек")
            }
        }
        .padding()
        .background(Color.purple.opacity(0.05))
        .cornerRadius(12)
    }

    private func loadBoundPhones() {
        boundPhones = []
    }

    private func requestVerification() {
        isLoading = true
        statusMessage = ""

        Task {
            do {
                try await Task.sleep(nanoseconds: 1_000_000_000)

                await MainActor.run {
                    isVerificationSent = true
                    statusMessage = "✓ Код отправлен на \(phoneInput)"
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    statusMessage = "❌ Не удалось отправить код"
                    isLoading = false
                }
            }
        }
    }

    private func verifyCode() {
        isLoading = true
        statusMessage = ""

        Task {
            do {
                try await Task.sleep(nanoseconds: 1_000_000_000)

                await MainActor.run {
                    statusMessage = "✓ Номер \(phoneInput) успешно привязан!"
                    boundPhones.append(BoundPhone(number: phoneInput))
                    phoneInput = ""
                    codeInput = ""
                    isVerificationSent = false
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    statusMessage = "❌ Неверный код"
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - Models

struct OwnedNumber: Identifiable {
    let id = UUID()
    let number: Int
    let formatted: String
    let pricePaid: Int
}

struct BoundPhone: Identifiable {
    let id = UUID()
    let number: String
}

private struct InfoRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 8) {
            Text(icon)
                .font(.body)
            Text(text)
                .font(.callout)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Preview

#Preview {
    PhoneView()
        .environmentObject(PresenceEngine.shared)
        .frame(width: 600, height: 500)
}
