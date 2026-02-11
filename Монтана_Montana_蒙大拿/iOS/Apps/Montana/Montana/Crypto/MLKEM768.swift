//
//  MLKEM768.swift
//  Junona — Montana Protocol
//
//  ML-KEM-768 (FIPS 203) Post-Quantum Key Encapsulation
//  "Полный постквантовый стек: ML-DSA-65 + ML-KEM-768"
//
//  ✅ POST-QUANTUM: ML-KEM-768 (NIST FIPS 203)
//  ✅ DETERMINISTIC: Same seed → same keypair
//  ✅ KEY ENCAPSULATION: For hybrid encryption
//

import Foundation

/// ML-KEM-768 Post-Quantum Key Encapsulation Mechanism
/// Used for encrypting ML-DSA-65 private keys with cognitive key
public struct MLKEM768 {

    // MARK: - Constants (FIPS 203)

    /// Public key size: 1184 bytes
    public static let publicKeySize = 1184

    /// Secret key size: 2400 bytes
    public static let secretKeySize = 2400

    /// Ciphertext size: 1088 bytes
    public static let ciphertextSize = 1088

    /// Shared secret size: 32 bytes
    public static let sharedSecretSize = 32

    /// Keypair seed size: 64 bytes
    public static let keypairSeedSize = 64

    /// Encapsulation seed size: 32 bytes
    public static let encapsSeedSize = 32

    // MARK: - Key Generation

    /// Generate ML-KEM-768 keypair deterministically from seed
    /// - Parameter seed: 64-byte seed (from PBKDF2 of cognitive key)
    /// - Returns: (secretKey, publicKey) tuple
    public static func keypairFromSeed(_ seed: Data) -> (secretKey: Data, publicKey: Data)? {
        guard seed.count == keypairSeedSize else {
            print("[MLKEM768] Invalid seed size: \(seed.count), expected \(keypairSeedSize)")
            return nil
        }

        OQS_init()

        guard let kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768) else {
            print("[MLKEM768] Failed to create ML-KEM-768 instance")
            return nil
        }
        defer { OQS_KEM_free(kem) }

        var publicKey = Data(count: Int(kem.pointee.length_public_key))
        var secretKey = Data(count: Int(kem.pointee.length_secret_key))

        let result = publicKey.withUnsafeMutableBytes { pubPtr in
            secretKey.withUnsafeMutableBytes { secPtr in
                seed.withUnsafeBytes { seedPtr in
                    OQS_KEM_ml_kem_768_keypair_derand(
                        pubPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        secPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        seedPtr.baseAddress?.assumingMemoryBound(to: UInt8.self)
                    )
                }
            }
        }

        guard result == OQS_SUCCESS else {
            print("[MLKEM768] Keypair generation failed")
            return nil
        }

        print("[MLKEM768] Generated keypair: pk=\(publicKey.count), sk=\(secretKey.count)")
        return (secretKey, publicKey)
    }

    // MARK: - Encapsulation

    /// Encapsulate to generate shared secret (deterministic)
    /// - Parameters:
    ///   - publicKey: ML-KEM-768 public key
    ///   - seed: 32-byte random seed for encapsulation
    /// - Returns: (ciphertext, sharedSecret) tuple
    public static func encapsulate(publicKey: Data, seed: Data) -> (ciphertext: Data, sharedSecret: Data)? {
        guard publicKey.count == publicKeySize else {
            print("[MLKEM768] Invalid public key size: \(publicKey.count)")
            return nil
        }
        guard seed.count == encapsSeedSize else {
            print("[MLKEM768] Invalid encaps seed size: \(seed.count)")
            return nil
        }

        OQS_init()

        guard let kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768) else {
            print("[MLKEM768] Failed to create ML-KEM-768 instance")
            return nil
        }
        defer { OQS_KEM_free(kem) }

        var ciphertext = Data(count: Int(kem.pointee.length_ciphertext))
        var sharedSecret = Data(count: Int(kem.pointee.length_shared_secret))

        let result = ciphertext.withUnsafeMutableBytes { ctPtr in
            sharedSecret.withUnsafeMutableBytes { ssPtr in
                publicKey.withUnsafeBytes { pkPtr in
                    seed.withUnsafeBytes { seedPtr in
                        OQS_KEM_ml_kem_768_encaps_derand(
                            ctPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                            ssPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                            pkPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                            seedPtr.baseAddress?.assumingMemoryBound(to: UInt8.self)
                        )
                    }
                }
            }
        }

        guard result == OQS_SUCCESS else {
            print("[MLKEM768] Encapsulation failed")
            return nil
        }

        print("[MLKEM768] Encapsulated: ct=\(ciphertext.count), ss=\(sharedSecret.count)")
        return (ciphertext, sharedSecret)
    }

    /// Encapsulate with random seed
    /// - Parameter publicKey: ML-KEM-768 public key
    /// - Returns: (ciphertext, sharedSecret) tuple
    public static func encapsulate(publicKey: Data) -> (ciphertext: Data, sharedSecret: Data)? {
        let seed = randomBytes(encapsSeedSize)
        return encapsulate(publicKey: publicKey, seed: seed)
    }

    // MARK: - Decapsulation

    /// Decapsulate to recover shared secret
    /// - Parameters:
    ///   - ciphertext: ML-KEM-768 ciphertext
    ///   - secretKey: ML-KEM-768 secret key
    /// - Returns: Shared secret (32 bytes)
    public static func decapsulate(ciphertext: Data, secretKey: Data) -> Data? {
        guard ciphertext.count == ciphertextSize else {
            print("[MLKEM768] Invalid ciphertext size: \(ciphertext.count)")
            return nil
        }
        guard secretKey.count == secretKeySize else {
            print("[MLKEM768] Invalid secret key size: \(secretKey.count)")
            return nil
        }

        OQS_init()

        guard let kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768) else {
            print("[MLKEM768] Failed to create ML-KEM-768 instance")
            return nil
        }
        defer { OQS_KEM_free(kem) }

        var sharedSecret = Data(count: Int(kem.pointee.length_shared_secret))

        let result = sharedSecret.withUnsafeMutableBytes { ssPtr in
            ciphertext.withUnsafeBytes { ctPtr in
                secretKey.withUnsafeBytes { skPtr in
                    OQS_KEM_ml_kem_768_decaps(
                        ssPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        ctPtr.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        skPtr.baseAddress?.assumingMemoryBound(to: UInt8.self)
                    )
                }
            }
        }

        guard result == OQS_SUCCESS else {
            print("[MLKEM768] Decapsulation failed")
            return nil
        }

        print("[MLKEM768] Decapsulated: ss=\(sharedSecret.count)")
        return sharedSecret
    }

    // MARK: - Helpers

    /// Generate cryptographically secure random bytes
    private static func randomBytes(_ count: Int) -> Data {
        var bytes = Data(count: count)
        _ = bytes.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, count, $0.baseAddress!) }
        return bytes
    }
}
