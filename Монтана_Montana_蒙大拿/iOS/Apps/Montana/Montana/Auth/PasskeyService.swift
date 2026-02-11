//
//  PasskeyService.swift
//  Montana — Post-Quantum Wallet
//
//  Passkey integration for device-local authentication
//  Cognitive Key = master backup (cross-device)
//  Passkey = Face ID / Touch ID convenience (same device)
//

import Foundation
import AuthenticationServices
import LocalAuthentication

/// Passkey service for device-local biometric authentication
/// Works alongside Cognitive Key (not replacement)
@MainActor
public class PasskeyService: NSObject, ObservableObject {

    public static let shared = PasskeyService()

    // MARK: - Published State

    @Published public var isPasskeyAvailable = false
    @Published public var hasPasskey = false
    @Published public var error: String?

    // MARK: - Private

    private let context = LAContext()
    private var authCompletion: ((Bool) -> Void)?

    // Relying Party ID (your domain)
    private let relyingPartyID = "montana.network"

    // MARK: - Init

    private override init() {
        super.init()
        checkBiometricAvailability()
        checkExistingPasskey()
    }

    // MARK: - Biometric Check

    /// Check if device supports biometrics
    private func checkBiometricAvailability() {
        var error: NSError?
        isPasskeyAvailable = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)

        if let error = error {
            print("[Passkey] Biometrics not available: \(error.localizedDescription)")
        } else {
            let biometryType = context.biometryType
            print("[Passkey] Biometrics available: \(biometryType == .faceID ? "Face ID" : "Touch ID")")
        }
    }

    /// Check if passkey already exists for this device
    private func checkExistingPasskey() {
        hasPasskey = UserDefaults.standard.bool(forKey: "montana_has_passkey")
    }

    // MARK: - Create Passkey

    /// Create passkey after cognitive key registration
    /// Links biometric auth to the Montana address
    public func createPasskey(for address: String) async -> Bool {
        guard isPasskeyAvailable else {
            error = "Biometrics not available"
            return false
        }

        // Store address reference in Keychain with biometric protection
        let success = saveToKeychainWithBiometrics(
            key: "montana_passkey_address",
            value: address.data(using: .utf8)!
        )

        if success {
            hasPasskey = true
            UserDefaults.standard.set(true, forKey: "montana_has_passkey")
            UserDefaults.standard.set(address, forKey: "montana_passkey_linked_address")
            print("[Passkey] Created for address: \(address)")
        }

        return success
    }

    // MARK: - Authenticate with Passkey

    /// Authenticate using Face ID / Touch ID
    /// Returns the Montana address if successful
    public func authenticate() async -> String? {
        guard hasPasskey else {
            error = "No passkey configured"
            return nil
        }

        // Read address from biometric-protected Keychain
        guard let addressData = readFromKeychainWithBiometrics(key: "montana_passkey_address"),
              let address = String(data: addressData, encoding: .utf8) else {
            error = "Failed to read passkey"
            return nil
        }

        print("[Passkey] Authenticated: \(address)")
        return address
    }

    /// Quick check if can authenticate with passkey
    public func canAuthenticateWithPasskey() -> Bool {
        return isPasskeyAvailable && hasPasskey
    }

    // MARK: - Remove Passkey

    /// Remove passkey (user must use cognitive key to restore)
    public func removePasskey() {
        deleteFromKeychain(key: "montana_passkey_address")
        hasPasskey = false
        UserDefaults.standard.set(false, forKey: "montana_has_passkey")
        UserDefaults.standard.removeObject(forKey: "montana_passkey_linked_address")
        print("[Passkey] Removed")
    }

    // MARK: - Cognitive Key Storage (Biometric Protected)

    /// Store cognitive key with biometric protection
    /// Like Trust Wallet / MetaMask - user can view seed with Face ID
    public func storeCognitiveKey(_ key: String) -> Bool {
        guard let keyData = key.data(using: .utf8) else { return false }
        let success = saveToKeychainWithBiometrics(key: "montana_cognitive_key", value: keyData)
        if success {
            UserDefaults.standard.set(true, forKey: "montana_has_stored_seed")
            print("[Passkey] Cognitive key stored securely")
        }
        return success
    }

    /// Retrieve cognitive key (requires Face ID)
    /// Returns nil if biometric auth fails
    public func retrieveCognitiveKey() -> String? {
        guard let keyData = readFromKeychainWithBiometrics(key: "montana_cognitive_key"),
              let key = String(data: keyData, encoding: .utf8) else {
            return nil
        }
        return key
    }

    /// Check if cognitive key is stored
    public var hasCognitiveKeyStored: Bool {
        return UserDefaults.standard.bool(forKey: "montana_has_stored_seed")
    }

    /// Delete stored cognitive key
    public func deleteCognitiveKey() {
        deleteFromKeychain(key: "montana_cognitive_key")
        UserDefaults.standard.set(false, forKey: "montana_has_stored_seed")
        print("[Passkey] Cognitive key deleted")
    }

    // MARK: - Keychain with Biometrics

    /// Save to Keychain with biometric protection
    private func saveToKeychainWithBiometrics(key: String, value: Data) -> Bool {
        // Create access control with biometric requirement
        guard let accessControl = SecAccessControlCreateWithFlags(
            nil,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            .biometryCurrentSet,
            nil
        ) else {
            print("[Passkey] Failed to create access control")
            return false
        }

        // Delete existing item first
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecAttrService as String: "network.montana.passkey"
        ]
        SecItemDelete(deleteQuery as CFDictionary)

        // Add new item with biometric protection
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecAttrService as String: "network.montana.passkey",
            kSecValueData as String: value,
            kSecAttrAccessControl as String: accessControl
        ]

        let status = SecItemAdd(query as CFDictionary, nil)

        if status == errSecSuccess {
            return true
        } else {
            print("[Passkey] Keychain save failed: \(status)")
            return false
        }
    }

    /// Read from Keychain with biometric prompt
    private func readFromKeychainWithBiometrics(key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecAttrService as String: "network.montana.passkey",
            kSecReturnData as String: true,
            kSecUseOperationPrompt as String: "Войти в Montana"
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        if status == errSecSuccess {
            return result as? Data
        } else {
            print("[Passkey] Keychain read failed: \(status)")
            return nil
        }
    }

    /// Delete from Keychain
    private func deleteFromKeychain(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecAttrService as String: "network.montana.passkey"
        ]
        SecItemDelete(query as CFDictionary)
    }
}

// MARK: - Biometry Type Extension

extension LABiometryType: CustomStringConvertible {
    public var description: String {
        switch self {
        case .none: return "None"
        case .touchID: return "Touch ID"
        case .faceID: return "Face ID"
        case .opticID: return "Optic ID"
        @unknown default: return "Unknown"
        }
    }
}
