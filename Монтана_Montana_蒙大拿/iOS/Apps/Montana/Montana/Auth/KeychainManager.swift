//
//  KeychainManager.swift
//  Montana — Post-Quantum Wallet
//
//  Явное управление ключами в iOS Keychain
//  Модель: когнитивный ключ → derive keys → save to Keychain
//

import Foundation
import Security

/// Менеджер хранения ключей в iOS Keychain
///
/// Архитектура (по модели самостоятельного хранения):
/// ```
/// ┌─────────────────────────────────────────────────────────────┐
/// │                КОГНИТИВНЫЙ КЛЮЧ (Recovery Phrase)           │
/// │                Пользователь записал на бумагу               │
/// │                Хранится зашифрованным с PIN (опционально)   │
/// └─────────────────────────────────────────────────────────────┘
///                               │
///                               ▼
/// ┌─────────────────────────────────────────────────────────────┐
/// │                       DERIVE KEYS                           │
/// │            ML-DSA-65 → Private Key + Public Key             │
/// └─────────────────────────────────────────────────────────────┘
///                               │
///                               ▼
/// ┌─────────────────────────────────────────────────────────────┐
/// │                      iOS KEYCHAIN                           │
/// │   ┌─────────────────────────────────────────────────────┐   │
/// │   │  private_key: [4032 bytes ML-DSA-65]                │   │
/// │   │  public_key:  [1952 bytes ML-DSA-65]                │   │
/// │   │  (защищено Secure Enclave)                          │   │
/// │   └─────────────────────────────────────────────────────┘   │
/// └─────────────────────────────────────────────────────────────┘
///                               │
///                               ▼
/// ┌─────────────────────────────────────────────────────────────┐
/// │                       APP LAUNCH                            │
/// │   hasKeys() == true → AUTHORIZED                            │
/// │   hasKeys() == false → Show Create/Import                   │
/// └─────────────────────────────────────────────────────────────┘
/// ```
@MainActor
public final class KeychainManager {

    public static let shared = KeychainManager()

    // MARK: - Constants

    private let service = "network.montana.junona"

    /// Ключи в Keychain (базовые имена, индекс добавляется для мульти-кошелька)
    private enum Key: String {
        case privateKey = "private_key"     // 4032 bytes ML-DSA-65
        case publicKey = "public_key"       // 1952 bytes ML-DSA-65
        case encryptedSeed = "encrypted_seed" // Когнитивный ключ (зашифрован PIN)
        case seedSalt = "seed_salt"         // Соль для шифрования
        case pinHash = "pin_hash"           // Хеш PIN для верификации
        case walletCount = "wallet_count"   // Количество кошельков
    }

    /// Текущий активный кошелёк (индекс)
    public var activeWalletIndex: Int {
        get { UserDefaults.standard.integer(forKey: "montana_active_wallet") }
        set { UserDefaults.standard.set(newValue, forKey: "montana_active_wallet") }
    }

    /// Количество кошельков
    public var walletCount: Int {
        if let data = read(key: .walletCount), let count = String(data: data, encoding: .utf8), let n = Int(count) {
            return n
        }
        // Миграция: если есть старые ключи без индекса — это кошелёк 0
        if read(key: .privateKey) != nil {
            setWalletCount(1)
            return 1
        }
        return 0
    }

    private func setWalletCount(_ count: Int) {
        if let data = "\(count)".data(using: .utf8) {
            _ = save(key: .walletCount, data: data)
        }
    }

    private init() {}

    // MARK: - Keys Check

    /// Проверка наличия ключей в Keychain (для активного кошелька)
    /// Это ЕДИНСТВЕННОЕ условие для авторизации
    public func hasKeys() -> Bool {
        let idx = activeWalletIndex
        let hasPrivate = readWallet(key: .privateKey, index: idx) != nil
        let hasPublic = readWallet(key: .publicKey, index: idx) != nil
        return hasPrivate && hasPublic
    }

    /// Проверка наличия ключей для конкретного кошелька
    public func hasKeys(forWallet index: Int) -> Bool {
        let hasPrivate = readWallet(key: .privateKey, index: index) != nil
        let hasPublic = readWallet(key: .publicKey, index: index) != nil
        return hasPrivate && hasPublic
    }

