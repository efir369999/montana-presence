# ML-DSA-65 Integration Plan for iOS

## Current Status
- iOS app uses HKDF-based key generation (deterministic)
- Signature is HMAC-SHA256 stub (NOT quantum-safe)
- Server (Python) uses `dilithium_py.ml_dsa.ML_DSA_65`

## Target
- Full ML-DSA-65 (FIPS 204) on iOS
- Self-custody: private key never leaves device
- Quantum-resistant signatures

## Key Sizes (FIPS 204)
| Parameter | Size |
|-----------|------|
| Private Key | 4,032 bytes |
| Public Key | 1,952 bytes |
| Signature | 3,309 bytes |

## Integration Options

### Option A: liboqs XCFramework (Recommended)
**Effort:** High | **Security:** Maximum

1. Clone liboqs: `git clone https://github.com/open-quantum-safe/liboqs`
2. Cross-compile for iOS:
```bash
mkdir build-ios && cd build-ios
cmake -G Xcode \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DOQS_MINIMAL_BUILD="OQS_ENABLE_SIG_ml_dsa_65" \
  -DBUILD_SHARED_LIBS=OFF \
  ..
cmake --build . --config Release
```
3. Create XCFramework
4. Add to Xcode project
5. Swift bridging header

### Option B: Reference Implementation Embed
**Effort:** Medium | **Security:** High

Include liboqs reference C code directly:
1. Copy `src/sig/ml_dsa/` from liboqs
2. Add to Xcode as C sources
3. Create Swift wrapper
4. No external dependencies

### Option C: dilithium_py via Python Server (Temporary)
**Effort:** Low | **Security:** Compromised

1. iOS sends PBKDF2 seed to server
2. Server generates ML-DSA-65 keypair
3. Server stores and signs on behalf
4. ⚠️ NOT self-custody!

## Recommended Path

### Phase 1: Quick Win (Option C)
- Deploy NOW with server-side signing
- User experience works
- Mark as "BETA - Server-Assisted Signing"

### Phase 2: Full Self-Custody (Option A/B)
- Compile liboqs for iOS
- Replace server-assisted with local signing
- True self-custody achieved

## Swift Wrapper Design

```swift
// MARK: - ML-DSA-65 Protocol
protocol PostQuantumSigner {
    static func generateKeyPair(seed: Data) -> (privateKey: Data, publicKey: Data)
    static func sign(message: Data, privateKey: Data) -> Data
    static func verify(signature: Data, message: Data, publicKey: Data) -> Bool
}

// MARK: - liboqs Implementation
final class MLDSA65: PostQuantumSigner {
    static func generateKeyPair(seed: Data) -> (privateKey: Data, publicKey: Data) {
        // Call to liboqs OQS_SIG_ml_dsa_65_keypair_from_seed()
    }

    static func sign(message: Data, privateKey: Data) -> Data {
        // Call to OQS_SIG_ml_dsa_65_sign()
    }

    static func verify(signature: Data, message: Data, publicKey: Data) -> Bool {
        // Call to OQS_SIG_ml_dsa_65_verify()
    }
}
```

## C Bridging Header

```c
// JunonaAI-Bridging-Header.h
#include <oqs/oqs.h>

// Wrapper functions for Swift
int montana_ml_dsa_65_keypair(uint8_t *public_key, uint8_t *secret_key);
int montana_ml_dsa_65_keypair_from_seed(uint8_t *public_key, uint8_t *secret_key, const uint8_t *seed);
int montana_ml_dsa_65_sign(uint8_t *sig, size_t *siglen, const uint8_t *msg, size_t msglen, const uint8_t *secret_key);
int montana_ml_dsa_65_verify(const uint8_t *msg, size_t msglen, const uint8_t *sig, size_t siglen, const uint8_t *public_key);
```

## Build Requirements
- Xcode 15+
- CMake 3.20+
- OpenSSL (for liboqs build)
- iOS 15+ deployment target

## Security Considerations
1. Private key in Secure Enclave (if possible) or Keychain
2. Memory wiping after use
3. No logging of key material
4. Signature includes timestamp to prevent replay

## Timeline
- Phase 1 (Server-Assisted): Immediate
- Phase 2 (liboqs Build): 1-2 days
- Phase 3 (Full Integration): 1 day testing

## Sources
- [liboqs GitHub](https://github.com/open-quantum-safe/liboqs)
- [ML-DSA Specification](https://openquantumsafe.org/liboqs/algorithms/sig/ml-dsa.html)
- [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final)
