//
//  MontanaCore.swift
//  Montana Protocol — Shared Core
//
//  Ɉ — Protocol of Ideal Money
//  Time is the only real currency
//

import Foundation
import SwiftUI

// MARK: - Montana Protocol Version

public struct Montana {
    public static let version = "1.9.3"
    public static let genesisDate = "2025-01-09"
    public static let symbol = "Ɉ"
    public static let cryptography = "ML-DSA-65 (FIPS 204)"

    /// Инициализация Montana Core
    public static func initialize() {
        print("🏔 Montana Protocol v\(version)")
        print("   Genesis: \(genesisDate)")
        print("   Crypto: \(cryptography)")
        print("   Symbol: \(symbol)")
    }
}

// MARK: - Shared Address Format

public struct MontanaAddress {
    public let raw: String

    public init?(_ string: String) {
        guard Self.isValid(string) else { return nil }
        self.raw = string
    }

    /// Проверка формата адреса: mt + 40 hex chars = 42 chars
    public static func isValid(_ address: String) -> Bool {
        guard address.count == 42 else { return false }
        guard address.hasPrefix("mt") else { return false }

        let hexPart = String(address.dropFirst(2))
        let validChars = CharacterSet(charactersIn: "0123456789abcdef")
        return hexPart.unicodeScalars.allSatisfy { validChars.contains($0) }
    }

    /// Сокращённый формат для отображения
    public var shortened: String {
        guard raw.count >= 10 else { return raw }
        return "\(raw.prefix(8))...\(raw.suffix(6))"
    }
}

// MARK: - Shared Theme

public struct MontanaTheme {
    public static let primary = Color(red: 0.29, green: 0.56, blue: 0.85)      // #4A90D9
    public static let secondary = Color(red: 0.55, green: 0.36, blue: 0.96)    // #8B5CF6
    public static let background = Color(red: 0.06, green: 0.06, blue: 0.10)   // #0F0F1A
    public static let cardBackground = Color(red: 0.10, green: 0.10, blue: 0.18) // #1A1A2E
    public static let success = Color(red: 0.06, green: 0.73, blue: 0.51)      // #10B981
    public static let warning = Color(red: 0.96, green: 0.62, blue: 0.04)      // #F59E0B
    public static let error = Color(red: 0.94, green: 0.27, blue: 0.27)        // #EF4444

    public static let textPrimary = Color.white
    public static let textSecondary = Color.gray
}

// MARK: - Cross-App Deep Links

public struct MontanaLinks {
    // URL Schemes для связи между приложениями
    public static let walletScheme = "montana-wallet"
    public static let junonaScheme = "montana-junona"
    public static let contractsScheme = "montana-contracts"

    /// Открыть кошелёк
    public static func openWallet(address: String? = nil) {
        var urlString = "\(walletScheme)://"
        if let address = address {
            urlString += "address/\(address)"
        }
        if let url = URL(string: urlString) {
            UIApplication.shared.open(url)
        }
    }

    /// Открыть Юнону
    public static func openJunona(message: String? = nil) {
        var urlString = "\(junonaScheme)://"
        if let message = message?.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) {
            urlString += "chat?message=\(message)"
        }
        if let url = URL(string: urlString) {
            UIApplication.shared.open(url)
        }
    }

    /// Открыть контракты
    public static func openContracts(contractId: String? = nil) {
        var urlString = "\(contractsScheme)://"
        if let id = contractId {
            urlString += "contract/\(id)"
        }
        if let url = URL(string: urlString) {
            UIApplication.shared.open(url)
        }
    }

    /// Проверка установлено ли приложение
    public static func isInstalled(_ scheme: String) -> Bool {
        guard let url = URL(string: "\(scheme)://") else { return false }
        return UIApplication.shared.canOpenURL(url)
    }
}

// MARK: - Shared Keychain

public class MontanaKeychain {
    public static let shared = MontanaKeychain()

    private let service = "network.montana.protocol"

    private init() {}

    public func save(key: String, data: Data) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            kSecAttrAccessGroup as String: "group.network.montana" // Shared between apps
        ]

        SecItemDelete(query as CFDictionary)
        return SecItemAdd(query as CFDictionary, nil) == errSecSuccess
    }

    public func load(key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecAttrAccessGroup as String: "group.network.montana",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess else { return nil }
        return result as? Data
    }

    public func delete(key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecAttrAccessGroup as String: "group.network.montana"
        ]

        return SecItemDelete(query as CFDictionary) == errSecSuccess
    }

    // Convenience methods for wallet
    public var walletAddress: String? {
        get {
            guard let data = load(key: "wallet_address") else { return nil }
            return String(data: data, encoding: .utf8)
        }
        set {
            if let value = newValue, let data = value.data(using: .utf8) {
                _ = save(key: "wallet_address", data: data)
            } else {
                _ = delete(key: "wallet_address")
            }
        }
    }

    public var privateKey: Data? {
        get { load(key: "private_key") }
        set {
            if let data = newValue {
                _ = save(key: "private_key", data: data)
            } else {
                _ = delete(key: "private_key")
            }
        }
    }

    public var publicKey: Data? {
        get { load(key: "public_key") }
        set {
            if let data = newValue {
                _ = save(key: "public_key", data: data)
            } else {
                _ = delete(key: "public_key")
            }
        }
    }
}

