//
//  MontanaApp.swift
//  Montana — Кошелёк времени
//
//  Постквантовый протокол идеальных денег
//  Bundle ID: network.montana.junona
//

import SwiftUI
import MontanaCore

@main
struct MontanaApp: App {
    @StateObject private var auth = AuthService.shared
    @StateObject private var wallet = WalletService.shared
    @StateObject private var biometricAuth = BiometricAuth.shared
    @Environment(\.scenePhase) var scenePhase

    init() {
        Montana.initialize()

        // ОДНОРАЗОВАЯ МИГРАЦИЯ v1.9.3: очистка старых данных
        // Keychain сохраняется после удаления приложения - нужно очистить
        let migrationKey = "montana_migration_v1_9_3_done"
        if !UserDefaults.standard.bool(forKey: migrationKey) {
            print("[Montana] Migration v1.9.3: clearing old data")

            // Очистить keychain
            let keychainKeys = ["private_key", "public_key", "cognitive_key", "pin_code", "pin_hash"]
            for key in keychainKeys {
                let query: [String: Any] = [
                    kSecClass as String: kSecClassGenericPassword,
                    kSecAttrService as String: "network.montana.junona",
                    kSecAttrAccount as String: key
                ]
                SecItemDelete(query as CFDictionary)
            }

            // Очистить UserDefaults
            let userDefaultsKeys = [
                "montana_address", "montana_mt_number", "montana_mt_id",
                "montana_balance", "montana_user", "montana_logged_out",
                "montana_last_reported_balance"
            ]
            for key in userDefaultsKeys {
                UserDefaults.standard.removeObject(forKey: key)
            }

            // Пометить миграцию как выполненную
            UserDefaults.standard.set(true, forKey: migrationKey)
            print("[Montana] Migration complete - app is fresh")
        }
    }

    var body: some Scene {
        WindowGroup {
            ZStack {
                Group {
                    if auth.state.isAuthorized {
                        WalletView()
                    } else {
                        // ТОЛЬКО когнитивный ключ — никаких Telegram/Google
                        CognitiveKeyView()
                    }
                }

                // Face ID блокировка при возврате из фона
                if biometricAuth.isLocked && auth.state.isAuthorized {
                    LockScreenView()
                        .transition(.opacity)
                }
            }
            .animation(.easeInOut(duration: 0.2), value: biometricAuth.isLocked)
            .preferredColorScheme(.dark)
            .onOpenURL { url in
                handleDeepLink(url)
            }
            .onChange(of: scenePhase) { _, newPhase in
                if newPhase == .background {
                    biometricAuth.lock()
                }
            }
        }
    }

    private func handleDeepLink(_ url: URL) {
        print("[Montana] Deep link: \(url.absoluteString)")

        guard url.scheme == "montana" else { return }

        // Формат: montana://path?param=value
        // Только когнитивный ключ — никаких внешних OAuth
        if let components = URLComponents(url: url, resolvingAgainstBaseURL: false) {
            // montana://wallet - открыть кошелёк
            if components.host == "wallet" {
                print("[Montana] Open wallet request")
                return
            }

            // montana://transfer?to=mtXXX&amount=100
            if components.host == "transfer",
               let queryItems = components.queryItems {
                let toAddress = queryItems.first(where: { $0.name == "to" })?.value
                let amount = queryItems.first(where: { $0.name == "amount" })?.value
                print("[Montana] Transfer request: to=\(toAddress ?? ""), amount=\(amount ?? "")")
                // TODO: Handle transfer deep link
                return
            }
        }
    }

}

// MARK: - Profile Manager
//
// Montana Native Auth — когнитивный ключ + ML-DSA-65
// MT ID: Ɉ-1, Ɉ-2, Ɉ-3... — порядковый номер регистрации

@MainActor
class ProfileManager: ObservableObject {
    static let shared = ProfileManager()

    @Published var isFrozen = false
    @Published var profileId: String?
    @Published var mtNumber: Int?  // Порядковый номер, присвоенный СЕТЬЮ

    // ═══════════════════════════════════════════════════════════════
    // АДРЕС MONTANA: Ɉ-{номер}-{криптохеш}
    // Пример: Ɉ-1-26035a7cd7d04d4702b9dee85497cc95da8c1867
    // Адрес хранится как ЕДИНАЯ строка в UserDefaults
    // ═══════════════════════════════════════════════════════════════

    // ПОЛНЫЙ АДРЕС — читается из UserDefaults напрямую
    var fullAddress: String {
        UserDefaults.standard.string(forKey: "montana_address") ?? "Ɉ-0-"
    }

    // АЛИАС: короткая форма (Ɉ-1)
    // ПРИОРИТЕТ: mtNumber > saved number > address parsing
    var alias: String {
        // 1. Сначала проверяем mtNumber (в памяти)
        if let number = mtNumber, number > 0 {
            return "Ɉ-\(number)"
        }

        // 2. Потом saved number (из UserDefaults)
        let saved = UserDefaults.standard.integer(forKey: "montana_mt_number")
        if saved > 0 {
            return "Ɉ-\(saved)"
        }

        // 3. Пробуем извлечь из адреса формата Ɉ-{N}-{hash}
        let addr = fullAddress
        if addr.hasPrefix("Ɉ-") {
            let parts = addr.dropFirst(2).split(separator: "-", maxSplits: 1)
            if let first = parts.first, let number = Int(first), number > 0 {
                return "Ɉ-\(number)"
            }
        }

        // 4. Нет номера — ждём регистрацию
        return "Ɉ-..."
    }

    var mtId: String? {
        get { alias != "Ɉ-..." ? alias : nil }
        set { /* ignore */ }
    }

    var mtIdDisplay: String { alias }

    // Извлечь номер из адреса
    private var sequentialNumber: Int {
        if let number = mtNumber, number > 0 { return number }
        let saved = UserDefaults.standard.integer(forKey: "montana_mt_number")
        return saved > 0 ? saved : 0
    }

    // Уникальный ID устройства
    var deviceId: String {
        if let existing = UserDefaults.standard.string(forKey: "montana_device_uuid") {
            return existing
        }
        let newId = UUID().uuidString
        UserDefaults.standard.set(newId, forKey: "montana_device_uuid")
        return newId
    }

    // 3 узла + сайт (проверены через SSH)
    // IP адреса используют HTTP (нет SSL), сайт использует HTTPS
    private let endpoints = [
        "https://1394793-cy33234.tw1.ru",    // Сайт Timeweb (primary, HTTPS)
        "http://176.124.208.93",              // Москва (HTTP)
        "http://72.56.102.240",               // Амстердам (HTTP)
        "http://91.200.148.93"                // Алматы (HTTP)
    ]

    private init() {}

    func loadProfile() {
        if UserDefaults.standard.bool(forKey: "montana_logged_out") {
            print("[ProfileManager] User logged out, skipping auto-restore")
            return
        }
        loadLocal()

        // Если есть адрес, но нет номера — регистрируем в сети
        if sequentialNumber == 0,
           let address = UserDefaults.standard.string(forKey: "montana_address"),
           !address.isEmpty {
            Task {
                await registerInNetwork()
            }
        }
    }

    func clearLogoutFlag() {
        UserDefaults.standard.removeObject(forKey: "montana_logged_out")
    }

    private func saveLocal() {
        if let id = mtId {
            UserDefaults.standard.set(id, forKey: "montana_mt_id")
        }
        if let number = mtNumber {
            UserDefaults.standard.set(number, forKey: "montana_mt_number")
        }
    }

    func loadLocal() {
        mtId = UserDefaults.standard.string(forKey: "montana_mt_id")
        let savedNumber = UserDefaults.standard.integer(forKey: "montana_mt_number")
        if savedNumber > 0 || UserDefaults.standard.object(forKey: "montana_mt_number") != nil {
            mtNumber = savedNumber
        }
    }

    func resetOnServer() async {
        guard let url = URL(string: "\(endpoints[0])/api/auth/reset") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        do {
            let (_, _) = try await URLSession.shared.data(for: request)
            print("[ProfileManager] Profile reset on server")
        } catch {
            print("[ProfileManager] Reset error: \(error)")
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // РЕГИСТРАЦИЯ В СЕТИ — получить порядковый номер
    // POST /api/wallet/register { address: "mt..." }
    // Response: { number: 42 }
    // ═══════════════════════════════════════════════════════════════
    func registerInNetwork() async {
        guard let address = UserDefaults.standard.string(forKey: "montana_address"),
              !address.isEmpty else {
            print("[ProfileManager] No address to register")
            return
        }

        // Если уже есть номер — не регистрируем повторно
        if sequentialNumber > 0 {
            print("[ProfileManager] Already registered: Ɉ-\(sequentialNumber)")
            return
        }

        guard let url = URL(string: "\(endpoints[0])/api/wallet/register") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(deviceId, forHTTPHeaderField: "X-Device-ID")

        let body: [String: Any] = ["address": address]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let number = json["number"] as? Int {
                    // Сохраняем номер
                    mtNumber = number
                    UserDefaults.standard.set(number, forKey: "montana_mt_number")

                    // Обновляем адрес на единый формат Ɉ-{N}-{hash}
                    if let fullAddress = json["full_address"] as? String {
                        UserDefaults.standard.set(fullAddress, forKey: "montana_address")
                        // Также сохраняем для активного кошелька
                        KeychainManager.shared.saveWalletAddress(fullAddress, forWallet: KeychainManager.shared.activeWalletIndex)
                    }

                    print("[ProfileManager] Registered: Ɉ-\(number), address updated to unified format")
                }
            }
        } catch {
            print("[ProfileManager] Registration error: \(error)")
        }
    }

    func reset() {
        isFrozen = false
        profileId = nil
        mtId = nil
        mtNumber = nil
        print("[ProfileManager] Local state reset")
    }
}

// MARK: - Wallet View

struct WalletView: View {
    @ObservedObject var wallet = WalletService.shared
    @ObservedObject var auth = AuthService.shared
    @ObservedObject var profile = ProfileManager.shared
    @State private var showSettings = false
    @State private var showSend = false
    @State private var showReceive = false
    @State private var showHistory = false
    @State private var copiedMtId = false
    @State private var showMenu = false
    @State private var menuOffset: CGFloat = -UIScreen.main.bounds.width * 0.8

    private let menuWidth: CGFloat = UIScreen.main.bounds.width * 0.8

    // Алиас: делегируем ProfileManager (единый источник правды)
    private var displayAlias: String {
        ProfileManager.shared.alias
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                HStack {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "line.3.horizontal")
                            .font(.title2)
                            .foregroundColor(.white.opacity(0.6))
                    }

                    Spacer()

                    // Network Status (видимая инфраструктура "too big to fail")
                    NetworkStatusView()

                    Spacer()

                    Button {
                        // Notifications
                    } label: {
                        Image(systemName: "bell")
                            .font(.title2)
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 16)

                Spacer()

                // Main Balance
                VStack(spacing: 24) {
                    // Genesis Photo: МЫ_ПОВСЮДУ
                    Image("GenesisPhoto")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 100, height: 100)
                        .clipShape(Circle())
                        .shadow(color: Color(hex: "10B981").opacity(0.5), radius: 30)

