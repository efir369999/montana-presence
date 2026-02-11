//
//  MontanaSeed.swift
//  Montana Protocol
//
//  Детерминистическая генерация ключей
//  "Когнитивный ключ = Seed Phrase. Сервер не нужен."
//
//  Постквантовая криптография:
//  - Когнитивный ключ (ONE memory phrase) = уникальная фраза пользователя
//  - PBKDF2 → Master Seed
//  - Детерминистический RNG → ML-DSA-65 keypair
//  - Тот же когнитивный ключ → те же ключи, ВСЕГДА
//
//  СЕРВЕР НЕ НУЖЕН ДЛЯ ВОССТАНОВЛЕНИЯ!
//

import Foundation
import CommonCrypto

/// Global state for deterministic RNG (required for C callback)
private var deterministicRNGState: DeterministicRNGState?

/// State for SHA256-CTR deterministic PRNG
private class DeterministicRNGState {
    var seed: Data      // 32-byte seed
    var counter: UInt64 // Counter for CTR mode

    init(seed: Data) {
        self.seed = seed
        self.counter = 0
    }

    deinit {
        // SECURITY: Always zero seed on deallocation
        secureWipe()
    }

    /// Secure memory wipe - zeros all sensitive data
    func secureWipe() {
        // Overwrite seed with zeros
        let zeroData = Data(repeating: 0, count: seed.count)
        seed = zeroData
        counter = 0
    }

    /// Generate next 32 bytes using SHA256(seed || counter)
    func nextBlock() -> Data {
        var input = seed
        var counterBytes = counter.bigEndian
        input.append(Data(bytes: &counterBytes, count: 8))
        counter += 1

        var hash = [UInt8](repeating: 0, count: 32)
        input.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(input.count), &hash)
        }
        return Data(hash)
    }

    /// Fill buffer with deterministic bytes
    func fill(_ buffer: UnsafeMutablePointer<UInt8>, count: Int) {
        var remaining = count
        var offset = 0

        while remaining > 0 {
            let block = nextBlock()
            let bytesToCopy = min(remaining, 32)
            block.withUnsafeBytes { (blockPtr: UnsafeRawBufferPointer) in
                for i in 0..<bytesToCopy {
                    buffer[offset + i] = blockPtr[i]
                }
            }
            offset += bytesToCopy
            remaining -= bytesToCopy
        }
    }
}

/// C callback for liboqs custom RNG
private func deterministicRNGCallback(_ buffer: UnsafeMutablePointer<UInt8>?, _ count: Int) {
    guard let buffer = buffer, let state = deterministicRNGState else { return }
    state.fill(buffer, count: count)
}

// MARK: - Montana Seed

/// Montana Post-Quantum Seed — Детерминистическая генерация ключей
///
/// Когнитивный ключ — это seed phrase. Тот же ключ = тот же кошелёк, всегда.
/// Сервер не нужен для восстановления — всё локально.
public struct MontanaSeed {

    // MARK: - Constants

    /// Protocol version for future upgrades
    /// V1: ML-DSA-65 + PBKDF2-SHA256 + SHA256-CTR RNG
    public static let protocolVersion: UInt8 = 1

    /// Master seed size: 32 bytes (256 bits)
    public static let masterSeedSize = 32

    /// Fixed salt includes version
    /// Security comes from cognitive key entropy (~248 bits), not salt
    private static let seedSalt = "MONTANA_SEED_V\(protocolVersion)".data(using: .utf8)!

    /// PBKDF2 iterations - high because we want maximum security
    private static let iterations: UInt32 = 600_000

    // MARK: - Seed Derivation

    /// Derive master seed from cognitive key
    /// DETERMINISTIC: Same cognitive key → same seed, ALWAYS
    ///
    /// - Parameter cognitiveKey: The user's cognitive key (one memory phrase)
    /// - Returns: 32-byte master seed
    public static func deriveMasterSeed(from cognitiveKey: String) -> Data? {
        // Normalize: trim whitespace, lowercase
        let normalized = cognitiveKey
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()

        guard !normalized.isEmpty else {
            print("[MontanaSeed] Empty cognitive key")
            return nil
        }

        // PBKDF2 to derive 32-byte seed
        guard let seed = pbkdf2(
            password: normalized,
            salt: seedSalt,
            iterations: iterations,
            keyLength: masterSeedSize
        ) else {
            print("[MontanaSeed] PBKDF2 failed")
            return nil
        }

        print("[MontanaSeed] Derived master seed: \(seed.count) bytes")
        return seed
    }