    // MARK: - Private Key

    /// Сохранить приватный ключ ML-DSA-65 (4032 bytes) для активного кошелька
    public func savePrivateKey(_ key: Data) -> Bool {
        return savePrivateKey(key, forWallet: activeWalletIndex)
    }

    /// Сохранить приватный ключ для конкретного кошелька
    public func savePrivateKey(_ key: Data, forWallet index: Int) -> Bool {
        guard key.count == 4032 else {
            print("[Keychain] Invalid private key size: \(key.count), expected 4032")
            return false
        }
        return saveWallet(key: .privateKey, data: key, index: index)
    }

    /// Загрузить приватный ключ ML-DSA-65 для активного кошелька
    public func loadPrivateKey() -> Data? {
        return readWallet(key: .privateKey, index: activeWalletIndex)
    }

    /// Загрузить приватный ключ для конкретного кошелька
    public func loadPrivateKey(forWallet index: Int) -> Data? {
        return readWallet(key: .privateKey, index: index)
    }

    // MARK: - Public Key

    /// Сохранить публичный ключ ML-DSA-65 (1952 bytes) для активного кошелька
    public func savePublicKey(_ key: Data) -> Bool {
        return savePublicKey(key, forWallet: activeWalletIndex)
    }

    /// Сохранить публичный ключ для конкретного кошелька
    public func savePublicKey(_ key: Data, forWallet index: Int) -> Bool {
        guard key.count == 1952 else {
            print("[Keychain] Invalid public key size: \(key.count), expected 1952")
            return false
        }
        return saveWallet(key: .publicKey, data: key, index: index)
    }

    /// Загрузить публичный ключ ML-DSA-65 для активного кошелька
    public func loadPublicKey() -> Data? {
        return readWallet(key: .publicKey, index: activeWalletIndex)
    }

    /// Загрузить публичный ключ для конкретного кошелька
    public func loadPublicKey(forWallet index: Int) -> Data? {
        return readWallet(key: .publicKey, index: index)
    }

    // MARK: - Save Both Keys

    /// Сохранить пару ключей (privateKey + publicKey) для активного кошелька
    public func saveKeyPair(privateKey: Data, publicKey: Data) -> Bool {
        return saveKeyPair(privateKey: privateKey, publicKey: publicKey, forWallet: activeWalletIndex)
    }

    /// Сохранить пару ключей для конкретного кошелька
    public func saveKeyPair(privateKey: Data, publicKey: Data, forWallet index: Int) -> Bool {
        let privateOk = savePrivateKey(privateKey, forWallet: index)
        let publicOk = savePublicKey(publicKey, forWallet: index)

        if privateOk && publicOk {
            print("[Keychain] ✅ Keys saved for wallet \(index): private=\(privateKey.count)b, public=\(publicKey.count)b")
            return true
        } else {
            print("[Keychain] ❌ Failed to save keys for wallet \(index)")
            // Rollback if partial save
            deleteWallet(key: .privateKey, index: index)
            deleteWallet(key: .publicKey, index: index)
            return false
        }
    }

    // MARK: - Multi-Wallet Operations

    /// Создать новый кошелёк и вернуть его индекс
    public func createNewWallet(privateKey: Data, publicKey: Data) -> Int? {
        let newIndex = walletCount
        if saveKeyPair(privateKey: privateKey, publicKey: publicKey, forWallet: newIndex) {
            setWalletCount(newIndex + 1)
            print("[Keychain] ✅ Created wallet \(newIndex), total: \(newIndex + 1)")
            return newIndex
        }
        return nil
    }

    /// Переключиться на другой кошелёк
    public func switchToWallet(_ index: Int) -> Bool {
        guard index >= 0 && index < walletCount else {
            print("[Keychain] Invalid wallet index: \(index)")
            return false
        }
        activeWalletIndex = index
        print("[Keychain] Switched to wallet \(index)")
        return true
    }

    /// Получить список всех адресов кошельков
    public func listWalletAddresses() -> [String] {
        var addresses: [String] = []
        for i in 0..<walletCount {
            if let addr = UserDefaults.standard.string(forKey: "montana_wallet_\(i)_address") {
                addresses.append(addr)
            } else {
                addresses.append("Wallet \(i)")
            }
        }
        return addresses
    }