                    // Алиас + полный адрес
                    VStack(spacing: 8) {
                        // Алиас (Ɉ-20)
                        Button {
                            UIPasteboard.general.string = displayAlias
                            withAnimation(.easeInOut(duration: 0.3)) {
                                copiedMtId = true
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                withAnimation { copiedMtId = false }
                            }
                        } label: {
                            HStack(spacing: 6) {
                                Text(displayAlias)
                                    .font(.system(size: 22, weight: .semibold, design: .monospaced))
                                    .foregroundColor(Color(hex: "D4AF37"))

                                Image(systemName: copiedMtId ? "checkmark" : "doc.on.doc")
                                    .font(.system(size: 12))
                                    .foregroundColor(copiedMtId ? Color(hex: "10B981") : Color(hex: "D4AF37").opacity(0.6))
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .background(
                                Capsule()
                                    .fill(Color(hex: "D4AF37").opacity(0.1))
                                    .overlay(
                                        Capsule()
                                            .stroke(Color(hex: "D4AF37").opacity(0.3), lineWidth: 1)
                                    )
                            )
                        }

                        // Полный адрес (не урезанный)
                        if let address = UserDefaults.standard.string(forKey: "montana_address") {
                            Text(address)
                                .font(.system(size: 10, weight: .light, design: .monospaced))
                                .foregroundColor(.white.opacity(0.4))
                                .multilineTextAlignment(.center)
                                .lineLimit(2)
                                .padding(.horizontal, 20)
                        }
                    }

                    // Balance with glow and symbol
                    ZStack {
                        // Glow effect (green)
                        Text(formatBalance(wallet.balance))
                            .font(.system(size: 56, weight: .thin, design: .rounded))
                            .foregroundColor(Color(hex: "10B981"))
                            .blur(radius: 20)
                            .opacity(0.5)

                        VStack(spacing: 8) {
                            // Balance + Symbol (bigger)
                            HStack(spacing: 8) {
                                Text(formatBalance(wallet.balance))
                                    .font(.system(size: 56, weight: .thin, design: .rounded))
                                    .foregroundColor(Color(hex: "10B981"))

                                // Coin Symbol — same size as balance
                                Image("CoinSymbol")
                                    .renderingMode(.original)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(height: 56)
                            }

                            Text("монет времени")
                                .font(.system(size: 14, weight: .light))
                                .foregroundColor(Color(hex: "10B981").opacity(0.7))
                                .tracking(2)

                            // Price in RUB + Rate
                            VStack(spacing: 2) {
                                HStack(spacing: 4) {
                                    Text("=")
                                        .font(.system(size: 14, weight: .light))
                                        .foregroundColor(.white.opacity(0.4))
                                    Text(formatRubles(wallet.balance * 12.2))
                                        .font(.system(size: 18, weight: .medium, design: .rounded))
                                        .foregroundColor(Color(hex: "D4AF37"))
                                    Text("RUB")
                                        .font(.system(size: 12, weight: .light))
                                        .foregroundColor(.white.opacity(0.4))
                                }

                                Text("1 сек = 12.2 RUB")
                                    .font(.system(size: 10, weight: .light))
                                    .foregroundColor(.white.opacity(0.3))
                            }
                            .padding(.top, 4)
                        }
                    }

                    // 4 Time Slices + TIME_BANK (всё от генезиса)
                    GlobalTimeSlices()
                        .padding(.top, 8)

                    // Sync indicator
                    if wallet.isLoading {
                        HStack(spacing: 8) {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: Color(hex: "10B981")))
                                .scaleEffect(0.8)
                            Text("Синхронизация...")
                                .font(.system(size: 12, weight: .light))
                                .foregroundColor(.white.opacity(0.5))
                        }
                    }
                }

                Spacer()

                // Action Buttons
                HStack(spacing: 24) {
                    ActionCircle(icon: "arrow.up", label: "Отправить") {
                        showSend = true
                    }

                    ActionCircle(icon: "arrow.down", label: "Получить") {
                        showReceive = true
                    }

                    ActionCircle(icon: "clock", label: "История") {
                        showHistory = true
                    }
                }
                .padding(.bottom, 40)

                // Footer
                VStack(spacing: 4) {
                    Text("1 секунда присутствия = 1 Ɉ")
                        .font(.system(size: 12, weight: .light))
                        .foregroundColor(.white.opacity(0.3))

                    Text("Генезис Beeple: 1 Ɉ = 12.2 RUB")
                        .font(.system(size: 10, weight: .light))
                        .foregroundColor(Color(hex: "D4AF37").opacity(0.4))
                }
                .padding(.bottom, 32)
            }
        }
        .sheet(isPresented: $showSend) {
            SendSheet()
        }
        .sheet(isPresented: $showReceive) {
            ReceiveSheet()
        }
        .sheet(isPresented: $showHistory) {
            NavigationStack {
                TransactionHistoryView()
            }
        }
        .onAppear {
            wallet.startSession()
        }
        // Свайп влево для открытия меню
        .gesture(
            DragGesture()
                .onChanged { value in
                    // Свайп от левого края вправо — открываем меню
                    if value.startLocation.x < 30 && value.translation.width > 0 {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            menuOffset = min(0, -menuWidth + value.translation.width)
                        }
                    }
                    // Свайп влево при открытом меню — закрываем
                    if showMenu && value.translation.width < 0 {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            menuOffset = max(-menuWidth, value.translation.width)
                        }
                    }
                }
                .onEnded { value in
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        if value.translation.width > 50 || (showMenu && value.translation.width > -50) {
                            menuOffset = 0
                            showMenu = true
                        } else {
                            menuOffset = -menuWidth
                            showMenu = false
                        }
                    }
                }
        )
        // Оверлей меню
        .overlay(
            ZStack {
                // Затемнение фона
                if showMenu {
                    Color.black.opacity(0.5)
                        .ignoresSafeArea()
                        .onTapGesture {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                menuOffset = -menuWidth
                                showMenu = false
                            }
                        }
                }

                // Боковое меню
                HStack(spacing: 0) {
                    SideMenuView(showMenu: $showMenu, menuOffset: $menuOffset, menuWidth: menuWidth)
                        .frame(width: menuWidth)
                        .offset(x: menuOffset)

                    Spacer()
                }
            }
        )
        .onChange(of: showSettings) { newValue in
            if newValue {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    menuOffset = 0
                    showMenu = true
                }
                showSettings = false
            }
        }
        .onAppear {
            // Загружаем профиль (MT ID) при появлении кошелька
            profile.loadProfile()
        }
    }

    private func formatBalance(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        return formatter.string(from: NSNumber(value: Int(value))) ?? "0"
    }

    private func formatRubles(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        formatter.maximumFractionDigits = 2
        return formatter.string(from: NSNumber(value: value)) ?? "0"
    }

    private func formatCountdown(_ minutes: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        return formatter.string(from: NSNumber(value: Int(minutes))) ?? "0"
    }

    // TAU Time Slices from server (synced)
    // τ1 = 1 min, τ2 = 10 min, τ3 = 14 days, τ4 = 4 years
    private let TAU1_SEC: Double = 60
    private let TAU2_SEC: Double = 600
    private let TAU3_SEC: Double = 1_209_600
    private let TAU4_SEC: Double = 126_230_400

    private func sliceValue(for index: Int) -> String {
        // Use synced values from server
        switch index {
        case 0: return String(format: "%.0f", wallet.tau1)   // τ1
        case 1: return String(format: "%.1f", wallet.tau2)   // τ2
        case 2: return String(format: "%.4f", wallet.tau3)   // τ3
        case 3: return String(format: "%.6f", wallet.tau4)   // τ4
        default: return "0"
        }
    }

    private func sliceLabel(for index: Int) -> String {
        switch index {
        case 0: return "1 мин"
        case 1: return "10 мин"
        case 2: return "14 дн"
        case 3: return "4 года"
        default: return ""
        }
    }

    private func sliceIsActive(for index: Int) -> Bool {
        let total = wallet.balance
        switch index {
        case 0: return total >= TAU1_SEC
        case 1: return total >= TAU2_SEC
        case 2: return total >= TAU3_SEC
        case 3: return total >= TAU4_SEC
        default: return false
        }
    }
}

// MARK: - Time Slice Component

struct TimeSlice: View {
    let value: String
    let label: String
    let isActive: Bool

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 24, weight: .light, design: .monospaced))
                .foregroundColor(isActive ? .white : .white.opacity(0.3))

            Text(label)
                .font(.system(size: 10, weight: .light))
                .foregroundColor(isActive ? Color(hex: "D4AF37") : .white.opacity(0.2))
        }
        .frame(width: 60, height: 50)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.white.opacity(isActive ? 0.08 : 0.03))
        )
    }
}

// MARK: - Global Time Slices + TIME_BANK (всё от Genesis 9 Jan 2026)

struct GlobalTimeSlices: View {
    // Когнитивный Генезис: 9 января 2026 00:00:00 МСК
    // = 8 января 2026 21:00:00 UTC
    private let genesisDate: Date = {
        var components = DateComponents()
        components.year = 2026
        components.month = 1
        components.day = 9
        components.hour = 0
        components.minute = 0
        components.second = 0
        components.timeZone = TimeZone(identifier: "Europe/Moscow")
        return Calendar.current.date(from: components) ?? Date()
    }()

    // TAU Constants (в секундах)
    private let TAU1: Double = 60              // 1 минута
    private let TAU2: Double = 600             // 10 минут
    private let TAU3: Double = 1_209_600       // 14 дней
    private let TAU4: Double = 126_230_400     // 4 года

    // БАНК ВРЕМЕНИ: ровно 40 лет в секундах (с реальными високосными)
    // Високосные: 2028,2032,2036,2040,2044,2048,2052,2056,2060,2064 = 10 лет
    // Обычные: 30 лет
    // 30 × 365 × 86400 = 946,080,000
    // 10 × 366 × 86400 = 316,224,000
    // ИТОГО: 1,262,304,000 секунд
    // Конец: 9 января 2066 00:00:00 МСК
    private let totalReserveSeconds: Int = 1_262_304_000

