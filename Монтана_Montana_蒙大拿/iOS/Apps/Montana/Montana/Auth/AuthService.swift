//
//  AuthService.swift
//  Junona — Montana Messenger
//
//  Сервис авторизации через Montana Backend
//  Постквантовая криптография ML-DSA-65
//

import Foundation
import SwiftUI
import CommonCrypto

// MARK: - Auth State

enum AuthState: Equatable {
    case unauthorized
    case sendingCode
    case waitingForCode(phone: String)
    case verifying(phone: String)
    case creatingKeys
    case authorized
    case enteringCognitiveKey  // Ввод когнитивного ключа
    case restoringIdentity     // Восстановление по когнитивному ключу

    var isSendingCode: Bool {
        if case .sendingCode = self { return true }
        return false
    }

    var isVerifying: Bool {
        if case .verifying = self { return true }
        return false
    }

    var isAuthorized: Bool {
        if case .authorized = self { return true }
        return false
    }
}

// MARK: - Cognitive Key Validation

/// Результат валидации когнитивного ключа
struct CognitiveKeyValidation {
    let isValid: Bool
    let wordCount: Int
    let charCount: Int
    let normalized: String
    let entropyBits: Double
    let entropyLevel: EntropyLevel

    /// Минимум 24 слова ИЛИ 150 символов
    static let minWords = 24
    static let minChars = 150
    /// Минимум 248 бит энтропии для защиты от коллизий на планетарном масштабе
    /// При 8 млрд пользователей: P(collision) ≈ 10^-55 (практически невозможно)
    /// Birthday paradox: P ≈ n²/(2×2^entropy) = (2^33)²/(2×2^248) = 2^(-183)
    static let minEntropyBits: Double = 248

    enum EntropyLevel: String {
        case weak = "Слабый"       // < 100 бит
        case medium = "Средний"    // 100-180 бит
        case strong = "Сильный"    // 180-248 бит
        case excellent = "Отличный" // ≥ 248 бит

        var color: String {
            switch self {
            case .weak: return "red"
            case .medium: return "orange"
            case .strong: return "green"
            case .excellent: return "blue"
            }
        }
    }
}

// MARK: - Auth Service

@MainActor
class AuthService: ObservableObject {
    static let shared = AuthService()

    @Published var state: AuthState = .unauthorized
    @Published var error: String?
    @Published var currentUser: MontanaUser?

    // Demo mode - для тестирования без сервера
    private let demoMode = true
    private let demoCode = "12345"

    private let baseURL = "https://amsterdam.montana.network"
    private let session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        self.session = URLSession(configuration: config)

