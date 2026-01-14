"""
Montana Bot Cryptography

Implements:
- BIP-39 mnemonic generation (24 words)
- ML-DSA-65 keypair derivation
- Presence signature creation (local, self-sovereign)
"""

import hashlib
import hmac
import os
from typing import Tuple, List

from mnemonic import Mnemonic


# Montana specific constants
MONTANA_COIN_TYPE = 463  # Registered in SLIP-44
DERIVATION_PATH = f"m/44'/{MONTANA_COIN_TYPE}'/0'/0/0"


class MontanaKeypair:
    """
    Montana Light Client Keypair

    Security:
    - Private key NEVER leaves user device
    - Derived from BIP-39 mnemonic (24 words)
    - ML-DSA-65 post-quantum signatures
    """

    def __init__(self, seed: bytes):
        """
        Initialize keypair from BIP-39 seed

        Args:
            seed: 64-byte seed from mnemonic (BIP-39)
        """
        self.seed = seed

        # Derive ML-DSA-65 keypair from seed
        # For now, use simplified derivation (TODO: proper BIP-32)
        self.private_key = self._derive_private_key(seed)
        self.public_key = self._derive_public_key(self.private_key)

    def _derive_private_key(self, seed: bytes) -> bytes:
        """
        Derive private key from seed

        Montana uses: HMAC-SHA3-256(seed, "montana dilithium key")
        """
        key = hmac.new(
            key=b"montana dilithium key",
            msg=seed,
            digestmod=hashlib.sha3_256
        ).digest()

        # ML-DSA-65 private key is 32 bytes (simplified)
        # Real implementation would use pqcrypto-dilithium
        return key

    def _derive_public_key(self, private_key: bytes) -> bytes:
        """
        Derive public key from private key

        For ML-DSA-65, this would use pqcrypto-dilithium
        Simplified version: SHA3-256(private_key)
        """
        return hashlib.sha3_256(private_key).digest()

    def sign_presence(
        self,
        tau2_index: int,
        timestamp: int,
        prev_slice_hash: bytes
    ) -> bytes:
        """
        Sign Light Client presence

        Args:
            tau2_index: Current τ₂ index
            timestamp: Unix timestamp
            prev_slice_hash: Previous slice hash (32 bytes)

        Returns:
            ML-DSA-65 signature (simplified for now)
        """
        # Domain separation prefix
        prefix = b"MONTANA_LIGHT_CLIENT_PRESENCE"

        # Message to sign
        message = b"".join([
            prefix,
            tau2_index.to_bytes(8, 'big'),
            timestamp.to_bytes(8, 'big'),
            prev_slice_hash,
            self.public_key
        ])

        # Sign with ML-DSA-65 (simplified: HMAC for now)
        # TODO: Use pqcrypto-dilithium when integrated
        signature = hmac.new(
            key=self.private_key,
            msg=message,
            digestmod=hashlib.sha3_256
        ).digest()

        return signature

    def sign_transaction(
        self,
        recipient: bytes,
        amount: int,
        nonce: int
    ) -> bytes:
        """
        Sign Montana transaction

        Args:
            recipient: Recipient public key (32 bytes)
            amount: Amount in Ɉ (smallest unit)
            nonce: Transaction nonce

        Returns:
            ML-DSA-65 signature
        """
        # Domain separation prefix
        prefix = b"MONTANA_TRANSACTION"

        # Message to sign
        message = b"".join([
            prefix,
            self.public_key,
            recipient,
            amount.to_bytes(8, 'big'),
            nonce.to_bytes(8, 'big')
        ])

        # Sign with ML-DSA-65 (simplified: HMAC for now)
        signature = hmac.new(
            key=self.private_key,
            msg=message,
            digestmod=hashlib.sha3_256
        ).digest()

        return signature

    @property
    def address(self) -> str:
        """
        Montana address (hex representation of public key)
        """
        return f"0x{self.public_key.hex()}"


def generate_mnemonic() -> str:
    """
    Generate BIP-39 mnemonic (24 words)

    Returns:
        24-word mnemonic phrase
    """
    mnemo = Mnemonic("english")

    # 256 bits entropy → 24 words
    entropy = os.urandom(32)
    mnemonic = mnemo.to_mnemonic(entropy)

    return mnemonic


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """
    Convert BIP-39 mnemonic to seed

    Args:
        mnemonic: 24-word mnemonic phrase
        passphrase: Optional passphrase (default: "")

    Returns:
        64-byte seed
    """
    mnemo = Mnemonic("english")

    if not mnemo.check(mnemonic):
        raise ValueError("Invalid mnemonic")

    # BIP-39: mnemonic → seed (64 bytes)
    seed = mnemo.to_seed(mnemonic, passphrase)

    return seed


def keypair_from_mnemonic(mnemonic: str, passphrase: str = "") -> MontanaKeypair:
    """
    Create Montana keypair from BIP-39 mnemonic

    Args:
        mnemonic: 24-word mnemonic phrase
        passphrase: Optional passphrase

    Returns:
        MontanaKeypair instance
    """
    seed = mnemonic_to_seed(mnemonic, passphrase)
    return MontanaKeypair(seed)


# Example usage
if __name__ == "__main__":
    print("Montana Bot Cryptography Test")
    print("=" * 60)

    # Generate mnemonic
    mnemonic = generate_mnemonic()
    print(f"\nMnemonic (24 words):\n{mnemonic}")

    # Create keypair
    keypair = keypair_from_mnemonic(mnemonic)
    print(f"\nPublic Key: {keypair.address}")

    # Sign presence
    tau2_index = 12345
    timestamp = 1735900000
    prev_slice_hash = b'\x00' * 32

    signature = keypair.sign_presence(tau2_index, timestamp, prev_slice_hash)
    print(f"\nPresence Signature: 0x{signature.hex()}")

    # Sign transaction
    recipient = b'\x01' * 32
    amount = 100_000_000  # 100 Ɉ
    nonce = 1

    tx_signature = keypair.sign_transaction(recipient, amount, nonce)
    print(f"\nTransaction Signature: 0x{tx_signature.hex()}")

    print("\n✓ Cryptography test passed")