    var body: some View {
        // TimelineView для точной синхронизации с часами
        TimelineView(.periodic(from: .now, by: 1.0)) { context in
            let now = context.date

            // Глобальное время с genesis (в секундах)
            let secondsSinceGenesis = max(0, Double(now.timeIntervalSince(genesisDate)))

            // Иерархические слайсы времени (каскадный сброс)
            // τ₄ → τ₃ → τ₂ → τ₁ (как часы: годы → дни → часы → минуты)

            // τ₄: полные 4-летние эпохи (никогда не сбрасывается)
            let tau4Value = Int(secondsSinceGenesis / TAU4)
            let remainingAfterTau4 = secondsSinceGenesis.truncatingRemainder(dividingBy: TAU4)

            // τ₃: полные 14-дневки внутри текущей эпохи (0-103, потом сброс)
            let tau3Value = Int(remainingAfterTau4 / TAU3)
            let remainingAfterTau3 = remainingAfterTau4.truncatingRemainder(dividingBy: TAU3)

            // τ₂: полные 10-минутки внутри текущей 14-дневки (0-2015, потом сброс)
            let tau2Value = Int(remainingAfterTau3 / TAU2)
            let remainingAfterTau2 = remainingAfterTau3.truncatingRemainder(dividingBy: TAU2)

            // τ₁: полные минуты внутри текущей 10-минутки (0-9, потом сброс)
            let tau1Value = Int(remainingAfterTau2 / TAU1)

            // Секунды внутри текущей минуты (0-59, потом сброс в τ₁)
            let currentSecondInMinute = Int(remainingAfterTau2.truncatingRemainder(dividingBy: TAU1))

            // БАНК ВРЕМЕНИ: 1,262,304,000 секунд = ровно 40 лет
            // Конец: 9 января 2066 00:00:00 МСК
            let endDate = genesisDate.addingTimeInterval(Double(totalReserveSeconds))
            let remainingTotalSeconds = max(0, Int(endDate.timeIntervalSince(now)))
            let remainingMinutes = remainingTotalSeconds / 60
            let remainingSecondsInMinute = remainingTotalSeconds % 60

            // Для отображения даты конца (московское время)
            let dateFormatter = DateFormatter()
            dateFormatter.locale = Locale(identifier: "ru_RU")
            dateFormatter.timeZone = TimeZone(identifier: "Europe/Moscow")
            dateFormatter.dateFormat = "d MMMM yyyy HH:mm:ss"
            let endDateString = dateFormatter.string(from: endDate).uppercased()
            // Короткая дата для заголовка
            dateFormatter.dateFormat = "d MMMM yyyy"
            let endDateShort = dateFormatter.string(from: endDate).uppercased()

            // Обратный отсчёт до конца в годах/днях/часах
            let secondsToEnd = Double(remainingTotalSeconds)
            let yearsToEnd = Int(secondsToEnd / (365.25 * 24 * 60 * 60))
            let daysToEnd = Int((secondsToEnd.truncatingRemainder(dividingBy: 365.25 * 24 * 60 * 60)) / (24 * 60 * 60))
            let hoursToEnd = Int((secondsToEnd.truncatingRemainder(dividingBy: 24 * 60 * 60)) / (60 * 60))
            let minutesToEnd = Int((secondsToEnd.truncatingRemainder(dividingBy: 60 * 60)) / 60)
            let secondsToEndDisplay = remainingSecondsInMinute

            return VStack(spacing: 12) {
                // 5 Time Slices (иерархические — каскадный сброс)
                // сек → τ₁ → τ₂ → τ₃ → τ₄
                HStack(spacing: 8) {
                    GlobalSlice(value: String(format: "%02d", currentSecondInMinute), label: "сек", isActive: true)
                    GlobalSlice(value: "\(tau1Value)", label: "τ₁", isActive: tau1Value >= 1)
                    GlobalSlice(value: formatNumber(tau2Value), label: "τ₂", isActive: tau2Value >= 1)
                    GlobalSlice(value: "\(tau3Value)", label: "τ₃", isActive: tau3Value >= 1)
                    GlobalSlice(value: "\(tau4Value)", label: "τ₄", isActive: tau4Value >= 1)
                }

                // TIME_BANK Countdown
                VStack(spacing: 6) {
                    HStack(spacing: 6) {
                        Image(systemName: "hourglass")
                            .font(.system(size: 12))
                            .foregroundColor(Color(hex: "D4AF37").opacity(0.8))
                        Text("БАНК ВРЕМЕНИ")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(Color(hex: "D4AF37").opacity(0.8))
                    }

                    // Оставшееся время (минуты + секунды синхронизированы)
                    HStack(spacing: 4) {
                        Text(formatNumber(remainingMinutes))
                            .font(.system(size: 22, weight: .light, design: .monospaced))
                            .foregroundColor(.white.opacity(0.9))
                        Text("мин")
                            .font(.system(size: 10, weight: .light))
                            .foregroundColor(.white.opacity(0.4))
                        Text(String(format: "%02d", remainingSecondsInMinute))
                            .font(.system(size: 22, weight: .light, design: .monospaced))
                            .foregroundColor(Color(hex: "D4AF37"))
                        Text("сек")
                            .font(.system(size: 10, weight: .light))
                            .foregroundColor(.white.opacity(0.4))
                    }

                    // Прошло с генезиса — конвертация в дни/месяцы/годы
                    let genesisYears = Int(secondsSinceGenesis / (365.25 * 24 * 60 * 60))
                    let genesisDays = Int((secondsSinceGenesis.truncatingRemainder(dividingBy: 365.25 * 24 * 60 * 60)) / (24 * 60 * 60))
                    let genesisHours = Int((secondsSinceGenesis.truncatingRemainder(dividingBy: 24 * 60 * 60)) / (60 * 60))
                    let genesisMinutes = Int((secondsSinceGenesis.truncatingRemainder(dividingBy: 60 * 60)) / 60)
                    let genesisSec = Int(secondsSinceGenesis) % 60

                    HStack(spacing: 4) {
                        Text("с генезиса:")
                            .font(.system(size: 9, weight: .light))
                            .foregroundColor(.white.opacity(0.3))
                        if genesisYears > 0 {
                            Text("\(genesisYears)")
                                .font(.system(size: 10, weight: .medium, design: .monospaced))
                                .foregroundColor(.white.opacity(0.5))
                            Text("г")
                                .font(.system(size: 8, weight: .light))
                                .foregroundColor(.white.opacity(0.3))
                        }
                        Text("\(genesisDays)")
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .foregroundColor(.white.opacity(0.5))
                        Text("дн")
                            .font(.system(size: 8, weight: .light))
                            .foregroundColor(.white.opacity(0.3))
                        Text(String(format: "%02d:%02d:%02d", genesisHours, genesisMinutes, genesisSec))
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .foregroundColor(.white.opacity(0.4))
                    }
                }

                // Разделитель
                Rectangle()
                    .fill(Color.white.opacity(0.1))
                    .frame(height: 1)
                    .padding(.horizontal, 40)
                    .padding(.vertical, 8)

                // Дата конца эмиссии (вычислена от 21M минут, МСК)
                VStack(spacing: 4) {
                    Text(endDateShort + " МСК")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(Color(hex: "D4AF37").opacity(0.6))
                        .tracking(2)

                    // Обратный отсчёт до конца
                    HStack(spacing: 4) {
                        Text("\(yearsToEnd)")
                            .font(.system(size: 16, weight: .light, design: .monospaced))
                            .foregroundColor(.white.opacity(0.7))
                        Text("лет")
                            .font(.system(size: 8, weight: .light))
                            .foregroundColor(.white.opacity(0.3))

                        Text("\(daysToEnd)")
                            .font(.system(size: 16, weight: .light, design: .monospaced))
                            .foregroundColor(.white.opacity(0.7))
                        Text("дн")
                            .font(.system(size: 8, weight: .light))
                            .foregroundColor(.white.opacity(0.3))

                        Text(String(format: "%02d", hoursToEnd))
                            .font(.system(size: 16, weight: .light, design: .monospaced))
                            .foregroundColor(.white.opacity(0.7))
                        Text(":")
                            .foregroundColor(.white.opacity(0.3))
                        Text(String(format: "%02d", minutesToEnd))
                            .font(.system(size: 16, weight: .light, design: .monospaced))
                            .foregroundColor(.white.opacity(0.7))
                        Text(":")
                            .foregroundColor(.white.opacity(0.3))
                        Text(String(format: "%02d", secondsToEndDisplay))
                            .font(.system(size: 16, weight: .light, design: .monospaced))
                            .foregroundColor(Color(hex: "D4AF37").opacity(0.8))
                    }

                    Text("последняя секунда эмиссии")
                        .font(.system(size: 8, weight: .light))
                        .foregroundColor(.white.opacity(0.2))
                }
            }
        }
    }

    private func formatNumber(_ value: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        return formatter.string(from: NSNumber(value: value)) ?? "0"
    }
}

// MARK: - Global Slice Component

struct GlobalSlice: View {
    let value: String
    let label: String
    let isActive: Bool

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 20, weight: .light, design: .monospaced))
                .foregroundColor(isActive ? .white : .white.opacity(0.3))
                .lineLimit(1)
                .minimumScaleFactor(0.6)

            Text(label)
                .font(.system(size: 9, weight: .light))
                .foregroundColor(isActive ? Color(hex: "D4AF37") : .white.opacity(0.2))
        }
        .frame(width: 70, height: 50)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.white.opacity(isActive ? 0.08 : 0.03))
        )
    }
}

// MARK: - Action Circle

struct ActionCircle: View {
    let icon: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                ZStack {
                    Circle()
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                        .frame(width: 56, height: 56)

                    Image(systemName: icon)
                        .font(.system(size: 20, weight: .light))
                        .foregroundColor(.white)
                }

                Text(label)
                    .font(.system(size: 12, weight: .light))
                    .foregroundColor(.white.opacity(0.6))
            }
        }
    }
}

// MARK: - Sidebar Menu (Hamburger)

// MARK: - Side Menu View (свайп влево)

struct SideMenuView: View {
    @Binding var showMenu: Bool
    @Binding var menuOffset: CGFloat
    let menuWidth: CGFloat

    @ObservedObject var auth = AuthService.shared
    @ObservedObject var profile = ProfileManager.shared
    @State private var showSettingsDetail = false
    @State private var showTimeChain = false

    var body: some View {
        ZStack {
            Color(hex: "0A0A0A").ignoresSafeArea()

            VStack(spacing: 0) {
                // Header с аватаром
                HStack(spacing: 16) {
                    Image("GenesisPhoto")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 50, height: 50)
                        .clipShape(Circle())

                    VStack(alignment: .leading, spacing: 4) {
                        Text("Montana")
                            .font(.title3)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)

                        // MT ID — только цифры, кликабельный для копирования
                        if let mtNumber = profile.mtNumber {
                            Button {
                                UIPasteboard.general.string = "\(mtNumber)"
                                // Haptic feedback
                                let generator = UIImpactFeedbackGenerator(style: .light)
                                generator.impactOccurred()
                            } label: {
                                HStack(spacing: 4) {
                                    Text("\(mtNumber)")
                                        .font(.system(size: 14, weight: .medium, design: .monospaced))
                                        .foregroundColor(Color(hex: "D4AF37"))
                                    Image(systemName: "doc.on.doc")
                                        .font(.system(size: 10))
                                        .foregroundColor(Color(hex: "D4AF37").opacity(0.6))
                                }
                            }
                        }
                    }

                    Spacer()

                    // Кнопка закрытия
                    Button {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            menuOffset = -menuWidth
                            showMenu = false
                        }
                    } label: {
                        Image(systemName: "xmark")
                            .font(.title3)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 60)
                .padding(.bottom, 20)

                Divider()
                    .background(Color.white.opacity(0.1))

                // Приложения Montana
                VStack(alignment: .leading, spacing: 0) {
                    Text("ПРИЛОЖЕНИЯ")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(.white.opacity(0.3))
                        .padding(.horizontal, 20)
                        .padding(.top, 20)
                        .padding(.bottom, 12)

                    // Junona (главный экран - кошелёк)
                    Button {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            menuOffset = -menuWidth
                            showMenu = false
                        }
                    } label: {
                        MenuRow(icon: "creditcard.fill", name: "Кошелёк", isActive: true)
                    }

                    // Цепочка Времени
                    Button {
                        showTimeChain = true
                    } label: {
                        MenuRow(icon: "pentagon", name: "Цепочка", isActive: true)
                    }
                }

                Spacer()

                Divider()
                    .background(Color.white.opacity(0.1))

                // Настройки и Выход
                VStack(spacing: 0) {
                    Button {
                        showSettingsDetail = true
                    } label: {
                        HStack(spacing: 16) {
                            Image(systemName: "gearshape.fill")
                                .font(.title3)
                                .foregroundColor(.white.opacity(0.6))
                                .frame(width: 32)

                            Text("Настройки")
                                .font(.system(size: 16))
                                .foregroundColor(.white.opacity(0.8))

                            Spacer()

                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.3))
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 14)
                    }

                    // Выход
                    Button {
                        auth.logout()
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            menuOffset = -menuWidth
                            showMenu = false
                        }
                    } label: {
                        HStack(spacing: 16) {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                                .font(.title3)
                                .foregroundColor(.red.opacity(0.7))
                                .frame(width: 32)

                            Text("Выйти")
                                .font(.system(size: 16))
                                .foregroundColor(.red.opacity(0.7))

                            Spacer()
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 14)
                    }
                }
                .padding(.bottom, 40)
            }
        }
        .sheet(isPresented: $showSettingsDetail) {
            SettingsDetailView()
        }
        .fullScreenCover(isPresented: $showTimeChain) {
            NavigationStack {
                TimeChainExplorerView()
                    .toolbar {
                        ToolbarItem(placement: .navigationBarLeading) {
                            Button {
                                showTimeChain = false
                            } label: {
                                Image(systemName: "xmark")
                                    .foregroundColor(.white.opacity(0.6))
                            }
                        }
                    }
            }
        }
    }
}

// MARK: - Menu Row

struct MenuRow: View {
    let icon: String
    let name: String
    var isActive: Bool = true
    var badge: String? = nil

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(isActive ? Color(hex: "10B981") : .white.opacity(0.4))
                .frame(width: 32)

            Text(name)
                .font(.system(size: 16))
                .foregroundColor(isActive ? .white : .white.opacity(0.5))

            Spacer()

            if let badge = badge {
                Text(badge)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.white.opacity(0.4))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.white.opacity(0.1))
                    .cornerRadius(4)
            } else if isActive {
                Circle()
                    .fill(Color(hex: "10B981"))
                    .frame(width: 8, height: 8)
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }
}

// MARK: - Settings Sheet (deprecated - используем SideMenuView)

