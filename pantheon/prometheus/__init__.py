"""
PROMETHEUS - God of Cryptography

Ed25519 signatures, ECVRF, SHA256 hashing.
Key generation, proof creation, verification.
"""
from crypto import (
    ECVRF,
    generate_keypair,
    sign_message,
    verify_signature,
    sha256,
)