    // MARK: - Deterministic Key Generation

    /// Generate ML-DSA-65 keypair DETERMINISTICALLY from cognitive key
    /// Тот же ключ → те же ключи, всегда
    ///
    /// - Parameter cognitiveKey: The user's cognitive key
    /// - Returns: (privateKey, publicKey) tuple, or nil on error
    public static func deriveKeypair(from cognitiveKey: String) -> (privateKey: Data, publicKey: Data)? {
        // 1. Derive master seed
        guard let seed = deriveMasterSeed(from: cognitiveKey) else {
            return nil
        }

        // 2. Set deterministic RNG
        deterministicRNGState = DeterministicRNGState(seed: seed)
        OQS_randombytes_custom_algorithm(deterministicRNGCallback)

        defer {
            // 4. SECURITY: Zero seed before releasing (side-channel protection)
            deterministicRNGState?.secureWipe()
            // 5. ALWAYS reset to system RNG after keygen
            OQS_randombytes_switch_algorithm(OQS_RAND_alg_system)
            deterministicRNGState = nil
        }

        // 3. Generate keypair (will use our deterministic RNG)
        OQS_init()

        guard let sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65) else {
            print("[MontanaSeed] Failed to create ML-DSA-65 instance")
            return nil
        }
        defer { OQS_SIG_free(sig) }

        var publicKey = Data(count: Int(sig.pointee.length_public_key))
        var privateKey = Data(count: Int(sig.pointee.length_secret_key))

        let result = publicKey.withUnsafeMutableBytes { pubPtr in
            privateKey.withUnsafeMutableBytes { privPtr in
                OQS_SIG_keypair(sig,
                               pubPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                               privPtr.baseAddress?.assumingMemoryBound(to: UInt8.self))
            }
        }

        guard result == OQS_SUCCESS else {
            print("[MontanaSeed] Keypair generation failed")
            return nil
        }

        print("[MontanaSeed] Generated deterministic keypair: pub=\(publicKey.count), priv=\(privateKey.count)")
        return (privateKey, publicKey)
    }

    /// Generate Montana address from cognitive key
    /// DETERMINISTIC: Same cognitive key → same address
    ///
    /// - Parameter cognitiveKey: The user's cognitive key
    /// - Returns: Montana address (mt + 40 hex chars)
    public static func deriveAddress(from cognitiveKey: String) -> String? {
        guard let keypair = deriveKeypair(from: cognitiveKey) else {
            return nil
        }
        return MLDSA65.generateAddress(from: keypair.publicKey)
    }

    // MARK: - Verification

    /// Verify cognitive key produces expected address
    /// Used when user enters cognitive key to restore wallet
    ///
    /// - Parameters:
    ///   - cognitiveKey: The cognitive key to verify
    ///   - expectedAddress: The expected Montana address
    /// - Returns: true if key produces the expected address
    public static func verify(cognitiveKey: String, producesAddress expectedAddress: String) -> Bool {
        guard let derivedAddress = deriveAddress(from: cognitiveKey) else {
            return false
        }
        return derivedAddress == expectedAddress
    }

    // MARK: - Private Helpers

    /// PBKDF2 key derivation
    private static func pbkdf2(password: String, salt: Data, iterations: UInt32, keyLength: Int) -> Data? {
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
                        iterations,
                        derivedBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        keyLength
                    )
                }
            }
        }

        return result == kCCSuccess ? derivedKey : nil
    }
}

// MARK: - Cognitive Key Info

extension MontanaSeed {

    /// Cognitive key is ONE memory phrase from the user
    /// "Ключ — это мысль. Подпись — это стиль мышления."
    ///
    /// Example: "в детстве я боялся темноты и всегда спал с включённым светом пока мама не..."
    ///
    /// Requirements:
    /// - Minimum 24 words OR 150 characters
    /// - ~248 bits of entropy for planetary-scale collision resistance
    /// - Normalized: lowercase, trimmed whitespace
}

// MARK: - Local Storage (Optional Backup)

extension MontanaSeed {

    /// Store address locally for quick access
    /// NOTE: This is OPTIONAL. The cognitive key can always regenerate everything.
    public static func storeAddressLocally(_ address: String) {
        UserDefaults.standard.set(address, forKey: "montana_address")
    }

    /// Get locally stored address
    public static func getStoredAddress() -> String? {
        return UserDefaults.standard.string(forKey: "montana_address")
    }

    /// Clear local storage
    public static func clearLocalStorage() {
        UserDefaults.standard.removeObject(forKey: "montana_address")
    }
}