struct SettingsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var auth = AuthService.shared
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Header с аватаром
                    if let user = auth.currentUser {
                        HStack(spacing: 16) {
                            Image("GenesisPhoto")
                                .resizable()
                                .scaledToFill()
                                .frame(width: 60, height: 60)
                                .clipShape(Circle())

                            VStack(alignment: .leading, spacing: 4) {
                                Text("Montana")
                                    .font(.title3)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white)

                                Text(user.shortAddress)
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.5))
                                    .fontDesign(.monospaced)
                            }

                            Spacer()
                        }
                        .padding(.horizontal, 24)
                        .padding(.top, 24)
                        .padding(.bottom, 16)
                    }

                    Divider()
                        .background(Color.white.opacity(0.1))

                    // Приложения Montana
                    VStack(alignment: .leading, spacing: 0) {
                        Text("ПРИЛОЖЕНИЯ")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(.white.opacity(0.3))
                            .padding(.horizontal, 24)
                            .padding(.top, 20)
                            .padding(.bottom, 12)

                        // Junona — активно
                        SidebarAppRow(
                            icon: "message.fill",
                            name: "Junona",
                            status: .active,
                            statusText: "Подключено"
                        )

                        // Кошелёк — активно
                        SidebarAppRow(
                            icon: "creditcard.fill",
                            name: "Кошелёк",
                            status: .active,
                            statusText: "Активен"
                        )

                        // Контракты — скоро
                        SidebarAppRow(
                            icon: "doc.text.fill",
                            name: "Контракты",
                            status: .soon,
                            statusText: "Скоро"
                        )
                    }

                    Spacer()

                    Divider()
                        .background(Color.white.opacity(0.1))

                    // Настройки внизу
                    VStack(spacing: 0) {
                        Button {
                            showSettings = true
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "gearshape.fill")
                                    .font(.title3)
                                    .foregroundColor(.white.opacity(0.6))
                                    .frame(width: 32)

                                Text("Настройки")
                                    .font(.system(size: 16))
                                    .foregroundColor(.white.opacity(0.8))

                                Spacer()

                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.3))
                            }
                            .padding(.horizontal, 24)
                            .padding(.vertical, 16)
                        }

                        // Выход
                        Button {
                            auth.logout()
                            dismiss()
                        } label: {
                            HStack(spacing: 16) {
                                Image(systemName: "rectangle.portrait.and.arrow.right")
                                    .font(.title3)
                                    .foregroundColor(.red.opacity(0.7))
                                    .frame(width: 32)

                                Text("Выйти")
                                    .font(.system(size: 16))
                                    .foregroundColor(.red.opacity(0.7))

                                Spacer()
                            }
                            .padding(.horizontal, 24)
                            .padding(.vertical, 16)
                        }
                    }
                    .padding(.bottom, 16)
                }
            }
            .navigationTitle("Меню")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsDetailView()
            }
        }
    }
}

// MARK: - Sidebar App Row

enum AppStatus {
    case active
    case soon
    case offline
}

struct SidebarAppRow: View {
    let icon: String
    let name: String
    let status: AppStatus
    let statusText: String

    var statusColor: Color {
        switch status {
        case .active: return Color(hex: "10B981")  // Зелёный
        case .soon: return Color(hex: "D4AF37")    // Золотой
        case .offline: return .red.opacity(0.7)
        }
    }

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(MontanaTheme.primary)
                .frame(width: 32)

            Text(name)
                .font(.system(size: 16))
                .foregroundColor(.white.opacity(0.9))

            Spacer()

            // Статус
            HStack(spacing: 6) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 6, height: 6)
                Text(statusText)
                    .font(.system(size: 11))
                    .foregroundColor(statusColor)
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 14)
        .background(Color.white.opacity(0.02))
    }
}

// MARK: - Settings Detail View

struct SettingsDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var auth = AuthService.shared
    @ObservedObject var profile = ProfileManager.shared
    @State private var copiedId: String?
    @State private var showRecoveryPhrase = false
    @State private var showChangePin = false
    @State private var showSetupPin = false
    @State private var showCreateIdentity = false
    @State private var showRestoreIdentity = false

    private var mtId: String? {
        UserDefaults.standard.string(forKey: "montana_mt_id")
    }
    private var montanaAddress: String? {
        UserDefaults.standard.string(forKey: "montana_address")
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // MARK: - Профиль
                        SettingsSectionView(title: "ПРОФИЛЬ") {
                            VStack(spacing: 0) {
                                // MT ID
                                if let mtId = mtId {
                                    SettingsRowView(
                                        icon: "person.badge.shield.checkmark.fill",
                                        iconColor: Color(hex: "D4AF37"),
                                        title: "Montana ID",
                                        value: mtId,
                                        isCopyable: true,
                                        copiedId: $copiedId
                                    )
                                }

                                Divider().background(Color.white.opacity(0.1))

                                // Баланс
                                SettingsRowView(
                                    icon: "clock.fill",
                                    iconColor: Color(hex: "10B981"),
                                    title: "Баланс",
                                    value: "\(Int(WalletService.shared.balance)) Ɉ"
                                )
                            }
                        }

                        // MARK: - Авторизация
                        SettingsSectionView(title: "АВТОРИЗАЦИЯ") {
                            VStack(spacing: 0) {
                                SettingsRowView(
                                    icon: "brain.head.profile",
                                    iconColor: Color(hex: "D4AF37"),
                                    title: "Когнитивный ключ",
                                    value: "Активен"
                                )
                            }
                        }

                        // MARK: - Устройства
                        SettingsSectionView(title: "УСТРОЙСТВА") {
                            VStack(spacing: 0) {
                                // Текущее устройство
                                SettingsDeviceRow(
                                    icon: "iphone",
                                    name: UIDevice.current.name,
                                    deviceId: profile.deviceId,
                                    isCurrent: true,
                                    onCopy: {
                                        UIPasteboard.general.string = profile.deviceId
                                        copiedId = profile.deviceId
                                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                            if copiedId == profile.deviceId { copiedId = nil }
                                        }
                                    },
                                    copiedId: copiedId
                                )
                            }
                        }

                        // MARK: - Безопасность
                        SettingsSectionView(title: "БЕЗОПАСНОСТЬ") {
                            VStack(spacing: 0) {
                                // PIN-код
                                Button {
                                    if KeychainManager.shared.hasPin {
                                        showChangePin = true
                                    } else {
                                        showSetupPin = true
                                    }
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: KeychainManager.shared.hasPin ? "lock.fill" : "lock.open.fill")
                                            .font(.system(size: 18))
                                            .foregroundColor(KeychainManager.shared.hasPin ? Color(hex: "10B981") : .orange)
                                            .frame(width: 28)

                                        Text("PIN-код")
                                            .font(.system(size: 15))
                                            .foregroundColor(.white.opacity(0.6))

                                        Spacer()

                                        Text(KeychainManager.shared.hasPin ? "Включён" : "Не установлен")
                                            .font(.system(size: 13))
                                            .foregroundColor(KeychainManager.shared.hasPin ? Color(hex: "10B981") : .orange)

                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 12))
                                            .foregroundColor(.white.opacity(0.3))
                                    }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 14)
                                }

                                Divider().background(Color.white.opacity(0.1))

                                // Когнитивный ключ
                                Button {
                                    if KeychainManager.shared.hasPin {
                                        showRecoveryPhrase = true
                                    } else {
                                        showSetupPin = true
                                    }
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "eye.fill")
                                            .font(.system(size: 18))
                                            .foregroundColor(Color(hex: "7b2fff"))
                                            .frame(width: 28)

                                        Text("Когнитивный ключ")
                                            .font(.system(size: 15))
                                            .foregroundColor(.white.opacity(0.6))

                                        Spacer()

                                        if KeychainManager.shared.hasPin {
                                            Image(systemName: "lock.fill")
                                                .font(.system(size: 12))
                                                .foregroundColor(.white.opacity(0.3))
                                        } else {
                                            Text("Нужен PIN")
                                                .font(.system(size: 13))
                                                .foregroundColor(.orange)
                                        }

                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 12))
                                            .foregroundColor(.white.opacity(0.3))
                                    }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 14)
                                }
                            }
                        }

                        // MARK: - Идентичность
                        SettingsSectionView(title: "ИДЕНТИЧНОСТЬ") {
                            VStack(spacing: 0) {
                                // Создать новую
                                Button {
                                    showCreateIdentity = true
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "plus.circle.fill")
                                            .font(.system(size: 18))
                                            .foregroundColor(Color(hex: "00d4ff"))
                                            .frame(width: 28)

                                        Text("Создать новую идентичность")
                                            .font(.system(size: 15))
                                            .foregroundColor(.white.opacity(0.6))

                                        Spacer()

                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 12))
                                            .foregroundColor(.white.opacity(0.3))
                                    }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 14)
                                }

                                Divider().background(Color.white.opacity(0.1))

                                // Восстановить
                                Button {
                                    showRestoreIdentity = true
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "arrow.counterclockwise.circle.fill")
                                            .font(.system(size: 18))
                                            .foregroundColor(Color(hex: "7b2fff"))
                                            .frame(width: 28)

                                        Text("Восстановить из ключа")
                                            .font(.system(size: 15))
                                            .foregroundColor(.white.opacity(0.6))

                                        Spacer()

                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 12))
                                            .foregroundColor(.white.opacity(0.3))
                                    }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 14)
                                }
                            }
                        }

                        // MARK: - О приложении (всегда в конце)
                        SettingsSectionView(title: "О ПРИЛОЖЕНИИ") {
                            VStack(spacing: 0) {
                                SettingsInfoRow(label: "Версия", value: Montana.version)
                                Divider().background(Color.white.opacity(0.1))
                                SettingsInfoRow(label: "Криптография", value: "ML-DSA-65")
                                Divider().background(Color.white.opacity(0.1))
                                SettingsInfoRow(label: "Стандарт", value: "FIPS 204")
                                Divider().background(Color.white.opacity(0.1))
                                SettingsInfoRow(label: "Генезис", value: "9 января 2026")
                            }
                        }

                        Spacer().frame(height: 40)
                    }
                    .padding(.top, 16)
                }
            }
            .navigationTitle("Настройки")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Готово") { dismiss() }
                        .foregroundColor(Color(hex: "D4AF37"))
                }
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
                    profile.loadProfile()
                }
            }
            .sheet(isPresented: $showRestoreIdentity) {
                RestoreIdentityView {
                    profile.loadProfile()
                }
            }
        }
    }
}

// MARK: - Settings Section

struct SettingsSectionView<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.white.opacity(0.4))
                .padding(.horizontal, 20)

            content
                .background(Color.white.opacity(0.05))
                .cornerRadius(12)
                .padding(.horizontal, 16)
        }
    }
}

// MARK: - Settings Row

struct SettingsRowView: View {
    let icon: String
    let iconColor: Color
    let title: String
    let value: String
    var isCopyable: Bool = false
    var fullValue: String? = nil
    @Binding var copiedId: String?
    var isConnected: Bool = false

    init(icon: String, iconColor: Color, title: String, value: String, isCopyable: Bool = false, fullValue: String? = nil, copiedId: Binding<String?>? = nil, isConnected: Bool = false) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.value = value
        self.isCopyable = isCopyable
        self.fullValue = fullValue
        self._copiedId = copiedId ?? .constant(nil)
        self.isConnected = isConnected
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(iconColor)
                .frame(width: 28)

            Text(title)
                .font(.system(size: 15))
                .foregroundColor(.white.opacity(0.6))

            Spacer()

            if copiedId == (fullValue ?? value) {
                Text("Скопировано")
                    .font(.system(size: 13))
                    .foregroundColor(Color(hex: "10B981"))
            } else {
                Text(value)
                    .font(.system(size: 14, design: .monospaced))
                    .foregroundColor(.white.opacity(0.9))
                    .lineLimit(1)
            }

