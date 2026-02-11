//
//  MLDSA65.swift
//  Junona — Montana Protocol
//
//  Self-Custody ML-DSA-65 (FIPS 204) via liboqs
//  "Ключи — это мысли. Подпись — это стиль мышления."
//
//  ✅ SELF-CUSTODY: Private key NEVER leaves device (unencrypted)
//  ✅ POST-QUANTUM SIGNATURES: ML-DSA-65 (FIPS 204)
//  ✅ DETERMINISTIC KEYGEN: MontanaSeed - same cognitive key = same keys
//  ✅ FULL PQ STACK: No classical cryptography in the chain
//
//  RECOMMENDED: Use MontanaSeed.deriveKeypair() for deterministic key derivation.
//  This file provides signing/verification and legacy encryption methods.
//

import Foundation
import CommonCrypto
import CryptoKit

/// ML-DSA-65 Post-Quantum Signature Scheme
/// Self-Custody implementation using liboqs
public struct MLDSA65 {

    // MARK: - Constants (FIPS 204)

    /// Private key size: 4032 bytes
    public static let privateKeySize = 4032

    /// Public key size: 1952 bytes
    public static let publicKeySize = 1952

    /// Signature size: 3309 bytes
    public static let signatureSize = 3309

    // MARK: - Key Generation

    /// Generate ML-DSA-65 keypair (random, then encrypt with cognitive key)
    /// - Returns: (privateKey, publicKey) tuple
    public static func generateKeypair() -> (privateKey: Data, publicKey: Data)? {
        // Initialize liboqs
        OQS_init()

        // Get ML-DSA-65 algorithm
        guard let sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65) else {
            print("[MLDSA65] Failed to create ML-DSA-65 instance")
            return nil
        }
        defer { OQS_SIG_free(sig) }

        // Allocate key buffers
        var publicKey = Data(count: Int(sig.pointee.length_public_key))
        var privateKey = Data(count: Int(sig.pointee.length_secret_key))

        // Generate random keypair (liboqs uses secure RNG)
        let result = publicKey.withUnsafeMutableBytes { pubPtr in
            privateKey.withUnsafeMutableBytes { privPtr in
                OQS_SIG_keypair(sig,
                               pubPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                               privPtr.baseAddress?.assumingMemoryBound(to: UInt8.self))
            }
        }

        guard result == OQS_SUCCESS else {
            print("[MLDSA65] Keypair generation failed")
            return nil
        }