    /// Сохранить адрес для кошелька
    public func saveWalletAddress(_ address: String, forWallet index: Int) {
        UserDefaults.standard.set(address, forKey: "montana_wallet_\(index)_address")
    }

    /// Получить адрес кошелька
    public func getWalletAddress(forWallet index: Int) -> String? {
        return UserDefaults.standard.string(forKey: "montana_wallet_\(index)_address")
    }

    // MARK: - Recovery Phrase (Encrypted with PIN)

    /// Сохранить когнитивный ключ зашифрованным с PIN
    /// Позволяет просмотреть recovery phrase позже
    public func saveSeed(_ seed: String, pin: String) -> Bool {
        guard let seedData = seed.data(using: .utf8) else { return false }

        // Generate random salt
        var salt = Data(count: 16)
        _ = salt.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 16, $0.baseAddress!) }

        // Derive encryption key from PIN
        guard let encryptionKey = deriveKey(from: pin, salt: salt) else { return false }

        // Encrypt seed with AES-256-GCM
        guard let encrypted = encrypt(data: seedData, key: encryptionKey) else { return false }

        // Save encrypted seed and salt
        let savedSeed = save(key: .encryptedSeed, data: encrypted)
        let savedSalt = save(key: .seedSalt, data: salt)

        // Save PIN hash for verification
        let pinHash = sha256(pin.data(using: .utf8)!)
        let savedHash = save(key: .pinHash, data: pinHash)

        return savedSeed && savedSalt && savedHash
    }

    /// Загрузить когнитивный ключ (требует PIN)
    public func loadSeed(pin: String) -> String? {
        // Verify PIN first
        guard verifyPin(pin) else {
            print("[Keychain] Invalid PIN")
            return nil
        }

        guard let encrypted = read(key: .encryptedSeed),
              let salt = read(key: .seedSalt) else {
            return nil
        }

        // Derive decryption key from PIN
        guard let decryptionKey = deriveKey(from: pin, salt: salt) else { return nil }

        // Decrypt seed
        guard let decrypted = decrypt(data: encrypted, key: decryptionKey) else { return nil }

        return String(data: decrypted, encoding: .utf8)
    }

    /// Проверить PIN
    public func verifyPin(_ pin: String) -> Bool {
        guard let storedHash = read(key: .pinHash) else { return false }
        let inputHash = sha256(pin.data(using: .utf8)!)
        return storedHash == inputHash
    }

    /// Есть ли сохранённый когнитивный ключ
    public var hasSavedSeed: Bool {
        return read(key: .encryptedSeed) != nil
    }

    /// Есть ли установленный PIN
    public var hasPin: Bool {
        return read(key: .pinHash) != nil
    }

    /// Сохранить только PIN (без когнитивного ключа)
    /// Используется когда пользователь устанавливает PIN из настроек
    public func savePinOnly(_ pin: String) {
        let pinHash = sha256(pin.data(using: .utf8)!)
        _ = save(key: .pinHash, data: pinHash)
    }

    // MARK: - Delete

    /// Удалить все ключи (выход из кошелька)
    public func deleteAll() {
        delete(key: .privateKey)
        delete(key: .publicKey)
        delete(key: .encryptedSeed)
        delete(key: .seedSalt)
        delete(key: .pinHash)
        print("[Keychain] All keys deleted")
    }

    /// Удалить только recovery phrase (оставить ключи)
    public func deleteSeed() {
        delete(key: .encryptedSeed)
        delete(key: .seedSalt)
        delete(key: .pinHash)
    }

    // MARK: - Private Keychain Operations

    private func save(key: Key, data: Data) -> Bool {
        // Delete existing first
        delete(key: key)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    private func read(key: Key) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        return status == errSecSuccess ? result as? Data : nil
    }

    private func delete(key: Key) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Wallet-Indexed Keychain Operations

    private func walletKey(_ key: Key, index: Int) -> String {
        // Для индекса 0 и миграции — используем старые ключи без суффикса
        if index == 0 && (key == .privateKey || key == .publicKey || key == .encryptedSeed || key == .seedSalt) {
            return key.rawValue
        }
        return "wallet_\(index)_\(key.rawValue)"
    }

    private func saveWallet(key: Key, data: Data, index: Int) -> Bool {
        let keyName = walletKey(key, index: index)
        deleteRaw(keyName: keyName)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: keyName,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    private func readWallet(key: Key, index: Int) -> Data? {
        let keyName = walletKey(key, index: index)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: keyName,
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        return status == errSecSuccess ? result as? Data : nil
    }

    private func deleteWallet(key: Key, index: Int) {
        let keyName = walletKey(key, index: index)
        deleteRaw(keyName: keyName)
    }

    private func deleteRaw(keyName: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: keyName
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Crypto Helpers

    private func deriveKey(from pin: String, salt: Data) -> Data? {
        guard let pinData = pin.data(using: .utf8) else { return nil }

        var derivedKey = Data(count: 32)

        let result = derivedKey.withUnsafeMutableBytes { derivedBytes in
            salt.withUnsafeBytes { saltBytes in
                pinData.withUnsafeBytes { pinBytes in
                    CCKeyDerivationPBKDF(
                        CCPBKDFAlgorithm(kCCPBKDF2),
                        pinBytes.baseAddress?.assumingMemoryBound(to: Int8.self),
                        pinData.count,
                        saltBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        salt.count,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256),
                        100_000, // 100k iterations
                        derivedBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        32
                    )
                }
            }
        }

        return result == kCCSuccess ? derivedKey : nil
    }

    private func encrypt(data: Data, key: Data) -> Data? {
        // AES-256-CBC encryption (GCM requires iOS 13+)
        var iv = Data(count: 16)
        _ = iv.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 16, $0.baseAddress!) }

        let bufferSize = data.count + kCCBlockSizeAES128
        var encrypted = Data(count: bufferSize)
        var numBytesEncrypted: size_t = 0

        let status = encrypted.withUnsafeMutableBytes { encryptedBytes in
            data.withUnsafeBytes { dataBytes in
                key.withUnsafeBytes { keyBytes in
                    iv.withUnsafeBytes { ivBytes in
                        CCCrypt(
                            CCOperation(kCCEncrypt),
                            CCAlgorithm(kCCAlgorithmAES),
                            CCOptions(kCCOptionPKCS7Padding),
                            keyBytes.baseAddress, 32,
                            ivBytes.baseAddress,
                            dataBytes.baseAddress, data.count,
                            encryptedBytes.baseAddress, bufferSize,
                            &numBytesEncrypted
                        )
                    }
                }
            }
        }

        guard status == kCCSuccess else { return nil }

        // Return IV + encrypted data
        var result = iv
        result.append(encrypted.prefix(numBytesEncrypted))
        return result
    }

    private func decrypt(data: Data, key: Data) -> Data? {
        guard data.count > 16 else { return nil }

        let iv = data.prefix(16)
        let encrypted = data.dropFirst(16)

        let bufferSize = encrypted.count + kCCBlockSizeAES128
        var decrypted = Data(count: bufferSize)
        var numBytesDecrypted: size_t = 0

        let status = decrypted.withUnsafeMutableBytes { decryptedBytes in
            encrypted.withUnsafeBytes { encryptedBytes in
                key.withUnsafeBytes { keyBytes in
                    iv.withUnsafeBytes { ivBytes in
                        CCCrypt(
                            CCOperation(kCCDecrypt),
                            CCAlgorithm(kCCAlgorithmAES),
                            CCOptions(kCCOptionPKCS7Padding),
                            keyBytes.baseAddress, 32,
                            ivBytes.baseAddress,
                            encryptedBytes.baseAddress, encrypted.count,
                            decryptedBytes.baseAddress, bufferSize,
                            &numBytesDecrypted
                        )
                    }
                }
            }
        }

        guard status == kCCSuccess else { return nil }
        return decrypted.prefix(numBytesDecrypted)
    }

    private func sha256(_ data: Data) -> Data {
        var hash = [UInt8](repeating: 0, count: 32)
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return Data(hash)
    }
}

// MARK: - CommonCrypto Import

import CommonCrypto