            if isConnected {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 16))
                    .foregroundColor(Color(hex: "10B981"))
            }

            if isCopyable {
                Button {
                    UIPasteboard.general.string = fullValue ?? value
                    withAnimation {
                        copiedId = fullValue ?? value
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                        withAnimation {
                            if copiedId == (fullValue ?? value) {
                                copiedId = nil
                            }
                        }
                    }
                } label: {
                    Image(systemName: "doc.on.doc")
                        .font(.system(size: 14))
                        .foregroundColor(.white.opacity(0.4))
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
}

struct SettingsInfoRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .font(.system(size: 14))
                .foregroundColor(.white.opacity(0.5))
            Spacer()
            Text(value)
                .font(.system(size: 14))
                .foregroundColor(.white.opacity(0.8))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

// MARK: - Settings Device Row

struct SettingsDeviceRow: View {
    let icon: String
    let name: String
    let deviceId: String
    let isCurrent: Bool
    var onCopy: (() -> Void)?
    var copiedId: String?

    var body: some View {
        HStack(spacing: 12) {
            // Иконка устройства
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(isCurrent ? Color(hex: "10B981") : .white.opacity(0.5))
                .frame(width: 28)

            // Название и ID
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(name)
                        .font(.system(size: 15))
                        .foregroundColor(.white)

                    if isCurrent {
                        Text("текущее")
                            .font(.system(size: 11))
                            .foregroundColor(Color(hex: "10B981"))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color(hex: "10B981").opacity(0.2))
                            .cornerRadius(4)
                    }
                }

                if copiedId == deviceId {
                    Text("Скопировано")
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: "10B981"))
                } else {
                    Text(String(deviceId.prefix(8)) + "...")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white.opacity(0.4))
                }
            }

            Spacer()

            // Копировать
            if let onCopy = onCopy {
                Button(action: onCopy) {
                    Image(systemName: "doc.on.doc")
                        .font(.system(size: 14))
                        .foregroundColor(.white.opacity(0.4))
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
}

// MARK: - Send Sheet

struct SendSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var wallet = WalletService.shared
    @State private var recipient = ""
    @State private var amount = ""
    @State private var isSending = false
    @State private var statusText = ""
    @State private var statusColor: Color = .secondary
    @State private var sendSuccess = false
    @State private var sentAmount = 0
    @State private var sentRecipient = ""
    @State private var sentTimestamp = ""

    private let gold = Color(hex: "D4AF37")
    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let cardBg = Color.white.opacity(0.05)

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                if sendSuccess {
                    confirmationView
                } else {
                    sendFormView
                }
            }
            .navigationTitle(sendSuccess ? "" : "Отправить")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if !sendSuccess {
                        Button("Отмена") { dismiss() }
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
            }
        }
    }

    private var confirmationView: some View {
        VStack(spacing: 0) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(.green)
                .padding(.bottom, 20)

            Text("Отправлено")
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(.green)
                .padding(.bottom, 28)

            VStack(spacing: 16) {
                confirmRow(label: "Сумма", value: formatAmt(sentAmount))
                confirmRow(label: "Получатель", value: sentRecipient)
                confirmRow(label: "Время", value: sentTimestamp)
            }
            .padding(20)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(cardBg)
            )
            .padding(.horizontal, 32)

            Spacer()

            Button { dismiss() } label: {
                Text("Готово")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(.black)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(cyan)
                    .cornerRadius(12)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
    }

    private func confirmRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(.white.opacity(0.5))
            Spacer()
            Text(value)
                .font(.system(size: 15, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
        }
    }

    private var currentBalance: Int {
        Int(wallet.balance)
    }

    private var sendFormView: some View {
        VStack(spacing: 24) {
            // Balance card
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Доступно")
                        .font(.system(size: 11, weight: .light))
                        .foregroundColor(.white.opacity(0.4))
                    Text(formatAmt(currentBalance))
                        .font(.system(size: 20, weight: .bold, design: .monospaced))
                        .foregroundColor(cyan)
                }
                Spacer()
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(cardBg)
            )

            VStack(alignment: .leading, spacing: 8) {
                Text("Адрес или номер")
                    .font(.system(size: 12, weight: .light))
                    .foregroundColor(.white.opacity(0.4))

                TextField("mt... / 1 / @ник", text: $recipient)
                    .font(.system(size: 16, design: .monospaced))
                    .foregroundColor(.white)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .padding()
                    .background(Color.white.opacity(0.05))
                    .cornerRadius(12)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Сумма")
                    .font(.system(size: 12, weight: .light))
                    .foregroundColor(.white.opacity(0.4))

                HStack {
                    TextField("0", text: $amount)
                        .keyboardType(.numberPad)
                        .font(.system(size: 32, weight: .thin))
                        .foregroundColor(.white)

                    Text("Ɉ")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(gold)
                }
                .padding()
                .background(Color.white.opacity(0.05))
                .cornerRadius(12)
            }

            if let amt = Int(amount), amt > currentBalance, currentBalance > 0 {
                HStack(spacing: 4) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 11))
                    Text("Недостаточно средств")
                }
                .font(.system(size: 12))
                .foregroundColor(.orange)
            }

            if !statusText.isEmpty {
                Text(statusText)
                    .font(.system(size: 13))
                    .foregroundColor(statusColor)
                    .multilineTextAlignment(.center)
            }

            Spacer()

            Button { sendTransfer() } label: {
                HStack(spacing: 8) {
                    if isSending {
                        ProgressView().tint(.black)
                    } else {
                        Image(systemName: "paperplane.fill")
                            .foregroundColor(.black)
                    }
                    Text("Отправить")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.black)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(
                    canSend ? gold : Color.white.opacity(0.2)
                )
                .cornerRadius(12)
            }
            .disabled(!canSend)
            .padding(.bottom, 32)
        }
        .padding(.horizontal, 24)
        .padding(.top, 32)
    }

    private var canSend: Bool {
        guard let amt = Int(amount), amt > 0 else { return false }
        return !recipient.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isSending
    }

    private func sendTransfer() {
        guard !isSending else { return }
        guard let amt = Int(amount), amt > 0 else { return }
        let input = recipient.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }
        guard let fromAddr = UserDefaults.standard.string(forKey: "montana_address"), !fromAddr.isEmpty else {
            statusText = "Кошелёк не настроен"
            statusColor = .orange
            return
        }

        isSending = true
        statusText = ""
        Task { @MainActor in
            defer { isSending = false }
            do {
                // Resolve address
                var toAddr = ""
                var toAlias = ""
                if input.hasPrefix("mt") && input.count == 42 {
                    toAddr = input
                    toAlias = String(input.prefix(8)) + "..." + String(input.suffix(4))
                } else {
                    let lookupID: String
                    if input.hasPrefix("@") {
                        lookupID = String(input.dropFirst())
                    } else if input.hasPrefix("Ɉ-") {
                        lookupID = String(input.dropFirst(2))
                    } else {
                        lookupID = input.filter { $0.isNumber }
                    }
                    guard !lookupID.isEmpty else {
                        statusText = "Неверный адрес"
                        statusColor = .red
                        return
                    }
                    let result = try await wallet.lookupWallet(identifier: lookupID)
                    toAddr = result.address
                    toAlias = result.alias
                }

                guard toAddr != fromAddr else {
                    statusText = "Нельзя отправить себе"
                    statusColor = .orange
                    return
                }

                try await wallet.transfer(from: fromAddr, to: toAddr, amount: amt)

                let df = DateFormatter()
                df.dateFormat = "dd.MM.yyyy HH:mm:ss"
                sentAmount = amt
                sentRecipient = toAlias.isEmpty ? (String(toAddr.prefix(8)) + "..." + String(toAddr.suffix(4))) : toAlias
                sentTimestamp = df.string(from: Date())
                sendSuccess = true
            } catch {
                statusText = "Ошибка: \(error.localizedDescription)"
                statusColor = .red
            }
        }
    }

    private func formatAmt(_ amount: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = " "
        let formatted = formatter.string(from: NSNumber(value: amount)) ?? "\(amount)"
        return "\(formatted) Ɉ"
    }
}

// MARK: - Receive Sheet

struct ReceiveSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var auth = AuthService.shared
    @ObservedObject var profile = ProfileManager.shared
    @State private var copiedAlias = false
    @State private var copiedAddress = false

    var body: some View {
        NavigationStack {
            ZStack {
                // Градиентный фон
                LinearGradient(
                    colors: [Color.black, Color(hex: "0a0a0a")],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {

                        // ═══════════════════════════════════════════
                        // ЛОГО МОНЕТЫ ВРЕМЕНИ
                        // ═══════════════════════════════════════════
                        ZStack {
                            // Внешнее свечение
                            Circle()
                                .fill(
                                    RadialGradient(
                                        colors: [Color(hex: "D4AF37").opacity(0.3), .clear],
                                        center: .center,
                                        startRadius: 40,
                                        endRadius: 100
                                    )
                                )
                                .frame(width: 200, height: 200)

                            // Кольцо
                            Circle()
                                .stroke(
                                    LinearGradient(
                                        colors: [Color(hex: "D4AF37"), Color(hex: "B8860B")],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    ),
                                    lineWidth: 3
                                )
                                .frame(width: 120, height: 120)

                            // Символ
                            Text("Ɉ")
                                .font(.system(size: 56, weight: .bold, design: .serif))
                                .foregroundStyle(
                                    LinearGradient(
                                        colors: [Color(hex: "FFD700"), Color(hex: "D4AF37")],
                                        startPoint: .top,
                                        endPoint: .bottom
                                    )
                                )
                        }
                        .padding(.top, 40)
                        .padding(.bottom, 32)

                        // ═══════════════════════════════════════════
                        // АЛИАС — главный идентификатор
                        // ═══════════════════════════════════════════
                        VStack(spacing: 20) {
                            // Заголовок
                            HStack(spacing: 8) {
                                Circle()
                                    .fill(Color(hex: "D4AF37"))
                                    .frame(width: 8, height: 8)
                                Text("АЛИАС")
                                    .font(.system(size: 12, weight: .bold))
                                    .tracking(3)
                                    .foregroundColor(Color(hex: "D4AF37"))
                            }

                            // Алиас — большой и красивый
                            Text(profile.alias)
                                .font(.system(size: 48, weight: .bold, design: .monospaced))
                                .foregroundStyle(
                                    LinearGradient(
                                        colors: [Color(hex: "FFD700"), Color(hex: "D4AF37")],
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    )
                                )

                            // Кнопка копирования
                            Button {
                                UIPasteboard.general.string = profile.alias
                                withAnimation(.spring(response: 0.3)) { copiedAlias = true }
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                    withAnimation { copiedAlias = false }
                                }
                            } label: {
                                HStack(spacing: 8) {
                                    Image(systemName: copiedAlias ? "checkmark.circle.fill" : "doc.on.doc.fill")
                                        .font(.system(size: 16))
                                    Text(copiedAlias ? "Скопировано!" : "Копировать алиас")
                                        .font(.system(size: 14, weight: .semibold))
                                }
                                .foregroundColor(copiedAlias ? Color(hex: "10B981") : Color(hex: "D4AF37"))
                                .padding(.horizontal, 24)
                                .padding(.vertical, 12)
                                .background(
                                    Capsule()
                                        .fill(copiedAlias ? Color(hex: "10B981").opacity(0.15) : Color(hex: "D4AF37").opacity(0.15))
                                        .overlay(
                                            Capsule()
                                                .stroke(copiedAlias ? Color(hex: "10B981").opacity(0.5) : Color(hex: "D4AF37").opacity(0.5), lineWidth: 1)
                                        )
                                )
                            }
                            .scaleEffect(copiedAlias ? 1.05 : 1.0)

                            // Пояснение
                            Text("Уникальный номер кошелька.\nПросто скажи: «Отправь на \(profile.alias)»")
                                .font(.system(size: 13))
                                .foregroundColor(.white.opacity(0.5))
                                .multilineTextAlignment(.center)
                                .lineSpacing(4)
                        }
                        .padding(.vertical, 28)
                        .padding(.horizontal, 24)
                        .frame(maxWidth: .infinity)
                        .background(
                            RoundedRectangle(cornerRadius: 24)
                                .fill(Color(hex: "D4AF37").opacity(0.06))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 24)
                                        .stroke(
                                            LinearGradient(
                                                colors: [Color(hex: "D4AF37").opacity(0.4), Color(hex: "D4AF37").opacity(0.1)],
                                                startPoint: .topLeading,
                                                endPoint: .bottomTrailing
                                            ),
                                            lineWidth: 1
                                        )
                                )
                        )
                        .padding(.horizontal, 20)

                        // Разделитель
                        HStack {
                            Rectangle().fill(.white.opacity(0.1)).frame(height: 1)
                            Text("или")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(.white.opacity(0.3))
                                .padding(.horizontal, 12)
                            Rectangle().fill(.white.opacity(0.1)).frame(height: 1)
                        }
                        .padding(.horizontal, 40)
                        .padding(.vertical, 24)

                        // ═══════════════════════════════════════════
                        // ПОЛНЫЙ АДРЕС — криптографический
                        // ═══════════════════════════════════════════
                        if let user = auth.currentUser {
                            VStack(spacing: 16) {
                                // Заголовок
                                HStack(spacing: 8) {
                                    Image(systemName: "key.fill")
                                        .font(.system(size: 10))
                                    Text("ПОЛНЫЙ АДРЕС")
                                        .font(.system(size: 11, weight: .semibold))
                                        .tracking(2)
                                }
                                .foregroundColor(.white.opacity(0.4))

                                // Адрес в новом формате: Ɉ-{номер}-{хеш}
                                Text(profile.fullAddress)
                                    .font(.system(size: 12, design: .monospaced))
                                    .foregroundColor(.white.opacity(0.7))
                                    .multilineTextAlignment(.center)
                                    .lineSpacing(4)
                                    .padding(.horizontal, 8)

                                // Кнопка копирования
                                Button {
                                    UIPasteboard.general.string = profile.fullAddress
                                    withAnimation(.spring(response: 0.3)) { copiedAddress = true }
                                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                        withAnimation { copiedAddress = false }
                                    }
                                } label: {
                                    HStack(spacing: 6) {
                                        Image(systemName: copiedAddress ? "checkmark.circle.fill" : "doc.on.doc")
                                            .font(.system(size: 12))
                                        Text(copiedAddress ? "Скопировано!" : "Копировать адрес")
                                            .font(.system(size: 12, weight: .medium))
                                    }
                                    .foregroundColor(copiedAddress ? Color(hex: "10B981") : .white.opacity(0.6))
                                    .padding(.horizontal, 20)
                                    .padding(.vertical, 10)
                                    .background(
                                        Capsule()
                                            .fill(.white.opacity(0.05))
                                            .overlay(
                                                Capsule()
                                                    .stroke(.white.opacity(0.1), lineWidth: 1)
                                            )
                                    )
                                }

                                // Пояснение
                                Text("Криптографический адрес ML-DSA-65\nДля верификации и внешних систем")
                                    .font(.system(size: 11))
                                    .foregroundColor(.white.opacity(0.3))
                                    .multilineTextAlignment(.center)
                                    .lineSpacing(3)
                            }
                            .padding(.vertical, 20)
                            .padding(.horizontal, 20)
                            .frame(maxWidth: .infinity)
                            .background(
                                RoundedRectangle(cornerRadius: 16)
                                    .fill(.white.opacity(0.02))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 16)
                                            .stroke(.white.opacity(0.06), lineWidth: 1)
                                    )
                            )
                            .padding(.horizontal, 20)
                        }

                        Spacer(minLength: 60)
                    }
                }
            }
            .navigationTitle("Получить")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Готово") { dismiss() }
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(Color(hex: "D4AF37"))
                }
            }
            .onAppear {
                profile.loadProfile()
            }
        }
    }
}