// MARK: - Privacy Levels (Уровни приватности)

/// Уровень приватности для папок и данных
/// ИНТИМНОЕ по умолчанию — постквантовое шифрование
public enum PrivacyLevel: String, CaseIterable, Identifiable, Codable {
    case intimate = "intimate"      // Интимное — ML-KEM-768 + ChaCha20 (постквантовое)
    case `private` = "private"      // Приватное — E2E шифрование
    case `public` = "public"        // Публичное — открытое

    public var id: String { rawValue }

    /// Русское название
    public var displayName: String {
        switch self {
        case .intimate: return "Интимное"
        case .private: return "Приватное"
        case .public: return "Публичное"
        }
    }

    /// Иконка SF Symbols
    public var icon: String {
        switch self {
        case .intimate: return "lock.shield.fill"
        case .private: return "lock.fill"
        case .public: return "globe"
        }
    }

    /// Цвет уровня
    public var color: Color {
        switch self {
        case .intimate: return MontanaTheme.secondary   // Фиолетовый — постквантово
        case .private: return MontanaTheme.primary      // Синий — E2E
        case .public: return MontanaTheme.warning       // Оранжевый — открытое
        }
    }

    /// Описание шифрования
    public var encryptionDescription: String {
        switch self {
        case .intimate: return "ML-KEM-768 + ChaCha20-Poly1305 (постквантовое)"
        case .private: return "E2E шифрование"
        case .public: return "Без шифрования"
        }
    }

    /// По умолчанию — ИНТИМНОЕ
    public static var `default`: PrivacyLevel { .intimate }
}

// MARK: - Folder Model

/// Модель папки с уровнем приватности
public struct MontanaFolder: Identifiable, Codable {
    public let id: UUID
    public var name: String
    public var privacyLevel: PrivacyLevel
    public var createdAt: Date
    public var updatedAt: Date
    public var itemCount: Int

    public init(
        id: UUID = UUID(),
        name: String,
        privacyLevel: PrivacyLevel = .intimate,  // По умолчанию ИНТИМНОЕ
        createdAt: Date = Date(),
        updatedAt: Date = Date(),
        itemCount: Int = 0
    ) {
        self.id = id
        self.name = name
        self.privacyLevel = privacyLevel
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.itemCount = itemCount
    }
}

// MARK: - Folder Item Model

/// Элемент в папке (файл, заметка, медиа)
public struct MontanaFolderItem: Identifiable, Codable {
    public let id: UUID
    public var name: String
    public var type: ItemType
    public var folderId: UUID
    public var createdAt: Date
    public var encryptedData: Data?  // Зашифрованные данные

    public enum ItemType: String, Codable {
        case note = "note"
        case photo = "photo"
        case video = "video"
        case audio = "audio"
        case file = "file"

        public var icon: String {
            switch self {
            case .note: return "doc.text"
            case .photo: return "photo"
            case .video: return "video"
            case .audio: return "waveform"
            case .file: return "doc"
            }
        }
    }

    public init(
        id: UUID = UUID(),
        name: String,
        type: ItemType,
        folderId: UUID,
        createdAt: Date = Date(),
        encryptedData: Data? = nil
    ) {
        self.id = id
        self.name = name
        self.type = type
        self.folderId = folderId
        self.createdAt = createdAt
        self.encryptedData = encryptedData
    }
}

// MARK: - Folder Storage Manager

/// Менеджер хранения папок
public class MontanaFolderStorage: ObservableObject {
    public static let shared = MontanaFolderStorage()

    @Published public var folders: [MontanaFolder] = []

    private let foldersKey = "montana_folders"

    private init() {
        loadFolders()
    }

    /// Создать папку (по умолчанию ИНТИМНОЕ)
    public func createFolder(name: String, privacyLevel: PrivacyLevel = .intimate) -> MontanaFolder {
        let folder = MontanaFolder(name: name, privacyLevel: privacyLevel)
        folders.append(folder)
        saveFolders()
        return folder
    }

    /// Удалить папку
    public func deleteFolder(_ folder: MontanaFolder) {
        folders.removeAll { $0.id == folder.id }
        saveFolders()
    }

