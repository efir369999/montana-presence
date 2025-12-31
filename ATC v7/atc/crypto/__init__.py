"""
ATC Protocol v7 Cryptographic Primitives
Part XII of Technical Specification
"""

from atc.crypto.hash import sha3_256, shake256, tagged_hash
from atc.crypto.merkle import merkle_root, MerkleTree
from atc.crypto.sphincs import (
    sphincs_keygen,
    sphincs_sign,
    sphincs_verify,
)

__all__ = [
    # Hash functions
    "sha3_256",
    "shake256",
    "tagged_hash",
    # Merkle tree
    "merkle_root",
    "MerkleTree",
    # SPHINCS+ signatures
    "sphincs_keygen",
    "sphincs_sign",
    "sphincs_verify",
]
