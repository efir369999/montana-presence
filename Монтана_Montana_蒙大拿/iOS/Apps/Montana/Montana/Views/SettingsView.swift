//
//  SettingsView.swift
//  Junona — Montana Messenger
//
//  Настройки приложения
//

import SwiftUI
import MontanaCore

struct SettingsView: View {
    @ObservedObject var auth = AuthService.shared
    @ObservedObject var profile = ProfileManager.shared
    @State private var defaultPrivacy: PrivacyLevel = .intimate
    @State private var showLogoutAlert = false
    @State private var aliasCopied = false
    @State private var showRecoveryPhrase = false
    @State private var showChangePin = false
    @State private var showSetupPin = false
    @State private var showCreateIdentity = false
    @State private var showRestoreIdentity = false

    var body: some View {
        NavigationStack {
            List {
                // Profile
                if auth.currentUser != nil {
                    Section {
                        HStack(spacing: 16) {
                            ZStack {
                                Circle()
                                    .fill(
                                        LinearGradient(
                                            colors: [MontanaTheme.primary, MontanaTheme.secondary],
                                            startPoint: .topLeading,
                                            endPoint: .bottomTrailing
                                        )
                                    )
                                    .frame(width: 60, height: 60)

                                Text("Ɉ")
                                    .font(.title2)
                                    .fontWeight(.bold)
                                    .foregroundColor(.white)
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text("Montana Wallet")
                                    .font(.headline)

                                let alias = profile.alias
                                if !alias.isEmpty && alias != "Ɉ-0" && alias != "Ɉ-..." {
                                    Text(alias)
                                        .font(.system(size: 16, weight: .semibold, design: .monospaced))
                                        .foregroundColor(Color(hex: "D4AF37"))
                                }
                            }

                            Spacer()
                        }
                        .padding(.vertical, 8)
                    }

                    // АЛИАС — главный идентификатор
                    if let mtId = profile.mtId {
                        Section {
                            VStack(alignment: .leading, spacing: 10) {
                                HStack {
                                    Image(systemName: "star.fill")
                                        .foregroundColor(Color(hex: "D4AF37"))
                                    Text("Алиас")
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                    Spacer()
                                }

                                HStack {
                                    Text(mtId)
                                        .font(.system(size: 24, weight: .semibold, design: .monospaced))
                                        .foregroundColor(Color(hex: "D4AF37"))

                                    Spacer()

                                    Button {
                                        UIPasteboard.general.string = mtId
                                        aliasCopied = true
                                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                            aliasCopied = false
                                        }
                                    } label: {
                                        HStack(spacing: 4) {
                                            Image(systemName: aliasCopied ? "checkmark.circle.fill" : "doc.on.doc")
                                            Text(aliasCopied ? "Скопировано" : "Копировать")
                                                .font(.caption)
                                        }
                                        .foregroundColor(aliasCopied ? MontanaTheme.success : Color(hex: "D4AF37"))
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.vertical, 4)
                        } header: {
                            Text("Кошелёк")
                        } footer: {
                            Text("Короткий адрес для переводов внутри сети Montana")
                        }
                    }

                }

                // Приватность
                Section {
                    Picker(selection: $defaultPrivacy) {
                        ForEach(PrivacyLevel.allCases) { level in
                            HStack {
                                Image(systemName: level.icon)
                                Text(level.displayName)
                            }
                            .tag(level)
                        }
                    } label: {
                        HStack {
                            Image(systemName: "lock.shield")
                                .foregroundColor(MontanaTheme.secondary)
                                .frame(width: 30)
                            Text("Уровень по умолчанию")
                        }
                    }
                } header: {
                    Text("Приватность")
                } footer: {
                    Text("Интимное — постквантовое шифрование, устойчивое к квантовым компьютерам")
                }

                // О программе
                Section {
                    HStack {
                        Text("Версия")
                        Spacer()
                        Text(Montana.version)
                            .foregroundColor(.secondary)
                    }

                    HStack {
                        Text("Криптография")
                        Spacer()
                        Text(Montana.cryptography)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    HStack {
                        Text("Genesis")
                        Spacer()
                        Text(Montana.genesisDate)
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("О Протоколе Монтана")
                }

                // Приватность и правила
                Section {
                    // Политика конфиденциальности
                    Link(destination: URL(string: "https://1394793-cy33234.tw1.ru/privacy.html")!) {
                        HStack {
                            Image(systemName: "hand.raised.fill")
                                .foregroundColor(MontanaTheme.secondary)
                                .frame(width: 30)
                            Text("Политика конфиденциальности")
                            Spacer()
                            Image(systemName: "arrow.up.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)

                    // Правила использования
                    Link(destination: URL(string: "https://1394793-cy33234.tw1.ru/terms.html")!) {
                        HStack {
                            Image(systemName: "doc.text.fill")
                                .foregroundColor(MontanaTheme.secondary)
                                .frame(width: 30)
                            Text("Условия использования")
                            Spacer()
                            Image(systemName: "arrow.up.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)

                    // GitHub
                    Link(destination: URL(string: "https://github.com/efir369999/-_Nothing_-")!) {
                        HStack {
                            Image(systemName: "chevron.left.forwardslash.chevron.right")
                                .foregroundColor(MontanaTheme.secondary)
                                .frame(width: 30)
                            Text("Исходный код")
                            Spacer()
                            Image(systemName: "arrow.up.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)
                } header: {
                    Text("Правовая информация")
                } footer: {
                    Text("Zero Collection по умолчанию. Мы не собираем данные, пока ты сам не включишь.")
                }

                // Безопасность
                Section {
                    // PIN-код: установить или сменить
                    if KeychainManager.shared.hasPin {
                        // Сменить PIN
                        Button {
                            showChangePin = true
                        } label: {
                            HStack {
                                Image(systemName: "lock.fill")
                                    .foregroundColor(MontanaTheme.success)
                                    .frame(width: 30)
                                Text("PIN-код")
                                Spacer()
                                Text("Включён")
                                    .font(.caption)
                                    .foregroundColor(MontanaTheme.success)
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .foregroundColor(.primary)
                    } else {
                        // Установить PIN
                        Button {
                            showSetupPin = true
                        } label: {
                            HStack {
                                Image(systemName: "lock.open.fill")
                                    .foregroundColor(.orange)
                                    .frame(width: 30)
                                Text("PIN-код")
                                Spacer()
                                Text("Не установлен")
                                    .font(.caption)
                                    .foregroundColor(.orange)
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .foregroundColor(.primary)
                    }

                    // Просмотр когнитивного ключа (защищён PIN)
                    Button {
                        if KeychainManager.shared.hasPin {
                            showRecoveryPhrase = true
                        } else {
                            // Сначала установить PIN
                            showSetupPin = true
                        }
                    } label: {
                        HStack {
                            Image(systemName: "eye.fill")
                                .foregroundColor(MontanaTheme.secondary)
                                .frame(width: 30)
                            Text("Когнитивный ключ")
                            Spacer()
                            if KeychainManager.shared.hasPin {
                                Image(systemName: "lock.fill")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            } else {
                                Text("Нужен PIN")
                                    .font(.caption)
                                    .foregroundColor(.orange)
                            }
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)
                } header: {
                    Text("Безопасность")
                } footer: {
                    Text("PIN-код защищает доступ к когнитивному ключу. Установите для безопасности.")
                }

                // Управление кошельками
                Section {
                    // Список кошельков
                    let walletCount = KeychainManager.shared.walletCount
                    let activeIndex = KeychainManager.shared.activeWalletIndex

                    if walletCount > 1 {
                        ForEach(0..<walletCount, id: \.self) { index in
                            Button {
                                if index != activeIndex {
                                    _ = KeychainManager.shared.switchToWallet(index)
                                    // Reload address for switched wallet
                                    if let address = KeychainManager.shared.getWalletAddress(forWallet: index) {
                                        UserDefaults.standard.set(address, forKey: "montana_address")
                                    }
                                    profile.loadProfile()
                                }
                            } label: {
                                HStack {
                                    Image(systemName: index == activeIndex ? "wallet.pass.fill" : "wallet.pass")
                                        .foregroundColor(index == activeIndex ? Color(hex: "D4AF37") : .secondary)
                                        .frame(width: 30)

                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("Кошелёк \(index + 1)")
                                            .font(.body)
                                        if let addr = KeychainManager.shared.getWalletAddress(forWallet: index) {
                                            Text(addr.prefix(12) + "...")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                    }

                                    Spacer()

                                    if index == activeIndex {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundColor(Color(hex: "D4AF37"))
                                    }
                                }
                            }
                            .foregroundColor(.primary)
                        }
                    }

                    // Добавить новый кошелёк
                    Button {
                        showCreateIdentity = true
                    } label: {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(Color(hex: "D4AF37"))
                                .frame(width: 30)
                            Text("Добавить кошелёк")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)

                    // Восстановить из когнитивного ключа
                    Button {
                        showRestoreIdentity = true
                    } label: {
                        HStack {
                            Image(systemName: "arrow.counterclockwise.circle.fill")
                                .foregroundColor(MontanaTheme.secondary)
                                .frame(width: 30)
                            Text("Импортировать кошелёк")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .foregroundColor(.primary)
                } header: {
                    Text("Кошельки")
                } footer: {
                    let count = KeychainManager.shared.walletCount
                    if count > 1 {
                        Text("У вас \(count) кошельков. Нажмите чтобы переключиться.")
                    } else {
                        Text("Добавьте ещё кошельков или импортируйте из когнитивного ключа.")
                    }
                }

                // Выход
                Section {
                    Button(role: .destructive) {
                        showLogoutAlert = true
                    } label: {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                                .frame(width: 30)
                            Text("Выйти из аккаунта")
                        }
                    }
                }
            }
            .navigationTitle("Ещё")
            .onAppear {
                profile.loadProfile()
            }
            .alert("Выйти из аккаунта?", isPresented: $showLogoutAlert) {
                Button("Отмена", role: .cancel) { }
                Button("Выйти", role: .destructive) {
                    auth.logout()
                }
            } message: {
                Text("Ключи будут удалены с устройства. Для входа понадобится повторная верификация.")
            }
            .sheet(isPresented: $showRecoveryPhrase) {
                RecoveryPhraseView()
            }
            .sheet(isPresented: $showChangePin) {
                ChangePinView()
            }
            .sheet(isPresented: $showSetupPin) {
                SetupPinFromSettingsView()
            }
            .sheet(isPresented: $showCreateIdentity) {
                CreateIdentityView {
                    // После создания обновить профиль
                    profile.loadProfile()
                }
            }
            .sheet(isPresented: $showRestoreIdentity) {
                RestoreIdentityView {
                    // После восстановления обновить профиль
                    profile.loadProfile()
                }
            }
        }
    }

    private func formatPhone(_ phone: String) -> String {
        let digits = phone.filter { $0.isNumber }
        if digits.count >= 11 {
            let code = String(digits.prefix(1))
            let area = String(digits.dropFirst().prefix(3))
            let part1 = String(digits.dropFirst(4).prefix(3))
            let part2 = String(digits.dropFirst(7).prefix(2))
            let part3 = String(digits.dropFirst(9).prefix(2))
            return "+\(code) (\(area)) \(part1)-\(part2)-\(part3)"
        }
        return phone
    }
}

#Preview {
    SettingsView()
        .preferredColorScheme(.dark)
}
