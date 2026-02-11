import SwiftUI

struct WalletView: View {
    @EnvironmentObject var appState: AppState
    @State private var showSendSheet = false
    @State private var showReceiveSheet = false

    var totalBalance: Int {
        appState.balance + appState.presenceSeconds
    }

    var presenceTime: String {
        let h = appState.presenceSeconds / 3600
        let m = (appState.presenceSeconds % 3600) / 60
        let s = appState.presenceSeconds % 60
        return String(format: "%02d:%02d:%02d", h, m, s)
    }

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Balance Card
                    VStack(alignment: .leading, spacing: 16) {
                        Text("БАЛАНС")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .tracking(1)

                        Text("\(totalBalance.formatted()) Ɉ")
                            .font(.system(size: 48, weight: .light))
                            .foregroundColor(Color("Gold"))

                        Divider()
                            .background(Color.white.opacity(0.1))

                        // Presence
                        HStack(spacing: 12) {
                            Circle()
                                .fill(Color("Success"))
                                .frame(width: 8, height: 8)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(presenceTime)
                                    .font(.system(.title2, design: .monospaced))
                                    .foregroundColor(Color("Success"))
                                Text("Присутствие активно")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding(24)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 24)
                            .fill(Color("Card"))
                            .overlay(
                                Text("Ɉ")
                                    .font(.system(size: 180, weight: .ultraLight))
                                    .foregroundColor(Color("Gold").opacity(0.03))
                                    .offset(x: 60, y: -30),
                                alignment: .topTrailing
                            )
                            .overlay(
                                RoundedRectangle(cornerRadius: 24)
                                    .stroke(Color("Gold").opacity(0.2), lineWidth: 1)
                            )
                    )
                    .padding(.horizontal)

                    // Action Buttons
                    HStack(spacing: 12) {
                        ActionButton(icon: "arrow.up", label: "Отправить") {
                            showSendSheet = true
                        }

                        ActionButton(icon: "arrow.down", label: "Получить") {
                            showReceiveSheet = true
                        }

                        ActionButton(icon: "sun.max.fill", label: "Юнона") {
                            // Navigate to chat
                        }
                    }
                    .padding(.horizontal)

                    // Recent Contacts
                    if !appState.contacts.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("КОНТАКТЫ")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .tracking(1)
                                .padding(.horizontal)

                            ForEach(appState.contacts.prefix(5)) { contact in
                                ContactRow(contact: contact) {
                                    // Send to contact
                                }
                            }
                        }
                        .padding(.top)
                    }

                    Spacer(minLength: 100)
                }
                .padding(.top)
            }
            .background(Color("Background").ignoresSafeArea())
            .navigationTitle("Кошелёк")
            .sheet(isPresented: $showSendSheet) {
                SendView()
            }
            .sheet(isPresented: $showReceiveSheet) {
                ReceiveView()
            }
        }
    }
}

// MARK: - Action Button
struct ActionButton: View {
    let icon: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(label)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .background(Color("Card"))
            .cornerRadius(16)
        }
        .foregroundColor(.white)
    }
}

// MARK: - Contact Row
struct ContactRow: View {
    let contact: Contact
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 14) {
                // Avatar
                Text(String(contact.name.prefix(1)).uppercased())
                    .font(.headline)
                    .foregroundColor(Color("Background"))
                    .frame(width: 48, height: 48)
                    .background(
                        LinearGradient(
                            colors: [Color("Gold"), Color(hex: "FFA500")],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(contact.name)
                        .font(.body)
                        .foregroundColor(.white)
                    Text(contact.phone)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
    }
}

// MARK: - Send View
struct SendView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss
    @State private var phone = ""
    @State private var amount = ""
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Text("Ɉ")
                    .font(.system(size: 64, weight: .thin))
                    .foregroundColor(Color("Gold"))
                    .padding(.top, 20)

                VStack(spacing: 12) {
                    TextField("Номер телефона", text: $phone)
                        .keyboardType(.phonePad)
                        .textFieldStyle(MontanaTextFieldStyle())

                    TextField("Сумма", text: $amount)
                        .keyboardType(.numberPad)
                        .textFieldStyle(MontanaTextFieldStyle())
                }
                .padding(.horizontal)

                if let error = error {
                    Text(error)
                        .foregroundColor(.red)
                        .font(.caption)
                }

                Button(action: sendTransfer) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: Color("Background")))
                    } else {
                        Text("Отправить")
                            .fontWeight(.semibold)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color("Gold"))
                .foregroundColor(Color("Background"))
                .cornerRadius(12)
                .padding(.horizontal)
                .disabled(isLoading)

                Spacer()
            }
            .background(Color("Background").ignoresSafeArea())
            .navigationTitle("Отправить Ɉ")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Отмена") { dismiss() }
                }
            }
        }
    }

    private func sendTransfer() {
        guard let deviceId = UserDefaults.standard.string(forKey: "deviceId"),
              let amountInt = Int(amount), amountInt > 0 else {
            error = "Введите корректную сумму"
            return
        }

        isLoading = true
        error = nil

        API.shared.transfer(deviceId: deviceId, to: phone, amount: amountInt) { result in
            DispatchQueue.main.async {
                isLoading = false
                switch result {
                case .success(let response):
                    if response.success {
                        appState.balance = response.newBalance ?? appState.balance
                        dismiss()
                    } else {
                        error = response.error ?? "Ошибка перевода"
                    }
                case .failure:
                    error = "Ошибка сети"
                }
            }
        }
    }
}

// MARK: - Receive View
struct ReceiveView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationView {
            VStack(spacing: 24) {
                Text("Ɉ")
                    .font(.system(size: 80, weight: .thin))
                    .foregroundColor(Color("Gold"))
                    .padding(.top, 40)

                Text(appState.user?.phone ?? "")
                    .font(.title)
                    .fontWeight(.semibold)
                    .foregroundColor(Color("Gold"))

                Text("Отправьте Ɉ на этот номер")
                    .foregroundColor(.secondary)

                Button(action: copyPhone) {
                    HStack {
                        Image(systemName: "doc.on.doc")
                        Text("Скопировать номер")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color("Gold"))
                    .foregroundColor(Color("Background"))
                    .cornerRadius(12)
                }
                .padding(.horizontal)

                Spacer()
            }
            .background(Color("Background").ignoresSafeArea())
            .navigationTitle("Получить Ɉ")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Закрыть") { dismiss() }
                }
            }
        }
    }

    private func copyPhone() {
        if let phone = appState.user?.phone {
            UIPasteboard.general.string = phone
        }
    }
}

// MARK: - Text Field Style
struct MontanaTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .padding()
            .background(Color.white.opacity(0.1))
            .cornerRadius(12)
            .foregroundColor(.white)
    }
}