// MARK: - Wallet Service (синхронизация с сервером + live update)

@MainActor
class WalletService: ObservableObject {
    static let shared = WalletService()

    @Published var balance: Double = 0
    @Published var sessionStart: Date?
    @Published var isLoading = false

    // TAU Slices from server
    @Published var tau1: Double = 0  // 1 минута
    @Published var tau2: Double = 0  // 10 минут
    @Published var tau3: Double = 0  // 14 дней
    @Published var tau4: Double = 0  // 4 года

    // Network Status (видимая инфраструктура "too big to fail")
    @Published var networkStatus: NetworkStatus = .connecting
    @Published var isConnected = false
    @Published var activeNodes = 0
    @Published var failoverCount = 0
    @Published var endpointLatencies: [String: Int] = [:]
    private var sessionStartTime = Date()

    private var tickTimer: Timer?
    private var syncTimer: Timer?

    // Серверы для отказоустойчивости (failover)
    // 3 узла сети Montana + сайт Timeweb
    // Все проверены через SSH — API работает
    // IP адреса используют HTTP (нет SSL сертификатов), сайт использует HTTPS
    private let endpointConfigs: [(name: String, url: String)] = [
        ("Timeweb", "https://1394793-cy33234.tw1.ru"),      // Сайт (primary, HTTPS)
        ("Moscow", "http://176.124.208.93"),                // Москва (HTTP)
        ("Amsterdam", "http://72.56.102.240"),              // Амстердам (HTTP)
        ("Almaty", "http://91.200.148.93")                  // Алматы (HTTP)
    ]
    private var endpoints: [String] { endpointConfigs.map { $0.url } }
    private var currentEndpointIndex = 0
    private var baseURL: String { endpoints[currentEndpointIndex] }

    // Имя текущего endpoint для UI
    var currentEndpointName: String {
        guard currentEndpointIndex < endpointConfigs.count else { return "Offline" }
        return endpointConfigs[currentEndpointIndex].name
    }

    // Все endpoints для отображения в NetworkDetailsSheet
    var allEndpoints: [EndpointInfo] {
        endpointConfigs.enumerated().map { index, config in
            EndpointInfo(
                name: config.name,
                url: config.url.replacingOccurrences(of: "https://", with: ""),
                isActive: index == currentEndpointIndex && isConnected,
                latency: endpointLatencies[config.url]
            )
        }
    }

    // Uptime с момента запуска сессии
    var uptimeString: String {
        let seconds = Int(Date().timeIntervalSince(sessionStartTime))
        if seconds < 60 { return "\(seconds)s" }
        if seconds < 3600 { return "\(seconds / 60)m" }
        return "\(seconds / 3600)h"
    }

    // TAU Constants for local tick
    private let TAU1_SEC: Double = 60
    private let TAU2_SEC: Double = 600
    private let TAU3_SEC: Double = 1_209_600
    private let TAU4_SEC: Double = 126_230_400

    // Ключи для UserDefaults
    private let balanceKey = "montana_balance"
    private let lastReportedKey = "montana_last_reported"
    private var hasSyncedOnce = false
    private var lastReportedBalance: Double = 0

    private init() {
        // Восстанавливаем состояние
        lastReportedBalance = UserDefaults.standard.double(forKey: lastReportedKey)
        balance = UserDefaults.standard.double(forKey: balanceKey)
        currentEndpointIndex = UserDefaults.standard.integer(forKey: "montana_endpoint_index")
        if currentEndpointIndex >= endpoints.count { currentEndpointIndex = 0 }
        sessionStartTime = Date()
        activeNodes = endpoints.count
        print("[Montana] Init: balance=\(Int(balance)), endpoints=\(endpoints.count)")
    }

    /// Сброс баланса при создании новой идентичности
    func resetForNewIdentity() {
        balance = 0
        lastReportedBalance = 0
        hasSyncedOnce = false
        tau1 = 0; tau2 = 0; tau3 = 0; tau4 = 0
        UserDefaults.standard.set(0.0, forKey: balanceKey)
        UserDefaults.standard.set(0.0, forKey: lastReportedKey)
        print("[Montana] Balance reset for new identity")
    }

    // Failover: попробовать все серверы для надёжности
    // "Too big to fail" — автоматическое переключение между узлами
    private func tryAllEndpoints<T>(_ operation: (String) async throws -> T) async throws -> T {
        var lastError: Error?
        networkStatus = .connecting

        for i in 0..<endpoints.count {
            let index = (currentEndpointIndex + i) % endpoints.count
            let endpoint = endpoints[index]

            let startTime = Date()
            do {
                let result = try await operation(endpoint)

                // Успех — обновляем статистику
                let latency = Int(Date().timeIntervalSince(startTime) * 1000)
                endpointLatencies[endpoint] = latency

                if index != currentEndpointIndex {
                    // Failover произошёл
                    failoverCount += 1
                    currentEndpointIndex = index
                    UserDefaults.standard.set(currentEndpointIndex, forKey: "montana_endpoint_index")
                    networkStatus = .failover
                    print("[Montana] Failover #\(failoverCount) → \(endpointConfigs[index].name)")

                    // Через 2 секунды покажем "connected"
                    Task {
                        try? await Task.sleep(nanoseconds: 2_000_000_000)
                        await MainActor.run {
                            self.networkStatus = .connected
                        }
                    }
                } else {
                    networkStatus = .connected
                }

                isConnected = true
                activeNodes = endpoints.count  // Все узлы считаются активными
                return result
            } catch {
                endpointLatencies[endpoint] = nil  // Endpoint не отвечает
                lastError = error
                print("[Montana] Endpoint \(endpointConfigs[index].name) failed: \(error.localizedDescription)")
            }
        }

        // Все endpoints недоступны
        networkStatus = .offline
        isConnected = false
        activeNodes = 0
        throw lastError ?? URLError(.cannotConnectToHost)
    }

    func startSession() {
        guard sessionStart == nil else { return }
        sessionStart = Date()

        // СНАЧАЛА синхронизируем с сервером, ПОТОМ запускаем таймер
        Task {
            // Пингуем ВСЕ узлы параллельно для отображения статуса
            await pingAllEndpoints()

            await syncBalance()
            await reportPresence()  // Сразу отправляем накопленное (если есть)

            // Только после первой синхронизации запускаем таймер +1
            await MainActor.run {
                self.startTimers()
            }
        }
    }

    /// Пингует все endpoints параллельно для показа latency/standby
    func pingAllEndpoints() async {
        await withTaskGroup(of: (String, Int?).self) { group in
            for config in endpointConfigs {
                group.addTask {
                    let startTime = Date()
                    do {
                        guard let url = URL(string: "\(config.url)/api/health") else {
                            return (config.url, nil)
                        }
                        var request = URLRequest(url: url)
                        request.timeoutInterval = 5
                        let (_, response) = try await URLSession.shared.data(for: request)
                        if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                            let latency = Int(Date().timeIntervalSince(startTime) * 1000)
                            return (config.url, latency)
                        }
                        return (config.url, nil)
                    } catch {
                        return (config.url, nil)
                    }
                }
            }

            for await (endpoint, latency) in group {
                await MainActor.run {
                    self.endpointLatencies[endpoint] = latency
                }
            }
        }