    /// Обновить папку
    public func updateFolder(_ folder: MontanaFolder) {
        if let index = folders.firstIndex(where: { $0.id == folder.id }) {
            var updated = folder
            updated.updatedAt = Date()
            folders[index] = updated
            saveFolders()
        }
    }

    private func loadFolders() {
        guard let data = MontanaKeychain.shared.load(key: foldersKey),
              let decoded = try? JSONDecoder().decode([MontanaFolder].self, from: data) else {
            // Создаём папки по умолчанию
            folders = [
                MontanaFolder(name: "Личное", privacyLevel: .intimate),
                MontanaFolder(name: "Заметки", privacyLevel: .intimate),
                MontanaFolder(name: "Медиа", privacyLevel: .private)
            ]
            saveFolders()
            return
        }
        folders = decoded
    }

    private func saveFolders() {
        guard let data = try? JSONEncoder().encode(folders) else { return }
        _ = MontanaKeychain.shared.save(key: foldersKey, data: data)
    }
}

// MARK: - Contact Model

/// Контакт Montana
public struct MontanaContact: Identifiable, Codable {
    public let id: UUID
    public var name: String
    public var address: String?  // mt... адрес
    public var phone: String?    // номер телефона
    public var avatar: Data?
    public var createdAt: Date

    public init(
        id: UUID = UUID(),
        name: String,
        address: String? = nil,
        phone: String? = nil,
        avatar: Data? = nil,
        createdAt: Date = Date()
    ) {
        self.id = id
        self.name = name
        self.address = address
        self.phone = phone
        self.avatar = avatar
        self.createdAt = createdAt
    }

    /// Сокращённый адрес
    public var shortAddress: String? {
        guard let addr = address else { return nil }
        return MontanaAddress(addr)?.shortened
    }

    /// Форматированный телефон
    public var formattedPhone: String? {
        guard let p = phone else { return nil }
        return p
    }

    /// Можно ли отправить (есть адрес или телефон)
    public var canSend: Bool {
        return address != nil || phone != nil
    }
}

// MARK: - Contact Storage Manager

/// Менеджер контактов
public class MontanaContactStorage: ObservableObject {
    public static let shared = MontanaContactStorage()

    @Published public var contacts: [MontanaContact] = []

    private let contactsKey = "montana_contacts"

    private init() {
        loadContacts()
    }

    public func addContact(name: String, address: String? = nil, phone: String? = nil, avatar: Data? = nil) -> MontanaContact {
        let contact = MontanaContact(name: name, address: address, phone: phone, avatar: avatar)
        contacts.append(contact)
        saveContacts()
        return contact
    }

    public func updateContact(_ contact: MontanaContact) {
        if let index = contacts.firstIndex(where: { $0.id == contact.id }) {
            contacts[index] = contact
            saveContacts()
        }
    }

    public func findByPhone(_ phone: String) -> MontanaContact? {
        let normalized = phone.replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: "(", with: "")
            .replacingOccurrences(of: ")", with: "")
        return contacts.first {
            guard let p = $0.phone else { return false }
            let normalizedP = p.replacingOccurrences(of: " ", with: "")
                .replacingOccurrences(of: "-", with: "")
                .replacingOccurrences(of: "(", with: "")
                .replacingOccurrences(of: ")", with: "")
            return normalizedP == normalized || normalizedP.hasSuffix(normalized) || normalized.hasSuffix(normalizedP)
        }
    }

    public func deleteContact(_ contact: MontanaContact) {
        contacts.removeAll { $0.id == contact.id }
        saveContacts()
    }

    private func loadContacts() {
        guard let data = MontanaKeychain.shared.load(key: contactsKey),
              let decoded = try? JSONDecoder().decode([MontanaContact].self, from: data) else {
            contacts = []
            return
        }
        contacts = decoded
    }

    private func saveContacts() {
        guard let data = try? JSONEncoder().encode(contacts) else { return }
        _ = MontanaKeychain.shared.save(key: contactsKey, data: data)
    }
}

// MARK: - App Entitlements Info

/*
 Для работы Shared Keychain между 3 приложениями нужно:

 1. Все 3 приложения должны иметь одинаковый App Group:
    - group.network.montana

 2. Entitlements файл для каждого приложения:

 <?xml version="1.0" encoding="UTF-8"?>
 <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
 <plist version="1.0">
 <dict>
     <key>com.apple.security.application-groups</key>
     <array>
         <string>group.network.montana</string>
     </array>
     <key>keychain-access-groups</key>
     <array>
         <string>$(AppIdentifierPrefix)group.network.montana</string>
     </array>
 </dict>
 </plist>

 3. URL Schemes в Info.plist:
    - Montana Wallet: montana-wallet
    - Junona AI: montana-junona
    - Montana Contracts: montana-contracts
*/