        print("[MLDSA65] Generated keypair: pub=\(publicKey.count) bytes, priv=\(privateKey.count) bytes")
        return (privateKey, publicKey)
    }

    // MARK: - Encryption (ML-KEM-768 + AES-256-GCM)
    //
    // ⚠️ DEPRECATED: Use MontanaSeed.deriveKeypair() instead!
    //
    // The new mechanism derives keys DETERMINISTICALLY from cognitive key.
    // No encryption needed - same cognitive key = same keys, always.
    // These methods are kept for backwards compatibility only.
    //
    // OLD (server-dependent):
    // 1. Generate random keypair
    // 2. Encrypt private key with cognitive key
    // 3. Upload encrypted key to server
    // 4. Restore: download + decrypt
    //
    // NEW (server-independent):
    // 1. MontanaSeed.deriveKeypair(cognitiveKey) → deterministic keypair
    // 2. No server needed!
    //

    /// Fixed salt for ML-KEM key derivation (deterministic from cognitive key)
    private static let kemKeySalt = "MONTANA_MLKEM_V1".data(using: .utf8)!

    /// Encrypt private key with cognitive key using ML-KEM-768 + AES-256-GCM
    /// - Parameters:
    ///   - privateKey: ML-DSA-65 private key (4032 bytes)
    ///   - cognitiveKey: User's cognitive key phrase
    /// - Returns: Encrypted data (kem_ciphertext + nonce + aes_ciphertext + tag)
    public static func encryptPrivateKey(_ privateKey: Data, with cognitiveKey: String) -> Data? {
        guard privateKey.count == privateKeySize else {
            print("[MLDSA65] Invalid private key size: \(privateKey.count)")
            return nil
        }

        // 1. Derive 64-byte seed from cognitive key
        let normalized = cognitiveKey
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        guard let seed = pbkdf2(password: normalized, salt: kemKeySalt, iterations: 600_000, keyLength: 64) else {
            print("[MLDSA65] PBKDF2 failed")
            return nil
        }

        // 2. Generate ML-KEM-768 keypair deterministically
        guard let kemKeys = MLKEM768.keypairFromSeed(seed) else {
            print("[MLDSA65] ML-KEM keypair generation failed")
            return nil
        }

        // 3. Encapsulate to get shared secret
        guard let encapsResult = MLKEM768.encapsulate(publicKey: kemKeys.publicKey) else {
            print("[MLDSA65] ML-KEM encapsulation failed")
            return nil
        }

        // 4. Use shared secret as AES-256 key
        let nonce = randomBytes(12)
        guard let aesEncrypted = aesGCMEncrypt(data: privateKey, key: encapsResult.sharedSecret, nonce: nonce) else {
            print("[MLDSA65] AES-GCM encryption failed")
            return nil
        }

        // 5. Pack: kem_ciphertext (1088) + nonce (12) + aes_ciphertext + tag
        var result = Data()
        result.append(encapsResult.ciphertext)  // 1088 bytes
        result.append(nonce)                     // 12 bytes
        result.append(aesEncrypted)              // 4032 + 16 bytes

        print("[MLDSA65] Encrypted with ML-KEM-768: \(result.count) bytes")
        return result
    }

    /// Decrypt private key with cognitive key using ML-KEM-768 + AES-256-GCM
    /// - Parameters:
    ///   - encryptedData: Encrypted private key data
    ///   - cognitiveKey: User's cognitive key phrase
    /// - Returns: Decrypted ML-DSA-65 private key
    public static func decryptPrivateKey(_ encryptedData: Data, with cognitiveKey: String) -> Data? {
        // Minimum size: kem_ct (1088) + nonce (12) + priv (4032) + tag (16) = 5148
        let minSize = MLKEM768.ciphertextSize + 12 + privateKeySize + 16
        guard encryptedData.count >= minSize else {
            print("[MLDSA65] Encrypted data too small: \(encryptedData.count), expected >= \(minSize)")
            return nil
        }

        // 1. Derive same 64-byte seed from cognitive key
        let normalized = cognitiveKey
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        guard let seed = pbkdf2(password: normalized, salt: kemKeySalt, iterations: 600_000, keyLength: 64) else {
            print("[MLDSA65] PBKDF2 failed")
            return nil
        }

        // 2. Generate same ML-KEM-768 keypair
        guard let kemKeys = MLKEM768.keypairFromSeed(seed) else {
            print("[MLDSA65] ML-KEM keypair generation failed")
            return nil
        }

        // 3. Unpack
        let kemCiphertext = encryptedData.prefix(MLKEM768.ciphertextSize)  // 1088 bytes
        let nonce = encryptedData.subdata(in: MLKEM768.ciphertextSize..<(MLKEM768.ciphertextSize + 12))
        let aesCiphertext = encryptedData.subdata(in: (MLKEM768.ciphertextSize + 12)..<encryptedData.count)

        // 4. Decapsulate to recover shared secret
        guard let sharedSecret = MLKEM768.decapsulate(ciphertext: kemCiphertext, secretKey: kemKeys.secretKey) else {
            print("[MLDSA65] ML-KEM decapsulation failed - wrong cognitive key?")
            return nil
        }

        // 5. Decrypt with AES-256-GCM
        guard let decrypted = aesGCMDecrypt(data: aesCiphertext, key: sharedSecret, nonce: nonce) else {
            print("[MLDSA65] AES-GCM decryption failed")
            return nil
        }

        // 6. Verify size
        guard decrypted.count == privateKeySize else {
            print("[MLDSA65] Decrypted key wrong size: \(decrypted.count)")
            return nil
        }

        print("[MLDSA65] Decrypted with ML-KEM-768: \(decrypted.count) bytes")
        return decrypted
    }

    /// Generate cryptographically secure random bytes
    private static func randomBytes(_ count: Int) -> Data {
        var bytes = Data(count: count)
        _ = bytes.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, count, $0.baseAddress!) }
        return bytes
    }

    /// AES-256-GCM encryption using CryptoKit
    private static func aesGCMEncrypt(data: Data, key: Data, nonce: Data) -> Data? {
        do {
            let symmetricKey = SymmetricKey(data: key)
            let nonceObj = try AES.GCM.Nonce(data: nonce)
            let sealedBox = try AES.GCM.seal(data, using: symmetricKey, nonce: nonceObj)
            // combined = nonce + ciphertext + tag, but we already have nonce separate
            // So return ciphertext + tag
            return sealedBox.ciphertext + sealedBox.tag
        } catch {
            print("[MLDSA65] AES-GCM encrypt error: \(error)")
            return nil
        }
    }

    /// AES-256-GCM decryption using CryptoKit
    private static func aesGCMDecrypt(data: Data, key: Data, nonce: Data) -> Data? {
        guard data.count > 16 else { return nil }

        do {
            let symmetricKey = SymmetricKey(data: key)
            let nonceObj = try AES.GCM.Nonce(data: nonce)

            // data = ciphertext + tag (16 bytes)
            let ciphertextLen = data.count - 16
            let ciphertext = data.prefix(ciphertextLen)
            let tag = data.suffix(16)

            let sealedBox = try AES.GCM.SealedBox(nonce: nonceObj, ciphertext: ciphertext, tag: tag)
            let decrypted = try AES.GCM.open(sealedBox, using: symmetricKey)
            return decrypted
        } catch {
            print("[MLDSA65] AES-GCM decrypt error: \(error)")
            return nil
        }
    }

    // MARK: - Legacy (for migration)

    /// Generate keypair from cognitive key (DEPRECATED - keys not truly deterministic)
    /// Kept for backwards compatibility during migration
    @available(*, deprecated, message: "Use generateKeypair() + encryptPrivateKey() instead")
    public static func keygenFromCognitiveKey(_ cognitiveKey: String) -> (privateKey: Data, publicKey: Data)? {
        // Just generate a new random keypair
        // The cognitive key will be used to ENCRYPT, not derive
        return generateKeypair()
    }

    // MARK: - Signing

    /// Sign message with ML-DSA-65 private key
    /// - Parameters:
    ///   - message: Message to sign
    ///   - privateKey: ML-DSA-65 private key (4032 bytes)
    /// - Returns: Signature (3309 bytes)
    public static func sign(message: Data, privateKey: Data) -> Data? {
        guard privateKey.count == privateKeySize else {
            print("[MLDSA65] Invalid private key size: \(privateKey.count), expected \(privateKeySize)")
            return nil
        }

        OQS_init()

        guard let sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65) else {
            print("[MLDSA65] Failed to create ML-DSA-65 instance")
            return nil
        }
        defer { OQS_SIG_free(sig) }

        var signature = Data(count: Int(sig.pointee.length_signature))
        var signatureLen: Int = 0

        let result = signature.withUnsafeMutableBytes { sigPtr in
            message.withUnsafeBytes { msgPtr in
                privateKey.withUnsafeBytes { keyPtr in
                    OQS_SIG_sign(sig,
                                sigPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                                &signatureLen,
                                msgPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                                message.count,
                                keyPtr.baseAddress?.assumingMemoryBound(to: UInt8.self))
                }
            }
        }

        guard result == OQS_SUCCESS else {
            print("[MLDSA65] Signing failed")
            return nil
        }

        signature = signature.prefix(signatureLen)
        print("[MLDSA65] Signed: \(signatureLen) bytes")
        return signature
    }

    // MARK: - Verification

    /// Verify ML-DSA-65 signature
    /// - Parameters:
    ///   - message: Original message
    ///   - signature: Signature to verify (3309 bytes)
    ///   - publicKey: ML-DSA-65 public key (1952 bytes)
    /// - Returns: true if signature is valid
    public static func verify(message: Data, signature: Data, publicKey: Data) -> Bool {
        guard publicKey.count == publicKeySize else {
            print("[MLDSA65] Invalid public key size: \(publicKey.count), expected \(publicKeySize)")
            return false
        }

        OQS_init()

        guard let sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65) else {
            print("[MLDSA65] Failed to create ML-DSA-65 instance")
            return false
        }
        defer { OQS_SIG_free(sig) }

        let result = message.withUnsafeBytes { msgPtr in
            signature.withUnsafeBytes { sigPtr in
                publicKey.withUnsafeBytes { keyPtr in
                    OQS_SIG_verify(sig,
                                  msgPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                                  message.count,
                                  sigPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                                  signature.count,
                                  keyPtr.baseAddress?.assumingMemoryBound(to: UInt8.self))
                }
            }
        }

        let isValid = result == OQS_SUCCESS
        print("[MLDSA65] Verify: \(isValid ? "✅ VALID" : "❌ INVALID")")
        return isValid
    }

    // MARK: - Helpers

    /// SHA-256 hash
    private static func sha256(_ data: Data) -> Data {
        var hash = [UInt8](repeating: 0, count: 32)
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return Data(hash)
    }

    /// PBKDF2 key derivation
    private static func pbkdf2(password: String, salt: Data, iterations: Int, keyLength: Int) -> Data? {
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

    /// HKDF-Expand (RFC 5869)
    private static func hkdfExpand(prk: Data, info: Data, length: Int) -> Data {
        var output = Data()
        var previous = Data()
        var counter: UInt8 = 1

        while output.count < length {
            var input = previous
            input.append(info)
            input.append(counter)

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
}

// MARK: - Montana Address Generation

extension MLDSA65 {

    /// Generate Montana address from public key
    /// Format: mt + SHA256(pubkey)[:20].hex() = 42 chars
    public static func generateAddress(from publicKey: Data) -> String {
        let hash = sha256(publicKey)
        let addressHex = hash.prefix(20).map { String(format: "%02x", $0) }.joined()
        return "mt" + addressHex
    }
}