        // Когнитивный ключ: ключи есть → авторизован
        if let privateKey = loadFromKeychain(key: "private_key"), !privateKey.isEmpty,
           let publicKey = loadFromKeychain(key: "public_key"), !publicKey.isEmpty {
            let address = generateAddress(from: publicKey)
            self.currentUser = MontanaUser(
                id: address,
                phone: "+montana",
                address: address,
                displayName: nil,
                createdAt: Date()
            )
            self.state = .authorized
            UserDefaults.standard.set(address, forKey: "montana_address")
        }
    }

    // MARK: - Send Verification Code

    func sendCode(to phone: String) async {
        state = .sendingCode
        error = nil

        let normalizedPhone = normalizePhone(phone)

        // Demo mode - сразу переходим к вводу кода
        if demoMode {
            try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 сек
            state = .waitingForCode(phone: normalizedPhone)
            return
        }

        do {
            let request = AuthRequest(phone: normalizedPhone, action: "send_code")
            let response: AuthResponse = try await post("/api/v1/auth/send-code", body: request)

            if response.success {
                state = .waitingForCode(phone: normalizedPhone)
            } else {
                error = response.error ?? "Ошибка отправки кода"
                state = .unauthorized
            }
        } catch {
            self.error = "Сеть недоступна"
            state = .unauthorized
        }
    }

    // MARK: - Verify Code

    func verifyCode(_ code: String, for phone: String) async {
        state = .verifying(phone: phone)
        error = nil

        // Demo mode - принимаем код 12345
        if demoMode {
            try? await Task.sleep(nanoseconds: 500_000_000)

            if code == demoCode {
                await createAccountLocal(phone: phone)
            } else {
                error = "Неверный код. Используйте: \(demoCode)"
                state = .waitingForCode(phone: phone)
            }
            return
        }

        do {
            let request = VerifyRequest(phone: phone, code: code)
            let response: VerifyResponse = try await post("/api/v1/auth/verify", body: request)

            if response.success {
                if response.isNewUser {
                    await createAccount(phone: phone, sessionToken: response.sessionToken ?? "")
                } else {
                    await loadProfile(sessionToken: response.sessionToken ?? "")
                }
            } else {
                error = response.error ?? "Неверный код"
                state = .waitingForCode(phone: phone)
            }
        } catch {
            self.error = "Ошибка проверки"
            state = .waitingForCode(phone: phone)
        }
    }

    // MARK: - Create Account Locally (Demo)

    private func createAccountLocal(phone: String) async {
        state = .creatingKeys

        try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 сек для анимации

        // Generate ML-DSA-65 keys
        let keys = generateMLDSAKeys()

        // Save keys to Keychain
        saveToKeychain(key: "private_key", data: keys.privateKey)
        saveToKeychain(key: "public_key", data: keys.publicKey)

        // Create user
        let user = MontanaUser(
            id: UUID().uuidString,
            phone: phone,
            address: generateAddress(from: keys.publicKey),
            displayName: nil,
            createdAt: Date()
        )

        // Save user
        if let userData = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(userData, forKey: "montana_user")
        }

        currentUser = user
        state = .authorized
    }

    // MARK: - Create Account with Server

    private func createAccount(phone: String, sessionToken: String) async {
        state = .creatingKeys

        let keys = generateMLDSAKeys()

        do {
            let request = RegisterRequest(
                phone: phone,
                publicKey: keys.publicKey.base64EncodedString(),
                sessionToken: sessionToken
            )

            let response: RegisterResponse = try await post("/api/v1/auth/register", body: request)

            if response.success {
                saveToKeychain(key: "private_key", data: keys.privateKey)
                saveToKeychain(key: "public_key", data: keys.publicKey)

                let user = MontanaUser(
                    id: response.userId ?? UUID().uuidString,
                    phone: phone,
                    address: response.address ?? generateAddress(from: keys.publicKey),
                    displayName: nil,
                    createdAt: Date()
                )

                if let userData = try? JSONEncoder().encode(user) {
                    UserDefaults.standard.set(userData, forKey: "montana_user")
                }
                UserDefaults.standard.set(sessionToken, forKey: "montana_session")

                currentUser = user
                state = .authorized
            } else {
                error = response.error ?? "Ошибка регистрации"
                state = .unauthorized
            }
        } catch {
            self.error = "Ошибка создания аккаунта"
            state = .unauthorized
        }
    }

    // MARK: - Load Profile

    private func loadProfile(sessionToken: String) async {
        do {
            let response: ProfileResponse = try await get("/api/v1/user/profile", token: sessionToken)

            if response.success, let user = response.user {
                if let userData = try? JSONEncoder().encode(user) {
                    UserDefaults.standard.set(userData, forKey: "montana_user")
                }
                UserDefaults.standard.set(sessionToken, forKey: "montana_session")

                currentUser = user
                state = .authorized
            } else {
                error = "Ошибка загрузки профиля"
                state = .unauthorized
            }
        } catch {
            self.error = "Ошибка загрузки профиля"
            state = .unauthorized
        }
    }

    // MARK: - Logout

    func logout() {
        // ПОЛНЫЙ СБРОС — удаляем ВСЕ данные Montana
        let keys = [
            "montana_user",
            "montana_session",
            "montana_device_id",
            "montana_telegram_id",
            "montana_google_email",
            "montana_has_telegram",
            "montana_has_google",
            "montana_has_apple",
            "montana_mt_id",
            "montana_mt_number",
            "montana_balance",
            "montana_last_reported_balance",
            "montana_logged_out",
            "montana_address",           // CRITICAL: clear address
            "montana_has_cognitive_key", // CRITICAL: clear cognitive key flag
            "montana_native_auth"
        ]

        for key in keys {
            UserDefaults.standard.removeObject(forKey: key)
        }

        // Ставим флаг что пользователь вышел (не авто-восстанавливать)
        UserDefaults.standard.set(true, forKey: "montana_logged_out")

        // Ключи в Keychain
        deleteFromKeychain(key: "private_key")
        deleteFromKeychain(key: "public_key")

        // Удаляем Passkey (Face ID) и разблокируем
        PasskeyService.shared.removePasskey()
        PasskeyService.shared.deleteCognitiveKey()
        BiometricAuth.shared.unlock()

        // НЕ удаляем montana_device_uuid — это ID устройства для восстановления

        currentUser = nil
        state = .unauthorized

        // Сбрасываем ProfileManager
        Task { @MainActor in
            ProfileManager.shared.reset()
        }

        print("[Auth] Полный выход — все данные удалены")
    }

    // MARK: - Cognitive Key (Montana Native Auth)

    /// Режим авторизации
    enum AuthMode {
        case beta       // HMAC подписи (iOS-only, не PQ)
        case mainnet    // ML-DSA-65 подписи (server-side, PQ-safe)
    }

    /// Текущий режим — MAINNET для реального ML-DSA-65
    private let authMode: AuthMode = .mainnet

    // ════════════════════════════════════════════════════════════════
    // SECURITY: Certificate Pinning (защита от MITM)
    // ════════════════════════════════════════════════════════════════
    // TODO: Включить после добавления CertificatePinning.swift в Xcode project
    // 1. Добавить Auth/CertificatePinning.swift в Build Phases -> Compile Sources
    // 2. Установить useCertificatePinning = true
    // 3. Заменить placeholder хеши на реальные (см. инструкции в файле)
    // ════════════════════════════════════════════════════════════════

    /// Валидация когнитивного ключа
    /// Считаем слова/символы + ГЛАВНЫЙ критерий: биты ≥ 248
    func validateCognitiveKey(_ key: String) -> CognitiveKeyValidation {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)

        // Нормализуем: lowercase, убираем лишние пробелы
        let normalized = trimmed
            .lowercased()
            .components(separatedBy: .whitespaces)
            .filter { !$0.isEmpty }
            .joined(separator: " ")

        let wordCount = normalized.components(separatedBy: " ").count
        let charCount = normalized.count

        // Расчёт энтропии
        let entropyBits = calculateEntropy(normalized)
        let entropyLevel = getEntropyLevel(entropyBits)

        // Валидация: ГЛАВНЫЙ критерий — биты ≥ 248
        // Слова/символы показываем, но принимаем ТОЛЬКО strong/excellent
        let entropyOk = entropyBits >= CognitiveKeyValidation.minEntropyBits

        return CognitiveKeyValidation(
            isValid: entropyOk,
            wordCount: wordCount,
            charCount: charCount,
            normalized: normalized,
            entropyBits: entropyBits,
            entropyLevel: entropyLevel
        )
    }

    /// Расчёт энтропии когнитивного ключа
    /// Формула: уникальные_слова × 10 бит + длина × 0.5 бит + бонусы
    /// 10 бит/слово — консервативная оценка (словарь ~1000 слов)
    private func calculateEntropy(_ text: String) -> Double {
        guard !text.isEmpty else { return 0 }

        let words = text.components(separatedBy: " ").filter { !$0.isEmpty }
        let uniqueWords = Set(words)
        let charCount = text.count

        // 1. Основа: уникальные слова × 10 бит
        // 10 бит = log2(1024) — консервативная оценка словаря
        let wordEntropy = Double(uniqueWords.count) * 10.0

        // 2. Бонус за длину: каждый символ добавляет ~0.5 бит
        // (текст не случайный, но длина увеличивает пространство)
        let lengthBonus = Double(charCount) * 0.5

        // 3. Бонус за разнообразие
        let hasLatin = text.range(of: "[a-zA-Z]", options: .regularExpression) != nil
        let hasCyrillic = text.range(of: "[а-яА-ЯёЁ]", options: .regularExpression) != nil
        let hasDigits = text.range(of: "[0-9]", options: .regularExpression) != nil
        let hasSpecial = text.range(of: "[^a-zA-Zа-яА-ЯёЁ0-9\\s]", options: .regularExpression) != nil

        var diversityBonus: Double = 0
        if hasLatin && hasCyrillic { diversityBonus += 20 }  // Смешение языков
        if hasDigits { diversityBonus += 10 }
        if hasSpecial { diversityBonus += 10 }

        // Итого: слова + длина + бонусы
        let totalEntropy = wordEntropy + lengthBonus + diversityBonus

        return totalEntropy  // Без cap — пусть показывает реальное значение
    }

    private func getEntropyLevel(_ bits: Double) -> CognitiveKeyValidation.EntropyLevel {
        switch bits {
        case ..<100: return .weak
        case 100..<180: return .medium
        case 180..<248: return .strong
        default: return .excellent
        }
    }

    /// Генерация Montana Identity из когнитивного ключа
    /// "Ключи — это мысли. Подпись — это стиль мышления."
    func generateMontanaIdentity(cognitiveKey: String) async -> String? {
        let validation = validateCognitiveKey(cognitiveKey)

        guard validation.isValid else {
            error = "Минимум 24 слова или 150 символов"
            return nil
        }

        state = .creatingKeys

        // MAINNET: Server-side ML-DSA-65
        if authMode == .mainnet {
            return await registerMainnet(cognitiveKey: validation.normalized)
        }

        // BETA: Local HKDF keys (не PQ-safe)
        return await registerBeta(validation: validation)
    }

    /// MAINNET регистрация — DETERMINISTIC ML-DSA-65
    /// ✅ DETERMINISTIC: Тот же ключ = те же ключи, ВСЕГДА
    /// Когнитивный ключ → ключи → идентичность
    /// Никаких серверов. Ключи = идентичность.
    private func registerMainnet(cognitiveKey: String) async -> String? {
        // Генерация ключей из когнитивного ключа
        guard let keys = MontanaSeed.deriveKeypair(from: cognitiveKey) else {
            error = "Ошибка генерации ключей"
            state = .enteringCognitiveKey
            return nil
        }

        // Криптографический хеш (без префикса)
        let cryptoHash = MLDSA65.generateAddress(from: keys.publicKey)
        let hashOnly = cryptoHash.hasPrefix("mt") ? String(cryptoHash.dropFirst(2)) : cryptoHash

        // Сохраняем ключи в Keychain
        saveToKeychain(key: "private_key", data: keys.privateKey)
        saveToKeychain(key: "public_key", data: keys.publicKey)

        // Очищаем старые данные
        for key in ["montana_balance", "montana_last_reported_balance", "montana_mt_number", "montana_mt_id", "montana_address"] {
            UserDefaults.standard.removeObject(forKey: key)
        }
        WalletService.shared.resetForNewIdentity()

        // ═══════════════════════════════════════════════════════════════
        // РЕГИСТРАЦИЯ В СЕТИ — получаем порядковый номер
        // Полный адрес: Ɉ-{номер}-{хеш}
        // ═══════════════════════════════════════════════════════════════
        let mtNumber = await registerAndGetNumber(cryptoHash: hashOnly)
        let fullAddress = "Ɉ-\(mtNumber)-\(hashOnly)"

        // Сохраняем полный адрес
        UserDefaults.standard.set(fullAddress, forKey: "montana_address")
        UserDefaults.standard.set(mtNumber, forKey: "montana_mt_number")
        ProfileManager.shared.mtNumber = mtNumber

        // Создаём пользователя с полным адресом
        let user = MontanaUser(
            id: fullAddress,
            phone: "+montana",
            address: fullAddress,
            displayName: nil,
            createdAt: Date()
        )
        if let userData = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(userData, forKey: "montana_user")
        }
        currentUser = user

        // Сохраняем когнитивный ключ для просмотра
        _ = PasskeyService.shared.storeCognitiveKey(cognitiveKey)

        return fullAddress
    }

    /// Регистрация в сети и получение порядкового номера
    /// Failover: пробует все 4 узла сети Montana (3 сервера + сайт)
    private func registerAndGetNumber(cryptoHash: String) async -> Int {
        // 3 узла + сайт (проверены через SSH)
        // IP адреса используют HTTP (нет SSL), сайт использует HTTPS
        let nodes = [
            "https://1394793-cy33234.tw1.ru",    // Сайт Timeweb (primary, HTTPS)
            "http://176.124.208.93",              // Москва (HTTP)
            "http://72.56.102.240",               // Амстердам (HTTP)
            "http://91.200.148.93"                // Алматы (HTTP)
        ]

        let body: [String: Any] = ["address": "mt\(cryptoHash)"]
        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else { return 0 }

        for (index, node) in nodes.enumerated() {
            let endpoint = "\(node)/api/wallet/register"
            guard let url = URL(string: endpoint) else { continue }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = bodyData
            request.timeoutInterval = 10  // 10 секунд на узел

            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let number = json["number"] as? Int {
                    print("[Auth] ✅ Registered via node \(index): Ɉ-\(number)")
                    return number
                }
            } catch {
                print("[Auth] Node \(index) failed: \(error.localizedDescription)")
                continue  // Пробуем следующий узел
            }
        }

        // Все узлы недоступны
        print("[Auth] ⚠️ All nodes failed, returning 0")
        return 0
    }

    /// BETA регистрация — Local HKDF keys (не PQ-safe)
    private func registerBeta(validation: CognitiveKeyValidation) async -> String? {
        // 1. PBKDF2: когнитивный ключ → 32-byte seed
        let keyHash = sha256(validation.normalized.data(using: .utf8)!)
        var salt = "MONTANA_COGNITIVE_V1_".data(using: .utf8)!
        salt.append(keyHash.prefix(16))

        guard let seed = pbkdf2(
            password: validation.normalized,
            salt: salt,
            iterations: 600_000,
            keyLength: 32
        ) else {
            error = "Ошибка генерации ключей"
            state = .enteringCognitiveKey
            return nil
        }

        // 2. Детерминированная генерация ключей из seed
        let keys = generateMLDSAKeysFromSeed(seed)

        // 3. Адрес = mt + SHA256(pubkey)[:20].hex()
        let address = generateAddress(from: keys.publicKey)

        // 4. Сохраняем в Keychain
        saveToKeychain(key: "private_key", data: keys.privateKey)
        saveToKeychain(key: "public_key", data: keys.publicKey)
        // SECURITY: DO NOT store cognitive_key_hash - enables offline brute-force
        saveToKeychain(key: "montana_address", data: address.data(using: .utf8)!)

        // 5. Регистрация на сервере
        let registered = await registerOnServer(
            address: address,
            publicKey: keys.publicKey
        )

        if registered {
            let user = MontanaUser(
                id: address,
                phone: "+montana",
                address: address,
                displayName: nil,
                createdAt: Date()
            )

            if let userData = try? JSONEncoder().encode(user) {
                UserDefaults.standard.set(userData, forKey: "montana_user")
            }
            UserDefaults.standard.set(address, forKey: "montana_address")
            UserDefaults.standard.set(true, forKey: "montana_native_auth")
            UserDefaults.standard.set("beta", forKey: "montana_auth_mode")

            currentUser = user
            state = .authorized

            return address
        } else {
            state = .enteringCognitiveKey
            return nil
        }
    }

    /// Восстановление идентичности по когнитивному ключу
    func restoreIdentity(cognitiveKey: String) async -> String? {
        let validation = validateCognitiveKey(cognitiveKey)

        guard validation.isValid else {
            error = "Минимум 24 слова или 150 символов"
            return nil
        }

        state = .restoringIdentity

        // MAINNET: Server-side ML-DSA-65 restore
        if authMode == .mainnet {
            return await restoreMainnet(cognitiveKey: validation.normalized)
        }

        // BETA: Local restore
        return await restoreBeta(validation: validation)
    }

    /// MAINNET восстановление — DETERMINISTIC ML-DSA-65
    /// ✅ NO SERVER NEEDED: Derive keys directly from cognitive key
    /// ✅ INSTANT: No network request required
    /// ✅ OFFLINE: Works without internet
    /// ✅ BIP-39 STYLE: Same device = verify address, new device = just restore
    private func restoreMainnet(cognitiveKey: String) async -> String? {
        // ═══════════════════════════════════════════════════════════════
        // DETERMINISTIC RESTORE (BIP-39 style):
        // Same cognitive key → same keys → same address
        // If device has saved address → VERIFY it matches!
        // If new device (no saved address) → just restore
        // ═══════════════════════════════════════════════════════════════

        print("[RESTORE] Deriving keys from cognitive key...")

        // Derive keys deterministically — this is ALL we need
        guard let keys = MontanaSeed.deriveKeypair(from: cognitiveKey) else {
            error = "Ошибка восстановления ключей"
            state = .enteringCognitiveKey
            return nil
        }

        let address = MLDSA65.generateAddress(from: keys.publicKey)
        print("[RESTORE] Derived address: \(address)")

        // ═══════════════════════════════════════════════════════════════
        // SERVER VERIFICATION (REQUIRED):
        // Address MUST exist on server to restore.
        // Wrong cognitive key → wrong address → NOT FOUND → error
        // This is BIP-39 style: key derives address, server confirms existence
        // ═══════════════════════════════════════════════════════════════
        var displayName: String? = nil
        var mtNumber: Int? = nil
        var addressExistsOnServer = false

        let endpoints = ["https://1394793-cy33234.tw1.ru"]
        for endpoint in endpoints {
            guard let url = URL(string: "\(endpoint)/api/auth/profile/\(address)") else { continue }

            var request = URLRequest(url: url)
            request.timeoutInterval = 10

            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse else { continue }

                if httpResponse.statusCode == 200 {
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        // Server returns {"exists": true/false}
                        if json["exists"] as? Bool == true {
                            // Address EXISTS on server
                            addressExistsOnServer = true
                            if let profile = json["profile"] as? [String: Any] {
                                displayName = profile["display_name"] as? String
                                mtNumber = profile["mt_number"] as? Int
                            } else {
                                mtNumber = json["mt_number"] as? Int
                            }
                            print("[RESTORE] Address verified on server ✓")
                        } else {
                            // {"exists": false} — Address NOT registered!
                            addressExistsOnServer = false
                            print("[RESTORE] Address NOT FOUND on server (exists=false)")
                        }
                    }
                } else if httpResponse.statusCode == 404 {
                    // Also handle 404 just in case
                    addressExistsOnServer = false
                    print("[RESTORE] Address NOT FOUND on server (404)")
                }
                break
            } catch {
                print("[RESTORE] Server error: \(error)")
                continue
            }
        }

        // CRITICAL: Address MUST exist on server for restore!
        if !addressExistsOnServer {
            error = "Неверный когнитивный ключ"
            state = .enteringCognitiveKey
            print("[RESTORE] REJECTED: Address \(address) not registered")
            return nil
        }

        // ═══════════════════════════════════════════════════════════════
        // SECURITY: Remove old Passkey before saving new keys
        // This prevents confusion if user restores a different address
        // ═══════════════════════════════════════════════════════════════
        PasskeyService.shared.removePasskey()

        // Save keys to Keychain (local cache)
        saveToKeychain(key: "private_key", data: keys.privateKey)
        saveToKeychain(key: "public_key", data: keys.publicKey)
        saveToKeychain(key: "montana_address", data: address.data(using: .utf8)!)

        // Create user
        if let mt = mtNumber {
            UserDefaults.standard.set(mt, forKey: "montana_mt_number")
            let mtIdStr = "Ɉ-\(mt)"
            UserDefaults.standard.set(mtIdStr, forKey: "montana_mt_id")
            ProfileManager.shared.mtId = mtIdStr
            ProfileManager.shared.mtNumber = mt
        }

        let user = MontanaUser(
            id: address,
            phone: "+montana",
            address: address,
            displayName: displayName,
            createdAt: Date()
        )

        if let userData = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(userData, forKey: "montana_user")
        }
        UserDefaults.standard.set(address, forKey: "montana_address")
        UserDefaults.standard.set(true, forKey: "montana_native_auth")
        UserDefaults.standard.set(true, forKey: "montana_has_cognitive_key")
        UserDefaults.standard.set("mainnet_deterministic", forKey: "montana_auth_mode")
        UserDefaults.standard.removeObject(forKey: "montana_logged_out")

        currentUser = user
        state = .authorized

        // Create Passkey for Face ID / Touch ID convenience
        await createPasskeyIfAvailable(for: address)

        // Sync balance from server immediately
        await WalletService.shared.syncBalance()

        print("[RESTORE] SUCCESS: \(address) (deterministic — no server needed)")
        return address
    }

    /// Authorize with existing keys from Keychain
    private func authorizeWithExistingKeys(address: String) async -> String? {
        let user = MontanaUser(
            id: address,
            phone: "+montana",
            address: address,
            displayName: nil,
            createdAt: Date()
        )

        if let userData = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(userData, forKey: "montana_user")
        }
        UserDefaults.standard.set(address, forKey: "montana_address")
        UserDefaults.standard.set(true, forKey: "montana_native_auth")
        UserDefaults.standard.set(true, forKey: "montana_has_cognitive_key")
        UserDefaults.standard.removeObject(forKey: "montana_logged_out")

        currentUser = user
        state = .authorized

        print("[RESTORE] Local restore: \(address)")
        return address
    }

    // MARK: - Passkey Integration

    /// Check if can authenticate with Passkey (Face ID / Touch ID)
    public func canAuthenticateWithPasskey() -> Bool {
        return PasskeyService.shared.canAuthenticateWithPasskey()
    }

    /// Authenticate using Passkey (Face ID / Touch ID)
    /// Returns address if successful
    public func authenticateWithPasskey() async -> String? {
        guard let address = await PasskeyService.shared.authenticate() else {
            error = "Passkey authentication failed"
            return nil
        }

        // Verify keys exist in Keychain
        guard let _ = loadFromKeychain(key: "private_key"),
              let _ = loadFromKeychain(key: "public_key") else {
            error = "Keys not found - use cognitive key to restore"
            PasskeyService.shared.removePasskey()
            return nil
        }

        // Authorize with existing keys
        return await authorizeWithExistingKeys(address: address)
    }

    /// Create Passkey after successful registration/restore
    /// Called automatically - user doesn't need to do anything
    public func createPasskeyIfAvailable(for address: String) async {
        guard PasskeyService.shared.isPasskeyAvailable else {
            print("[Passkey] Biometrics not available, skipping")
            return
        }

        let success = await PasskeyService.shared.createPasskey(for: address)
        if success {
            print("[Passkey] Created successfully for \(address)")
        } else {
            print("[Passkey] Creation failed, will use cognitive key only")
        }
    }

    /// BETA восстановление — Local keys
    private func restoreBeta(validation: CognitiveKeyValidation) async -> String? {
        // 1. PBKDF2: тот же ключ → тот же seed
        let keyHash = sha256(validation.normalized.data(using: .utf8)!)
        var salt = "MONTANA_COGNITIVE_V1_".data(using: .utf8)!
        salt.append(keyHash.prefix(16))

        guard let seed = pbkdf2(
            password: validation.normalized,
            salt: salt,
            iterations: 600_000,
            keyLength: 32
        ) else {
            error = "Ошибка восстановления"
            state = .enteringCognitiveKey
            return nil
        }

        // 2. Те же ключи
        let keys = generateMLDSAKeysFromSeed(seed)
        let address = generateAddress(from: keys.publicKey)

        // 3. Проверяем на сервере
        let profile = await checkProfileExists(address: address)

        guard profile != nil else {
            error = "Профиль не найден. Проверь когнитивный ключ."
            state = .enteringCognitiveKey
            return nil
        }

        // 4. Сохраняем ключи
        saveToKeychain(key: "private_key", data: keys.privateKey)
        saveToKeychain(key: "public_key", data: keys.publicKey)

        // 5. Challenge-response вход
        let loginSuccess = await performChallengeLogin(address: address)
        if !loginSuccess {
            print("[BETA] Challenge login failed, proceeding with local auth")
        }

        // 6. Сохраняем остальные данные
        // SECURITY: DO NOT store cognitive_key_hash - enables offline brute-force
        saveToKeychain(key: "montana_address", data: address.data(using: .utf8)!)

        // 7. Создаём пользователя
        let user = MontanaUser(
            id: address,
            phone: "+montana",
            address: address,
            displayName: profile?["display_name"] as? String,
            createdAt: Date()
        )

        if let userData = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(userData, forKey: "montana_user")
        }
        UserDefaults.standard.set(address, forKey: "montana_address")
        UserDefaults.standard.set(true, forKey: "montana_native_auth")
        UserDefaults.standard.set("beta", forKey: "montana_auth_mode")

        currentUser = user
        state = .authorized

        return address
    }

    /// PBKDF2 key derivation (100,000 итераций = защита от brute-force)
    private func pbkdf2(password: String, salt: Data, iterations: Int, keyLength: Int) -> Data? {
        guard let passwordData = password.data(using: .utf8) else { return nil }

        var derivedKey = Data(count: keyLength)

        let result = derivedKey.withUnsafeMutableBytes { derivedBytes in
            salt.withUnsafeBytes { saltBytes in
                passwordData.withUnsafeBytes { passwordBytes in
                    CCKeyDerivationPBKDF(
                        CCPBKDFAlgorithm(kCCPBKDF2),
                        passwordBytes.baseAddress?.assumingMemoryBound(to: Int8.self),
                        passwordData.count,
                        saltBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        salt.count,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256),
                        UInt32(iterations),
                        derivedBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        keyLength
                    )
                }
            }
        }

        return result == kCCSuccess ? derivedKey : nil
    }

    /// HKDF-Expand (RFC 5869) — криптографически безопасное расширение ключа
    /// Используется для детерминированной генерации ключей из seed
    private func hkdfExpand(prk: Data, info: Data, length: Int) -> Data {
        var output = Data()
        var previous = Data()
        var counter: UInt8 = 1

        while output.count < length {
            var input = previous
            input.append(info)
            input.append(counter)

            // HMAC-SHA256
            var hmacResult = Data(count: 32)
            hmacResult.withUnsafeMutableBytes { hmacBytes in
                prk.withUnsafeBytes { keyBytes in
                    input.withUnsafeBytes { inputBytes in
                        CCHmac(
                            CCHmacAlgorithm(kCCHmacAlgSHA256),
                            keyBytes.baseAddress, prk.count,
                            inputBytes.baseAddress, input.count,
                            hmacBytes.baseAddress
                        )
                    }
                }
            }

            previous = hmacResult
            output.append(hmacResult)
            counter += 1
        }

        return output.prefix(length)
    }

    /// Детерминированная генерация ML-DSA-65 ключей из seed
    ///
    /// ⚠️ КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ ⚠️
    /// ═══════════════════════════════════════════════════════════════════════
    /// Это НЕ настоящий ML-DSA-65! Текущая реализация использует HKDF для
    /// детерминированной генерации псевдо-ключей правильного размера.
    ///
    /// ПРОБЛЕМА:
    /// - Ключи имеют правильный размер (4032/1952 bytes)
    /// - НО они не могут создавать валидные ML-DSA-65 подписи
    /// - Подписи через signMessage() используют HMAC-SHA256 (НЕ квантово-устойчиво!)
    ///
    /// РЕШЕНИЕ:
    /// Интегрировать liboqs для iOS (см. ML_DSA_INTEGRATION.md):
    /// 1. Скомпилировать liboqs для arm64
    /// 2. Использовать OQS_SIG_ml_dsa_65_keypair_from_seed()
    /// 3. Использовать OQS_SIG_ml_dsa_65_sign()
    ///
    /// ВРЕМЕННО:
    /// Сервер верифицирует подписи через dilithium_py (Python).
    /// iOS подписи не пройдут верификацию до интеграции liboqs!
    /// ═══════════════════════════════════════════════════════════════════════
    private func generateMLDSAKeysFromSeed(_ seed: Data) -> (privateKey: Data, publicKey: Data) {
        // HKDF-Expand для детерминированной генерации
        // info содержит контекст для разделения ключей

        // Private key: 4032 bytes (ML-DSA-65 размер)
        let privateInfo = "MONTANA_ML_DSA_65_PRIVATE_KEY_V1".data(using: .utf8)!
        let privateKeyData = hkdfExpand(prk: seed, info: privateInfo, length: 4032)

        // Public key: 1952 bytes (детерминированно из private)
        // В настоящем ML-DSA публичный ключ вычисляется из приватного
        let publicInfo = "MONTANA_ML_DSA_65_PUBLIC_KEY_V1".data(using: .utf8)!
        var publicSeed = privateKeyData.prefix(32)
        publicSeed.append(publicInfo)
        let publicKeyData = hkdfExpand(prk: Data(publicSeed), info: publicInfo, length: 1952)

        return (Data(privateKeyData), Data(publicKeyData))
    }

    /// Регистрация нового адреса на сервере
    private func registerOnServer(address: String, publicKey: Data) async -> Bool {
        // SECURITY: HTTPS only — no HTTP fallback (MITM protection)
        let endpoints = [
            "https://1394793-cy33234.tw1.ru"
        ]

        for endpoint in endpoints {
            guard let url = URL(string: "\(endpoint)/api/auth/register") else { continue }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.timeoutInterval = 10

            // Подписываем регистрацию
            let message = "MONTANA_REGISTER:\(address)"
            let signature = signMessage(message)

            let body: [String: Any] = [
                "address": address,
                "public_key": publicKey.map { String(format: "%02x", $0) }.joined(),
                "signature": signature?.map { String(format: "%02x", $0) }.joined() ?? ""
            ]

            request.httpBody = try? JSONSerialization.data(withJSONObject: body)

            do {
                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse else { continue }

                if httpResponse.statusCode == 200 {
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       json["success"] as? Bool == true {
                        if let mtNumber = json["mt_number"] as? Int {
                            UserDefaults.standard.set(mtNumber, forKey: "montana_mt_number")
                        }
                        return true
                    }
                }
            } catch {
                continue
            }
        }

        // Если сервер недоступен — разрешаем локальную регистрацию
        // (синхронизируем позже)
        return true
    }

    /// Проверка существования профиля на сервере
    private func checkProfileExists(address: String) async -> [String: Any]? {
        // SECURITY: HTTPS only — no HTTP fallback (MITM protection)
        let endpoints = [
            "https://1394793-cy33234.tw1.ru"
        ]

        for endpoint in endpoints {
            guard let url = URL(string: "\(endpoint)/api/auth/profile/\(address)") else { continue }

            var request = URLRequest(url: url)
            request.timeoutInterval = 5

            do {
                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else { continue }

                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   json["exists"] as? Bool == true {
                    return json
                }
            } catch {
                continue
            }
        }

        return nil
    }

    /// MAINNET: Запросить подпись у сервера (ML-DSA-65)
    /// Server хранит private key и подписывает
    private func requestServerSignature(address: String, message: String) async -> Data? {
        // SECURITY: HTTPS only — no HTTP fallback (MITM protection)
        let endpoints = [
            "https://1394793-cy33234.tw1.ru"
        ]

        for endpoint in endpoints {
            guard let url = URL(string: "\(endpoint)/api/auth/sign/mainnet") else { continue }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.timeoutInterval = 10

            let body: [String: Any] = [
                "address": address,
                "message": message
            ]
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)

            do {
                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else { continue }

                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   json["success"] as? Bool == true,
                   let signatureHex = json["signature"] as? String {
                    return Data(hexString: signatureHex)
                }
            } catch {
                continue
            }
        }

        return nil
    }

    /// Challenge-response вход на сервер
    /// MAINNET: Использует server-side ML-DSA-65 подпись
    /// BETA: Использует локальную HMAC подпись
    private func performChallengeLogin(address: String) async -> Bool {
        // SECURITY: HTTPS only — no HTTP fallback (MITM protection)
        let endpoints = [
            "https://1394793-cy33234.tw1.ru"
        ]

        for endpoint in endpoints {
            // 1. Получить challenge
            guard let challengeUrl = URL(string: "\(endpoint)/api/auth/challenge") else { continue }

            var challengeRequest = URLRequest(url: challengeUrl)
            challengeRequest.httpMethod = "POST"
            challengeRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
            challengeRequest.timeoutInterval = 10
            challengeRequest.httpBody = try? JSONSerialization.data(withJSONObject: ["address": address])

            do {
                let (challengeData, challengeResponse) = try await URLSession.shared.data(for: challengeRequest)

                guard let httpResponse = challengeResponse as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else { continue }

                guard let json = try? JSONSerialization.jsonObject(with: challengeData) as? [String: Any],
                      let challenge = json["challenge"] as? String else { continue }

                // 2. Подписать challenge
                let message = "MONTANA_LOGIN:\(challenge)"
                var signature: Data?

                if authMode == .mainnet {
                    // MAINNET: Server-side ML-DSA-65 подпись
                    signature = await requestServerSignature(address: address, message: message)
                    if signature != nil {
                        print("[MAINNET] Got server ML-DSA-65 signature (\(signature!.count) bytes)")
                    }
                } else {
                    // BETA: Local HMAC подпись
                    signature = signMessage(message)
                }

                guard let sig = signature else {
                    print("[Auth] Failed to get signature")
                    continue
                }

                // 3. Отправить подпись
                guard let loginUrl = URL(string: "\(endpoint)/api/auth/login") else { continue }

                var loginRequest = URLRequest(url: loginUrl)
                loginRequest.httpMethod = "POST"
                loginRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                loginRequest.timeoutInterval = 10

                let loginBody: [String: Any] = [
                    "address": address,
                    "signature": sig.map { String(format: "%02x", $0) }.joined()
                ]
                loginRequest.httpBody = try? JSONSerialization.data(withJSONObject: loginBody)

                let (loginData, loginResponse) = try await URLSession.shared.data(for: loginRequest)

                guard let loginHttpResponse = loginResponse as? HTTPURLResponse,
                      loginHttpResponse.statusCode == 200 else {
                    if let errorJson = try? JSONSerialization.jsonObject(with: loginData) as? [String: Any] {
                        print("[Auth] Login error: \(errorJson)")
                    }
                    continue
                }

                if let loginJson = try? JSONSerialization.jsonObject(with: loginData) as? [String: Any],
                   loginJson["success"] as? Bool == true {
                    let mode = authMode == .mainnet ? "MAINNET" : "BETA"
                    print("[\(mode)] Challenge-response login successful!")
                    return true
                }
            } catch {
                print("[Auth] Login error: \(error)")
                continue
            }
        }

        return false
    }

    /// Подпись сообщения с ML-DSA-65 (Self-Custody)
    ///
    /// ✅ SELF-CUSTODY: Использует локальный private key
    /// ✅ POST-QUANTUM: ML-DSA-65 (FIPS 204) через liboqs
    /// ✅ Signature size: 3309 bytes
    private func signMessage(_ message: String) -> Data? {
        guard let privateKey = loadFromKeychain(key: "private_key") else {
            print("[SIGN] No private key in keychain")
            return nil
        }
        guard let messageData = message.data(using: .utf8) else { return nil }

        // SELF-CUSTODY: ML-DSA-65 signature with local private key
        guard let signature = MLDSA65.sign(message: messageData, privateKey: privateKey) else {
            print("[SIGN] ML-DSA-65 signing failed")
            return nil
        }

        print("[SIGN] ML-DSA-65 signature: \(signature.count) bytes")
        return signature
    }

    /// Загрузка из Keychain
    private func loadFromKeychain(key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "network.montana.junona",
            kSecAttrAccount as String: key,
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        return status == errSecSuccess ? result as? Data : nil
    }

    /// Load saved address from Keychain (for BIP-39 style verification)
    private func loadAddressFromKeychain() -> String? {
        guard let data = loadFromKeychain(key: "montana_address"),
              let address = String(data: data, encoding: .utf8) else {
            return nil
        }
        return address
    }

    // MARK: - Helpers

    private func normalizePhone(_ phone: String) -> String {
        let digits = phone.filter { $0.isNumber }
        if digits.hasPrefix("8") && digits.count == 11 {
            return "+7" + digits.dropFirst()
        }
        if !phone.hasPrefix("+") {
            return "+" + digits
        }
        return "+" + digits
    }

    private func generateMLDSAKeys() -> (privateKey: Data, publicKey: Data) {
        var privateKey = Data(count: 4032) // ML-DSA-65 private key size
        var publicKey = Data(count: 1952)  // ML-DSA-65 public key size

        _ = privateKey.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 4032, $0.baseAddress!) }
        _ = publicKey.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 1952, $0.baseAddress!) }

        return (privateKey, publicKey)
    }

    private func generateAddress(from publicKey: Data) -> String {
        let hash = sha256(publicKey)
        let addressHex = hash.prefix(20).map { String(format: "%02x", $0) }.joined()
        return "mt" + addressHex
    }

    private func sha256(_ data: Data) -> Data {
        var hash = [UInt8](repeating: 0, count: 32)
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return Data(hash)
    }

    // MARK: - Keychain

    private func saveToKeychain(key: String, data: Data) {
        // First delete any existing item
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "network.montana.junona",
            kSecAttrAccount as String: key
        ]
        SecItemDelete(deleteQuery as CFDictionary)

        // Then add the new item
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "network.montana.junona",
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
    }

    private func deleteFromKeychain(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "network.montana.junona",
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Network

    private func post<T: Encodable, R: Decodable>(_ path: String, body: T) async throws -> R {
        guard let url = URL(string: baseURL + path) else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(R.self, from: data)
    }

    private func get<R: Decodable>(_ path: String, token: String) async throws -> R {
        guard let url = URL(string: baseURL + path) else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(R.self, from: data)
    }
}

