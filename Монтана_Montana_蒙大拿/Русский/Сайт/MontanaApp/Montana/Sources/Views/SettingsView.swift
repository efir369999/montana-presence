import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var showLogoutAlert = false

    var body: some View {
        NavigationView {
            List {
                // Account Section
                Section {
                    HStack(spacing: 14) {
                        Text("Ɉ")
                            .font(.title)
                            .foregroundColor(Color("Background"))
                            .frame(width: 56, height: 56)
                            .background(
                                LinearGradient(
                                    colors: [Color("Gold"), Color(hex: "FFA500")],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .clipShape(Circle())

                        VStack(alignment: .leading, spacing: 4) {
                            Text(appState.user?.phone ?? "")
                                .font(.headline)
                            Text("Номер телефона")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding(.vertical, 8)
                }
                .listRowBackground(Color("Card"))

                // Stats Section
                Section("Статистика") {
                    HStack {
                        Label("Баланс", systemImage: "creditcard")
                        Spacer()
                        Text("\(appState.balance.formatted()) Ɉ")
                            .foregroundColor(Color("Gold"))
                    }

                    HStack {
                        Label("Присутствие сегодня", systemImage: "clock")
                        Spacer()
                        Text(formatTime(appState.presenceSeconds))
                            .foregroundColor(Color("Success"))
                    }

                    HStack {
                        Label("Контактов", systemImage: "person.2")
                        Spacer()
                        Text("\(appState.contacts.count)")
                            .foregroundColor(.secondary)
                    }
                }
                .listRowBackground(Color("Card"))

                // About Section
                Section("О приложении") {
                    HStack {
                        Label("Montana Protocol", systemImage: "sun.max.fill")
                        Spacer()
                        Text("v1.0.0")
                            .foregroundColor(.secondary)
                    }

                    Link(destination: URL(string: "https://t.me/junomontanaagibot")!) {
                        HStack {
                            Label("Telegram бот", systemImage: "paperplane.fill")
                            Spacer()
                            Text("@junomontanaagibot")
                                .foregroundColor(.secondary)
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .listRowBackground(Color("Card"))

                // Logout Section
                Section {
                    Button(action: { showLogoutAlert = true }) {
                        HStack {
                            Spacer()
                            Text("Выйти")
                                .foregroundColor(.red)
                            Spacer()
                        }
                    }
                }
                .listRowBackground(Color("Card"))
            }
            .scrollContentBackground(.hidden)
            .background(Color("Background").ignoresSafeArea())
            .navigationTitle("Настройки")
            .alert("Выйти из аккаунта?", isPresented: $showLogoutAlert) {
                Button("Отмена", role: .cancel) {}
                Button("Выйти", role: .destructive) {
                    appState.logout()
                }
            }
        }
    }

    private func formatTime(_ seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        let s = seconds % 60
        return String(format: "%02d:%02d:%02d", h, m, s)
    }
}