        // Подсчитываем активные узлы и обновляем статус
        await MainActor.run {
            let respondingNodes = self.endpointLatencies.values.compactMap { $0 }.count
            self.activeNodes = respondingNodes

            // Если хотя бы один узел отвечает — сеть работает
            if respondingNodes > 0 {
                self.networkStatus = .connected
                self.isConnected = true
            } else {
                self.networkStatus = .offline
                self.isConnected = false
            }
        }
    }

    private func startTimers() {
        guard tickTimer == nil else { return }

        // Обновляем UI каждую секунду (+1 Ɉ)
        tickTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self else { return }
                self.balance += 1

                // Сохраняем каждые 10 секунд
                if Int(self.balance) % 10 == 0 {
                    UserDefaults.standard.set(self.balance, forKey: self.balanceKey)
                }

                // Update local slices
                self.tau1 = self.balance / self.TAU1_SEC
                self.tau2 = self.balance / self.TAU2_SEC
                self.tau3 = self.balance / self.TAU3_SEC
                self.tau4 = self.balance / self.TAU4_SEC
            }
        }

        // Синхронизируем с сервером каждые 30 секунд + отправляем presence
        syncTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.syncBalance()
                await self?.reportPresence()
            }
        }
    }

    // MARK: - Presence Reporting
    //
    // АРХИТЕКТУРА MONTANA:
    // - balance = presence_seconds (сколько секунд присутствовал этот tg_id)
    // - 100 устройств с одним tg_id = всё равно 60 сек/мин (идентичность)
    // - АНТИЦЕНЗУРА: пробуем все endpoints при отправке

    func reportPresence() async {
        // Ключ кошелька = montana_address
        guard let key = UserDefaults.standard.string(forKey: "montana_address"),
              !key.isEmpty else { return }

        let delta = Int(balance - lastReportedBalance)
        guard delta > 0 else { return }

        do {
            // АНТИЦЕНЗУРА: пробуем все endpoints
            let serverBalance = try await tryAllEndpoints { endpoint -> Int in
                guard let url = URL(string: "\(endpoint)/api/presence") else {
                    throw URLError(.badURL)
                }

                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.setValue(key, forHTTPHeaderField: "X-Device-ID")
                request.httpBody = try JSONSerialization.data(withJSONObject: ["seconds": delta])

                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let balance = json["balance"] as? Int else {
                    throw URLError(.cannotParseResponse)
                }
                return balance
            }

            // Синхронизируем с сервером
            if Double(serverBalance) > self.balance {
                self.balance = Double(serverBalance)
                UserDefaults.standard.set(self.balance, forKey: balanceKey)
            }
            lastReportedBalance = Double(serverBalance)
            UserDefaults.standard.set(lastReportedBalance, forKey: lastReportedKey)
            print("[Montana] Presence: +\(delta)s → balance=\(serverBalance)")
        } catch {
            print("[Montana] Presence failed on all endpoints: \(error)")
        }
    }

    func stopSession() {
        tickTimer?.invalidate()
        tickTimer = nil
        syncTimer?.invalidate()
        syncTimer = nil
        sessionStart = nil
    }

    func syncBalance() async {
        // Ключ кошелька = montana_address
        guard let key = UserDefaults.standard.string(forKey: "montana_address"),
              !key.isEmpty else {
            print("[Montana] syncBalance: нет montana_address")
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            // АНТИЦЕНЗУРА: пробуем все endpoints
            let json = try await tryAllEndpoints { endpoint in
                let encodedKey = key.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? key
                guard let url = URL(string: "\(endpoint)/api/balance/\(encodedKey)") else {
                    throw URLError(.badURL)
                }
                let (data, _) = try await URLSession.shared.data(from: url)
                guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    throw URLError(.cannotParseResponse)
                }
                return json
            }

            // СЕРВЕР = ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ
            let serverBalance = json["balance"] as? Int ?? 0

            if !hasSyncedOnce {
                self.balance = Double(serverBalance)
                lastReportedBalance = self.balance
                UserDefaults.standard.set(lastReportedBalance, forKey: lastReportedKey)
                print("[Montana] First sync: balance=\(serverBalance)")
            } else {
                if Double(serverBalance) > self.balance {
                    self.balance = Double(serverBalance)
                }
            }

            hasSyncedOnce = true
            UserDefaults.standard.set(self.balance, forKey: balanceKey)
            print("[Montana] Sync: server=\(serverBalance), local=\(Int(balance))")

            // TAU slices от сервера
            if let slices = json["slices"] as? [String: Any] {
                self.tau1 = slices["tau1"] as? Double ?? (self.balance / TAU1_SEC)
                self.tau2 = slices["tau2"] as? Double ?? (self.balance / TAU2_SEC)
                self.tau3 = slices["tau3"] as? Double ?? (self.balance / TAU3_SEC)
                self.tau4 = slices["tau4"] as? Double ?? (self.balance / TAU4_SEC)
            }
        } catch {
            print("[Montana] All endpoints failed: \(error)")
        }
    }

    // MARK: - Transfer API

    /// Перевод монет времени
    /// - Parameters:
    ///   - to: Получатель (телефон, tg_id или mt-адрес)
    ///   - amount: Сумма в Ɉ
    /// - Returns: Результат перевода
    func transfer(to recipient: String, amount: Int) async -> TransferResult {
        // Ключ кошелька: telegram_id ИЛИ google_email
        var walletKey: String?
        if let tgId = UserDefaults.standard.string(forKey: "montana_telegram_id"),
           !tgId.isEmpty, tgId.allSatisfy({ $0.isNumber }) {
            walletKey = tgId
        } else if let email = UserDefaults.standard.string(forKey: "montana_google_email"),
                  !email.isEmpty {
            walletKey = email
        }

        guard let key = walletKey else {
            return TransferResult(success: false, error: "Не авторизован")
        }

        guard amount > 0 else {
            return TransferResult(success: false, error: "Сумма должна быть > 0")
        }

        guard Int(balance) >= amount else {
            return TransferResult(success: false, error: "Недостаточно средств")
        }

        do {
            let result = try await tryAllEndpoints { endpoint -> TransferResult in
                guard let url = URL(string: "\(endpoint)/api/transfer") else {
                    throw URLError(.badURL)
                }

                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.setValue(key, forHTTPHeaderField: "X-Device-ID")
                request.httpBody = try JSONSerialization.data(withJSONObject: [
                    "to": recipient,
                    "amount": amount
                ])

                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse else {
                    throw URLError(.cannotParseResponse)
                }

                guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    throw URLError(.cannotParseResponse)
                }

                if httpResponse.statusCode == 200, json["success"] as? Bool == true {
                    let newBalance = json["from_balance"] as? Int ?? Int(self.balance) - amount
                    return TransferResult(
                        success: true,
                        txId: json["tx_id"] as? String,
                        newBalance: newBalance
                    )
                } else {
                    let error = json["error"] as? String ?? "Ошибка перевода"
                    return TransferResult(success: false, error: error)
                }
            }

            // Обновляем локальный баланс
            if result.success, let newBalance = result.newBalance {
                self.balance = Double(newBalance)
                UserDefaults.standard.set(self.balance, forKey: balanceKey)
            }

            return result

        } catch {
            return TransferResult(success: false, error: error.localizedDescription)
        }
    }

    // MARK: - Transaction History

    /// Получить историю транзакций
    func fetchTransactions(limit: Int = 50) async -> [Transaction] {
        // Ключ кошелька: telegram_id ИЛИ google_email
        var walletKey: String?
        if let tgId = UserDefaults.standard.string(forKey: "montana_telegram_id"),
           !tgId.isEmpty, tgId.allSatisfy({ $0.isNumber }) {
            walletKey = tgId
        } else if let email = UserDefaults.standard.string(forKey: "montana_google_email"),
                  !email.isEmpty {
            walletKey = email
        }

        guard let key = walletKey else {
            print("[Montana] fetchTransactions: нет ключа кошелька")
            return []
        }

        do {
            let transactions = try await tryAllEndpoints { endpoint -> [Transaction] in
                let encodedKey = key.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? key
                guard let url = URL(string: "\(endpoint)/api/transactions/\(encodedKey)?limit=\(limit)") else {
                    throw URLError(.badURL)
                }

                let (data, _) = try await URLSession.shared.data(from: url)

                guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let txArray = json["transactions"] as? [[String: Any]] else {
                    throw URLError(.cannotParseResponse)
                }

                return txArray.compactMap { tx -> Transaction? in
                    guard let id = tx["id"] as? String,
                          let type = tx["type"] as? String,
                          let from = tx["from"] as? String,
                          let to = tx["to"] as? String,
                          let amount = tx["amount"] as? Int,
                          let timestamp = tx["timestamp"] as? String else {
                        return nil
                    }

                    let isIncoming = to == key
                    return Transaction(
                        id: id,
                        type: type,
                        from: from,
                        to: to,
                        amount: amount,
                        timestamp: timestamp,
                        isIncoming: isIncoming
                    )
                }
            }

            return transactions

        } catch {
            print("[Montana] Transactions failed: \(error)")
            return []
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Transfer API (new — matches macOS MontanaAPIClient)
    // ═══════════════════════════════════════════════════════════════════

    func transfer(from: String, to: String, amount: Int) async throws {
        try await tryAllEndpoints { endpoint in
            guard let url = URL(string: "\(endpoint)/api/transfer") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.timeoutInterval = 15

            let timestamp = ISO8601DateFormatter().string(from: Date())
            let body: [String: Any] = [
                "from_address": from,
                "to_address": to,
                "amount": amount,
                "timestamp": timestamp
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.cannotParseResponse)
            }
            if httpResponse.statusCode != 200 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    throw NSError(domain: "Montana", code: httpResponse.statusCode,
                                  userInfo: [NSLocalizedDescriptionKey: error])
                }
                throw URLError(.cannotParseResponse)
            }
            return ()
        }
    }

    func lookupWallet(identifier: String) async throws -> (address: String, alias: String) {
        return try await tryAllEndpoints { endpoint in
            let encoded = identifier.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? identifier
            guard let url = URL(string: "\(endpoint)/api/wallet/lookup/\(encoded)") else {
                throw URLError(.badURL)
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 10

            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw URLError(.cannotParseResponse)
            }

            let cryptoHash = json["crypto_hash"] as? String ?? ""
            let mtAddress = "mt" + cryptoHash
            let alias = json["alias"] as? String ?? ""
            return (mtAddress, alias)
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Event Ledger API — events & addresses (matches macOS)
    // ═══════════════════════════════════════════════════════════════════

    func fetchMyEvents(address: String, limit: Int = 100) async throws -> [[String: Any]] {
        return try await tryAllEndpoints { endpoint in
            let encoded = address.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? address
            guard let url = URL(string: "\(endpoint)/api/node/events?address=\(encoded)&limit=\(limit)") else {
                throw URLError(.badURL)
            }
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let events = json["events"] as? [[String: Any]] else {
                throw URLError(.cannotParseResponse)
            }
            return events
        }
    }

    func fetchEvents(limit: Int = 50) async throws -> [[String: Any]] {
        return try await tryAllEndpoints { endpoint in
            guard let url = URL(string: "\(endpoint)/api/node/events?limit=\(limit)") else {
                throw URLError(.badURL)
            }
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let events = json["events"] as? [[String: Any]] else {
                throw URLError(.cannotParseResponse)
            }
            return events
        }
    }

    func fetchAddresses() async throws -> [[String: Any]] {
        return try await tryAllEndpoints { endpoint in
            guard let url = URL(string: "\(endpoint)/api/addresses") else {
                throw URLError(.badURL)
            }
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let addresses = json["addresses"] as? [[String: Any]] else {
                throw URLError(.cannotParseResponse)
            }
            return addresses
        }
    }

    // MARK: - Lookup

    /// Поиск пользователя по телефону
    func lookupByPhone(_ phone: String) async -> LookupResult? {
        let normalizedPhone = phone
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: "(", with: "")
            .replacingOccurrences(of: ")", with: "")

        do {
            return try await tryAllEndpoints { endpoint -> LookupResult? in
                guard let url = URL(string: "\(endpoint)/api/lookup/phone/\(normalizedPhone)") else {
                    throw URLError(.badURL)
                }

                let (data, _) = try await URLSession.shared.data(from: url)

                guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    throw URLError(.cannotParseResponse)
                }

                if json["found"] as? Bool == true {
                    return LookupResult(
                        found: true,
                        tgId: json["tg_id"] as? String,
                        address: json["address"] as? String
                    )
                }

                return LookupResult(found: false)
            }
        } catch {
            return nil
        }
    }
}

// MARK: - Transfer Result

struct TransferResult {
    let success: Bool
    var txId: String?
    var newBalance: Int?
    var error: String?
}

// MARK: - Transaction

struct Transaction: Identifiable {
    let id: String
    let type: String
    let from: String
    let to: String
    let amount: Int
    let timestamp: String
    let isIncoming: Bool

    var formattedDate: String {
        // Parse ISO8601 and format nicely
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: timestamp) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateStyle = .short
            displayFormatter.timeStyle = .short
            return displayFormatter.string(from: date)
        }
        return timestamp
    }
}