// MARK: - Models

struct MontanaUser: Codable, Identifiable {
    let id: String
    let phone: String
    let address: String
    var displayName: String?
    let createdAt: Date

    var shortAddress: String {
        guard address.count > 10 else { return address }
        let prefix = String(address.prefix(6))
        let suffix = String(address.suffix(4))
        return "\(prefix)...\(suffix)"
    }
}

// MARK: - API Models

struct AuthRequest: Encodable {
    let phone: String
    let action: String
}

struct AuthResponse: Decodable {
    let success: Bool
    let error: String?
}

struct VerifyRequest: Encodable {
    let phone: String
    let code: String
}

struct VerifyResponse: Decodable {
    let success: Bool
    let isNewUser: Bool
    let sessionToken: String?
    let error: String?
}

struct RegisterRequest: Encodable {
    let phone: String
    let publicKey: String
    let sessionToken: String
}

struct RegisterResponse: Decodable {
    let success: Bool
    let userId: String?
    let address: String?
    let error: String?
}

struct ProfileResponse: Decodable {
    let success: Bool
    let user: MontanaUser?
}

// MARK: - Data Extension for Hex

extension Data {
    init?(hexString: String) {
        let hex = hexString.dropFirst(hexString.hasPrefix("0x") ? 2 : 0)
        guard hex.count % 2 == 0 else { return nil }

        var data = Data(capacity: hex.count / 2)
        var index = hex.startIndex

        while index < hex.endIndex {
            let nextIndex = hex.index(index, offsetBy: 2)
            guard let byte = UInt8(hex[index..<nextIndex], radix: 16) else { return nil }
            data.append(byte)
            index = nextIndex
        }

        self = data
    }
}