// MARK: - Lookup Result

struct LookupResult {
    let found: Bool
    var tgId: String?
    var address: String?
}

// MARK: - Network Status View (Видимая инфраструктура "too big to fail")

struct NetworkStatusView: View {
    @ObservedObject var wallet = WalletService.shared
    @State private var showDetails = false

    var body: some View {
        Button {
            showDetails = true
        } label: {
            HStack(spacing: 8) {
                // Пульсирующий индикатор
                Circle()
                    .fill(wallet.networkStatus.color)
                    .frame(width: 8, height: 8)
                    .overlay(
                        Circle()
                            .stroke(wallet.networkStatus.color.opacity(0.5), lineWidth: 2)
                            .scaleEffect(wallet.isConnected ? 1.5 : 1.0)
                            .opacity(wallet.isConnected ? 0 : 1)
                            .animation(.easeInOut(duration: 1).repeatForever(autoreverses: false), value: wallet.isConnected)
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text(wallet.currentEndpointName)
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(.white.opacity(0.8))

                    HStack(spacing: 4) {
                        Image(systemName: "server.rack")
                            .font(.system(size: 8))
                        Text("\(wallet.activeNodes) узлов")
                            .font(.system(size: 9))
                    }
                    .foregroundColor(.white.opacity(0.4))
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color.white.opacity(0.05))
            .cornerRadius(12)
        }
        .sheet(isPresented: $showDetails) {
            NetworkDetailsSheet()
        }
    }
}

// MARK: - Network Details Sheet (Полная информация о сети)

struct NetworkDetailsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var wallet = WalletService.shared

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // Заголовок статуса
                        VStack(spacing: 8) {
                            ZStack {
                                Circle()
                                    .fill(wallet.networkStatus.color.opacity(0.2))
                                    .frame(width: 80, height: 80)

                                Image(systemName: wallet.networkStatus == .connected ? "checkmark.shield.fill" : "exclamationmark.shield.fill")
                                    .font(.system(size: 36))
                                    .foregroundColor(wallet.networkStatus.color)
                            }

                            Text(wallet.networkStatus.title)
                                .font(.title2)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)

                            Text(wallet.networkStatus.description)
                                .font(.subheadline)
                                .foregroundColor(.white.opacity(0.6))
                                .multilineTextAlignment(.center)
                        }
                        .padding(.top, 24)

                        // Активные серверы
                        VStack(alignment: .leading, spacing: 12) {
                            Text("ИНФРАСТРУКТУРА")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundColor(.white.opacity(0.3))
                                .padding(.horizontal, 4)

                            ForEach(wallet.allEndpoints, id: \.name) { endpoint in
                                EndpointRow(
                                    name: endpoint.name,
                                    url: endpoint.url,
                                    isActive: endpoint.isActive,
                                    latency: endpoint.latency
                                )
                            }
                        }
                        .padding(.horizontal, 24)

                        // Статистика отказоустойчивости
                        VStack(alignment: .leading, spacing: 12) {
                            Text("ОТКАЗОУСТОЙЧИВОСТЬ")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundColor(.white.opacity(0.3))
                                .padding(.horizontal, 4)

                            HStack(spacing: 16) {
                                StatBox(value: "\(wallet.activeNodes)", label: "Узлов", icon: "server.rack")
                                StatBox(value: "\(wallet.failoverCount)", label: "Failover", icon: "arrow.triangle.2.circlepath")
                                StatBox(value: wallet.uptimeString, label: "Uptime", icon: "clock")
                            }
                        }
                        .padding(.horizontal, 24)

                        // Информация о протоколе
                        VStack(spacing: 8) {
                            Text("Montana Protocol v\(Montana.version)")
                                .font(.system(size: 12, weight: .light))
                                .foregroundColor(.white.opacity(0.3))

                            Text("Децентрализованная сеть — невозможно отключить")
                                .font(.system(size: 10, weight: .light))
                                .foregroundColor(Color(hex: "D4AF37").opacity(0.5))
                        }
                        .padding(.top, 16)

                        Spacer()
                    }
                }
            }
            .navigationTitle("Сеть Montana")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Готово") { dismiss() }
                        .foregroundColor(.white.opacity(0.6))
                }
            }
        }
    }
}

// MARK: - Endpoint Row

struct EndpointRow: View {
    let name: String
    let url: String
    let isActive: Bool
    let latency: Int?

    /// Статус узла: Active (зелёный), Standby (жёлтый), Offline (серый)
    private var nodeStatus: (String, Color) {
        if isActive {
            return ("Active", Color(hex: "10B981"))
        } else if latency != nil {
            return ("Standby", Color(hex: "D4AF37"))
        } else {
            return ("Offline", .white.opacity(0.3))
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            // Статус (цветной индикатор)
            Circle()
                .fill(nodeStatus.1)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(name)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.white.opacity(isActive ? 0.9 : latency != nil ? 0.7 : 0.4))

                    // Бейдж статуса
                    Text(nodeStatus.0)
                        .font(.system(size: 8, weight: .semibold))
                        .foregroundColor(nodeStatus.1)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(nodeStatus.1.opacity(0.15))
                        .cornerRadius(4)
                }

                Text(url)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.white.opacity(0.3))
            }

            Spacer()

            // Latency
            if let latency = latency {
                HStack(spacing: 4) {
                    Text("\(latency)ms")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundColor(latencyColor(latency))
                }
            } else {
                Text("—")
                    .font(.system(size: 11))
                    .foregroundColor(.white.opacity(0.2))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.white.opacity(isActive ? 0.08 : latency != nil ? 0.05 : 0.02))
        .cornerRadius(12)
    }

    private func latencyColor(_ ms: Int) -> Color {
        if ms < 100 { return Color(hex: "10B981") }
        if ms < 300 { return Color(hex: "D4AF37") }
        return .red.opacity(0.7)
    }
}

// MARK: - Stat Box

struct StatBox: View {
    let value: String
    let label: String
    let icon: String

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(Color(hex: "D4AF37").opacity(0.7))

            Text(value)
                .font(.system(size: 20, weight: .light, design: .monospaced))
                .foregroundColor(.white)

            Text(label)
                .font(.system(size: 10, weight: .light))
                .foregroundColor(.white.opacity(0.4))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }
}

// MARK: - Network Status Enum

enum NetworkStatus {
    case connected
    case connecting
    case failover
    case offline

    var color: Color {
        switch self {
        case .connected: return Color(hex: "10B981")
        case .connecting: return Color(hex: "D4AF37")
        case .failover: return Color(hex: "F59E0B")
        case .offline: return .red.opacity(0.7)
        }
    }

    var title: String {
        switch self {
        case .connected: return "Подключено"
        case .connecting: return "Подключение..."
        case .failover: return "Резервный узел"
        case .offline: return "Нет связи"
        }
    }

    var description: String {
        switch self {
        case .connected: return "Сеть Montana работает стабильно"
        case .connecting: return "Устанавливается соединение"
        case .failover: return "Переключение на резервный сервер"
        case .offline: return "Проверьте интернет-соединение"
        }
    }
}

// MARK: - Endpoint Info

struct EndpointInfo {
    let name: String
    let url: String
    let isActive: Bool
    let latency: Int?
}

// MARK: - Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Transaction History (Event Ledger — matches macOS)

struct TransactionHistoryView: View {
    @ObservedObject var wallet = WalletService.shared
    @State private var displayItems: [HistoryItem] = []
    @State private var isLoading = true
    @State private var errorText = ""

    private let cyan = Color(red: 0, green: 0.83, blue: 1)
    private let gold = Color(hex: "D4AF37")
    private let cardBg = Color.white.opacity(0.05)

    struct HistoryItem: Identifiable {
        let id = UUID()
        var eventType: String
        var amount: Int
        var fromAddr: String
        var toAddr: String
        var fromAlias: String
        var toAlias: String
        var timestamp: String
        var emissionCount: Int
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if isLoading {
                VStack(spacing: 16) {
                    ProgressView()
                        .tint(gold)
                    Text("Загрузка...")
                        .foregroundColor(.white.opacity(0.6))
                }
            } else if !errorText.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 40))
                        .foregroundColor(.orange)
                    Text(errorText)
                        .foregroundColor(.white.opacity(0.6))
                        .multilineTextAlignment(.center)
                }
                .padding()
            } else if displayItems.isEmpty {
                VStack(spacing: 24) {
                    Image(systemName: "tray")
                        .font(.system(size: 48))
                        .foregroundColor(.white.opacity(0.2))
                    Text("Нет транзакций")
                        .font(.title3)
                        .foregroundColor(.white.opacity(0.5))
                }
            } else {
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(displayItems) { item in
                            historyRow(item)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                }
            }
        }
        .navigationTitle("История")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { Task { await loadHistory() } } label: {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(gold)
                }
            }
        }
        .task { await loadHistory() }
        .refreshable { await loadHistory() }
    }

    private func historyRow(_ item: HistoryItem) -> some View {
        let myAddr = UserDefaults.standard.string(forKey: "montana_address") ?? ""
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
                return item.emissionCount > 1 ? "Эмиссия (10 мин)" : "Эмиссия"
            }
            if isSent { return "Отправлено" }
            return "Получено"
        }()

        let counterparty: String = {
            if isEmission {
                let alias = item.fromAlias.isEmpty ? "Ɉ-0" : item.fromAlias
                return item.emissionCount > 1 ? "\(alias) ×\(item.emissionCount)" : alias
            }
            if isSent { return displayAddr(item.toAddr, alias: item.toAlias) }
            return displayAddr(item.fromAddr, alias: item.fromAlias)
        }()

        let amountPrefix = (isSent && !isEmission) ? "-" : "+"

        return HStack(spacing: 12) {
            Image(systemName: directionIcon)
                .foregroundColor(directionColor)
                .font(.system(size: 24))

            VStack(alignment: .leading, spacing: 4) {
                Text(directionLabel)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(directionColor)
                HStack(spacing: 4) {
                    if isSent && !isEmission {
                        Image(systemName: "arrow.right")
                            .font(.system(size: 10))
                            .foregroundColor(.white.opacity(0.4))
                    } else if !isEmission {
                        Image(systemName: "arrow.left")
                            .font(.system(size: 10))
                            .foregroundColor(.white.opacity(0.4))
                    }
                    Text(counterparty)
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundColor(.white.opacity(0.5))
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text("\(amountPrefix)\(formatAmount(item.amount))")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundColor(directionColor)
                Text(formatTimestamp(item.timestamp))
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.white.opacity(0.3))
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(cardBg)
        )
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

    private func loadHistory() async {
        guard let myAddr = UserDefaults.standard.string(forKey: "montana_address"), !myAddr.isEmpty else {
            errorText = "Кошелёк не настроен"
            isLoading = false
            return
        }
        isLoading = true
        errorText = ""
        do {
            let events = try await wallet.fetchMyEvents(address: myAddr, limit: 200)
            displayItems = consolidateEvents(events)
            isLoading = false
        } catch {
            errorText = "Ошибка загрузки"
            isLoading = false
        }
    }

    private func consolidateEvents(_ events: [[String: Any]]) -> [HistoryItem] {
        let t2Window: TimeInterval = 600

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
                    if abs(bucket.date.timeIntervalSince(eventDate)) <= t2Window {
                        emissionBucket = (
                            amount: bucket.amount + amount,
                            count: bucket.count + 1,
                            fromAddr: bucket.fromAddr,
                            toAddr: bucket.toAddr,
                            fromAlias: bucket.fromAlias,
                            toAlias: bucket.toAlias,
                            timestamp: bucket.timestamp,
                            date: bucket.date
                        )
                    } else {
                        flushEmission()
                        emissionBucket = (amount, 1, fromAddr, toAddr, fromAlias, toAlias, timestamp, eventDate)
                    }
                } else {
                    emissionBucket = (amount, 1, fromAddr, toAddr, fromAlias, toAlias, timestamp, eventDate)
                }
            } else {
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
        flushEmission()

        return items
    }
}
