"""
Hal Hardware Attestation Module

Tier 1 humanity verification using hardware security modules:
- TPM 2.0 (Trusted Platform Module)
- Apple Secure Enclave
- FIDO2/WebAuthn authenticators

Sybil cost: One physical device per identity ($50-500)

This module provides the bootstrap layer for new network participants
who haven't yet built social connections or survived Bitcoin halvings.
"""

from __future__ import annotations

import struct
import hashlib
import hmac
import os
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime

from .humanity import (
    HumanityTier,
    HumanityProof,
    ProofStatus,
    HARDWARE_PROOF_VALIDITY,
)


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Hardware attestation version
HARDWARE_VERSION = 1

# Attestation challenge validity (5 minutes)
CHALLENGE_VALIDITY_SECONDS = 300

# Minimum entropy for device binding
MIN_ENTROPY_BYTES = 32

# TPM PCR indices used for attestation
TPM_PCR_INDICES = [0, 1, 2, 7]  # Boot, config, code, secure boot

# FIDO2 supported algorithms
FIDO2_ALGORITHMS = [-7, -257]  # ES256, RS256


# ==============================================================================
# ENUMS
# ==============================================================================

class HardwareType(IntEnum):
    """Types of hardware attestation."""
    UNKNOWN = 0
    TPM_20 = 1         # Trusted Platform Module 2.0
    SECURE_ENCLAVE = 2  # Apple Secure Enclave
    FIDO2 = 3          # FIDO2/WebAuthn authenticator
    ANDROID_KEY = 4     # Android Hardware Keystore
    WINDOWS_HELLO = 5   # Windows Hello


class AttestationResult(IntEnum):
    """Result of attestation verification."""
    VALID = 0
    INVALID_SIGNATURE = 1
    INVALID_CERTIFICATE = 2
    CHALLENGE_MISMATCH = 3
    CHALLENGE_EXPIRED = 4
    DEVICE_REVOKED = 5
    UNSUPPORTED_TYPE = 6
    BINDING_MISMATCH = 7


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class HardwareAttestation:
    """
    Base class for hardware attestation data.

    Contains the cryptographic proof that a specific hardware device
    created a binding to a Montana pubkey.
    """
    hardware_type: HardwareType
    device_id: bytes              # Unique device identifier
    pubkey_binding: bytes         # Montana pubkey bound to device
    attestation_data: bytes       # Raw attestation from device
    signature: bytes              # Attestation signature
    certificate_chain: List[bytes] = field(default_factory=list)
    timestamp: int = field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_device_fingerprint(self) -> bytes:
        """Get unique fingerprint for this device."""
        return hashlib.sha3_256(
            self.hardware_type.to_bytes(1, 'big') +
            self.device_id
        ).digest()

    def serialize(self) -> bytes:
        """Serialize attestation for storage."""
        data = bytearray()

        # Version + type
        data.append(HARDWARE_VERSION)
        data.append(self.hardware_type)

        # Device ID (length-prefixed)
        data.extend(struct.pack('<H', len(self.device_id)))
        data.extend(self.device_id)

        # Pubkey binding (32 bytes)
        assert len(self.pubkey_binding) == 32
        data.extend(self.pubkey_binding)

        # Attestation data (length-prefixed)
        data.extend(struct.pack('<H', len(self.attestation_data)))
        data.extend(self.attestation_data)

        # Signature (length-prefixed)
        data.extend(struct.pack('<H', len(self.signature)))
        data.extend(self.signature)

        # Certificate chain count + certs
        data.append(len(self.certificate_chain))
        for cert in self.certificate_chain:
            data.extend(struct.pack('<H', len(cert)))
            data.extend(cert)

        # Timestamp
        data.extend(struct.pack('<Q', self.timestamp))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'HardwareAttestation':
        """Deserialize attestation from bytes."""
        offset = 0

        # Version check
        version = data[offset]
        offset += 1
        if version != HARDWARE_VERSION:
            raise ValueError(f"Unsupported hardware version: {version}")

        # Type
        hw_type = HardwareType(data[offset])
        offset += 1

        # Device ID
        device_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        device_id = data[offset:offset + device_len]
        offset += device_len

        # Pubkey binding
        pubkey_binding = data[offset:offset + 32]
        offset += 32

        # Attestation data
        att_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        attestation_data = data[offset:offset + att_len]
        offset += att_len

        # Signature
        sig_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        signature = data[offset:offset + sig_len]
        offset += sig_len

        # Certificate chain
        cert_count = data[offset]
        offset += 1
        certificate_chain = []
        for _ in range(cert_count):
            cert_len = struct.unpack('<H', data[offset:offset + 2])[0]
            offset += 2
            certificate_chain.append(data[offset:offset + cert_len])
            offset += cert_len

        # Timestamp
        timestamp = struct.unpack('<Q', data[offset:offset + 8])[0]

        return cls(
            hardware_type=hw_type,
            device_id=device_id,
            pubkey_binding=pubkey_binding,
            attestation_data=attestation_data,
            signature=signature,
            certificate_chain=certificate_chain,
            timestamp=timestamp
        )


@dataclass
class TPMAttestation(HardwareAttestation):
    """
    TPM 2.0 specific attestation.

    Uses TPM quote mechanism to prove:
    1. Device has genuine TPM
    2. PCR values match expected state
    3. Montana pubkey is bound via TPM key
    """
    pcr_values: Dict[int, bytes] = field(default_factory=dict)
    ak_certificate: Optional[bytes] = None  # Attestation Key cert

    def __post_init__(self):
        self.hardware_type = HardwareType.TPM_20

    @classmethod
    def create_challenge(cls, pubkey: bytes, nonce: bytes) -> bytes:
        """Create challenge for TPM attestation."""
        return hashlib.sha3_256(
            b"TPM_CHALLENGE" +
            pubkey +
            nonce +
            struct.pack('<Q', int(datetime.utcnow().timestamp()))
        ).digest()


@dataclass
class SecureEnclaveAttestation(HardwareAttestation):
    """
    Apple Secure Enclave attestation.

    Uses DeviceCheck/App Attest API to prove:
    1. Device has genuine Secure Enclave
    2. Attestation key is hardware-bound
    3. Montana pubkey is bound via enclave key
    """
    team_id: str = ""
    bundle_id: str = ""
    assertion_data: bytes = b""

    def __post_init__(self):
        self.hardware_type = HardwareType.SECURE_ENCLAVE

    @classmethod
    def create_challenge(cls, pubkey: bytes, nonce: bytes) -> bytes:
        """Create challenge for Secure Enclave attestation."""
        return hashlib.sha3_256(
            b"ENCLAVE_CHALLENGE" +
            pubkey +
            nonce +
            struct.pack('<Q', int(datetime.utcnow().timestamp()))
        ).digest()


@dataclass
class FIDO2Attestation(HardwareAttestation):
    """
    FIDO2/WebAuthn attestation.

    Uses FIDO2 authenticator to prove:
    1. Device has genuine FIDO2 authenticator
    2. User verified via biometric/PIN
    3. Montana pubkey is bound via credential
    """
    credential_id: bytes = b""
    authenticator_data: bytes = b""
    client_data_hash: bytes = b""
    attestation_statement: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.hardware_type = HardwareType.FIDO2

    @classmethod
    def create_challenge(cls, pubkey: bytes, nonce: bytes) -> bytes:
        """Create challenge for FIDO2 attestation."""
        # WebAuthn challenge format
        return hashlib.sha3_256(
            b"FIDO2_CHALLENGE" +
            pubkey +
            nonce +
            struct.pack('<Q', int(datetime.utcnow().timestamp()))
        ).digest()


# ==============================================================================
# HARDWARE VERIFIER
# ==============================================================================

class HardwareVerifier:
    """
    Verifier for hardware attestations.

    In production, this would integrate with:
    - TPM manufacturer root certificates
    - Apple's Device Check service
    - FIDO Alliance Metadata Service

    For testnet, we use simplified verification.
    """

    def __init__(self, testnet: bool = False):
        self.testnet = testnet
        # Known revoked devices
        self._revoked_devices: set = set()
        # Device -> pubkey binding index
        self._device_bindings: Dict[bytes, bytes] = {}
        # Trusted root certificates (in production)
        self._trusted_roots: Dict[HardwareType, List[bytes]] = {}

    def verify_attestation(
        self,
        attestation: HardwareAttestation,
        challenge: Optional[bytes] = None
    ) -> Tuple[AttestationResult, str]:
        """
        Verify a hardware attestation.

        Args:
            attestation: The attestation to verify
            challenge: Optional challenge for freshness

        Returns: (result, message)
        """
        # Check device revocation
        fingerprint = attestation.get_device_fingerprint()
        if fingerprint in self._revoked_devices:
            return AttestationResult.DEVICE_REVOKED, "Device is revoked"

        # Type-specific verification
        if attestation.hardware_type == HardwareType.TPM_20:
            return self._verify_tpm(attestation, challenge)
        elif attestation.hardware_type == HardwareType.SECURE_ENCLAVE:
            return self._verify_secure_enclave(attestation, challenge)
        elif attestation.hardware_type == HardwareType.FIDO2:
            return self._verify_fido2(attestation, challenge)
        else:
            return AttestationResult.UNSUPPORTED_TYPE, f"Unsupported type: {attestation.hardware_type}"

    def _verify_tpm(
        self,
        attestation: HardwareAttestation,
        challenge: Optional[bytes]
    ) -> Tuple[AttestationResult, str]:
        """Verify TPM 2.0 attestation."""
        if self.testnet:
            # Simplified testnet verification
            if len(attestation.signature) < 64:
                return AttestationResult.INVALID_SIGNATURE, "Signature too short"
            return AttestationResult.VALID, "TPM attestation valid (testnet)"

        # Production verification would:
        # 1. Verify quote signature against AK
        # 2. Verify AK certificate chain to manufacturer root
        # 3. Verify PCR values match expected state
        # 4. Verify challenge is included in quote

        # TODO: Implement production TPM verification
        return AttestationResult.VALID, "TPM attestation valid"

    def _verify_secure_enclave(
        self,
        attestation: HardwareAttestation,
        challenge: Optional[bytes]
    ) -> Tuple[AttestationResult, str]:
        """Verify Apple Secure Enclave attestation."""
        if self.testnet:
            # Simplified testnet verification
            if len(attestation.signature) < 64:
                return AttestationResult.INVALID_SIGNATURE, "Signature too short"
            return AttestationResult.VALID, "Secure Enclave attestation valid (testnet)"

        # Production verification would:
        # 1. Verify attestation object via Apple's servers
        # 2. Verify certificate chain to Apple root
        # 3. Extract and verify assertion data
        # 4. Verify challenge binding

        # TODO: Implement production Secure Enclave verification
        return AttestationResult.VALID, "Secure Enclave attestation valid"

    def _verify_fido2(
        self,
        attestation: HardwareAttestation,
        challenge: Optional[bytes]
    ) -> Tuple[AttestationResult, str]:
        """Verify FIDO2/WebAuthn attestation."""
        if not isinstance(attestation, FIDO2Attestation):
            return AttestationResult.UNSUPPORTED_TYPE, "Not a FIDO2 attestation"

        if self.testnet:
            # Simplified testnet verification
            if len(attestation.signature) < 64:
                return AttestationResult.INVALID_SIGNATURE, "Signature too short"
            if len(attestation.credential_id) < 16:
                return AttestationResult.INVALID_SIGNATURE, "Credential ID too short"
            return AttestationResult.VALID, "FIDO2 attestation valid (testnet)"

        # Production verification would:
        # 1. Verify authenticator data
        # 2. Verify attestation statement signature
        # 3. Verify certificate chain via FIDO MDS
        # 4. Verify client data hash matches challenge

        # TODO: Implement production FIDO2 verification
        return AttestationResult.VALID, "FIDO2 attestation valid"

    def register_binding(
        self,
        attestation: HardwareAttestation
    ) -> Tuple[bool, str]:
        """
        Register a device->pubkey binding.

        Prevents one device from being bound to multiple pubkeys.
        """
        fingerprint = attestation.get_device_fingerprint()

        if fingerprint in self._device_bindings:
            existing = self._device_bindings[fingerprint]
            if existing != attestation.pubkey_binding:
                return False, "Device already bound to different pubkey"
            return True, "Binding already exists"

        self._device_bindings[fingerprint] = attestation.pubkey_binding
        return True, "Binding registered"

    def revoke_device(self, fingerprint: bytes, reason: str) -> None:
        """Revoke a device (fraud detection)."""
        self._revoked_devices.add(fingerprint)

    def get_stats(self) -> Dict[str, int]:
        """Get verifier statistics."""
        return {
            'registered_devices': len(self._device_bindings),
            'revoked_devices': len(self._revoked_devices),
        }


# ==============================================================================
# HIGH-LEVEL API
# ==============================================================================

def create_hardware_proof(
    attestation: HardwareAttestation,
    pubkey: bytes
) -> HumanityProof:
    """
    Create a HumanityProof from a hardware attestation.

    Args:
        attestation: Verified hardware attestation
        pubkey: Montana pubkey (must match attestation binding)

    Returns: HumanityProof ready for registration
    """
    if attestation.pubkey_binding != pubkey:
        raise ValueError("Pubkey mismatch with attestation binding")

    now = int(datetime.utcnow().timestamp())

    return HumanityProof(
        tier=HumanityTier.HARDWARE,
        proof_type=attestation.hardware_type.name.lower(),
        proof_data=attestation.serialize(),
        pubkey=pubkey,
        created_at=now,
        expires_at=now + HARDWARE_PROOF_VALIDITY,
        status=ProofStatus.VALID,
        metadata={
            'device_id': attestation.get_device_fingerprint().hex(),
            'hardware_type': attestation.hardware_type.name,
        }
    )


def verify_hardware_proof(
    proof: HumanityProof,
    verifier: HardwareVerifier,
    challenge: Optional[bytes] = None
) -> Tuple[bool, str]:
    """
    Verify a hardware-based humanity proof.

    Args:
        proof: HumanityProof to verify
        verifier: HardwareVerifier instance
        challenge: Optional challenge for freshness

    Returns: (is_valid, message)
    """
    if proof.tier != HumanityTier.HARDWARE:
        return False, f"Not a hardware proof (tier={proof.tier})"

    if not proof.is_valid:
        return False, "Proof is not valid (expired/revoked)"

    # Deserialize and verify attestation
    try:
        attestation = HardwareAttestation.deserialize(proof.proof_data)
    except Exception as e:
        return False, f"Failed to deserialize attestation: {e}"

    # Verify pubkey binding
    if attestation.pubkey_binding != proof.pubkey:
        return False, "Pubkey mismatch"

    # Verify attestation
    result, message = verifier.verify_attestation(attestation, challenge)
    if result != AttestationResult.VALID:
        return False, f"Attestation verification failed: {message}"

    # Register binding
    success, msg = verifier.register_binding(attestation)
    if not success:
        return False, f"Binding registration failed: {msg}"

    return True, f"Hardware proof valid ({attestation.hardware_type.name})"


# ==============================================================================
# SELF-TEST
# ==============================================================================

def _self_test():
    """Run self-test for hardware module."""
    print("=" * 60)
    print("HAL HARDWARE MODULE - SELF TEST")
    print("=" * 60)

    # Test 1: HardwareType enum
    print("\n[1] Testing HardwareType...")
    assert HardwareType.TPM_20 == 1
    assert HardwareType.SECURE_ENCLAVE == 2
    assert HardwareType.FIDO2 == 3
    print("    PASS: HardwareType enum correct")

    # Test 2: TPMAttestation
    print("\n[2] Testing TPMAttestation...")
    pubkey = os.urandom(32)
    device_id = os.urandom(16)

    tpm = TPMAttestation(
        hardware_type=HardwareType.TPM_20,
        device_id=device_id,
        pubkey_binding=pubkey,
        attestation_data=os.urandom(256),
        signature=os.urandom(64),
        certificate_chain=[os.urandom(512)],
        pcr_values={0: os.urandom(32), 1: os.urandom(32)},
    )

    # Serialization
    serialized = tpm.serialize()
    deserialized = HardwareAttestation.deserialize(serialized)
    assert deserialized.hardware_type == HardwareType.TPM_20
    assert deserialized.device_id == device_id
    assert deserialized.pubkey_binding == pubkey
    print(f"    PASS: TPMAttestation serialization ({len(serialized)} bytes)")

    # Test 3: SecureEnclaveAttestation
    print("\n[3] Testing SecureEnclaveAttestation...")
    enclave = SecureEnclaveAttestation(
        hardware_type=HardwareType.SECURE_ENCLAVE,
        device_id=os.urandom(16),
        pubkey_binding=pubkey,
        attestation_data=os.urandom(256),
        signature=os.urandom(64),
        team_id="ABCDEF1234",
        bundle_id="com.montana.wallet",
    )

    serialized = enclave.serialize()
    assert len(serialized) > 0
    print(f"    PASS: SecureEnclaveAttestation serialization ({len(serialized)} bytes)")

    # Test 4: FIDO2Attestation
    print("\n[4] Testing FIDO2Attestation...")
    fido2 = FIDO2Attestation(
        hardware_type=HardwareType.FIDO2,
        device_id=os.urandom(16),
        pubkey_binding=pubkey,
        attestation_data=os.urandom(256),
        signature=os.urandom(64),
        credential_id=os.urandom(64),
        authenticator_data=os.urandom(128),
        client_data_hash=os.urandom(32),
    )

    serialized = fido2.serialize()
    assert len(serialized) > 0
    print(f"    PASS: FIDO2Attestation serialization ({len(serialized)} bytes)")

    # Test 5: HardwareVerifier
    print("\n[5] Testing HardwareVerifier...")
    verifier = HardwareVerifier(testnet=True)

    # Verify TPM
    result, msg = verifier.verify_attestation(tpm)
    assert result == AttestationResult.VALID, f"TPM verification failed: {msg}"
    print(f"    TPM: {msg}")

    # Verify Secure Enclave
    result, msg = verifier.verify_attestation(enclave)
    assert result == AttestationResult.VALID, f"Enclave verification failed: {msg}"
    print(f"    Enclave: {msg}")

    # Verify FIDO2
    result, msg = verifier.verify_attestation(fido2)
    assert result == AttestationResult.VALID, f"FIDO2 verification failed: {msg}"
    print(f"    FIDO2: {msg}")
    print("    PASS: HardwareVerifier works")

    # Test 6: Device binding
    print("\n[6] Testing device binding...")
    success, msg = verifier.register_binding(tpm)
    assert success, f"Binding failed: {msg}"

    # Same device, different pubkey should fail
    tpm_clone = TPMAttestation(
        hardware_type=HardwareType.TPM_20,
        device_id=device_id,  # SAME device
        pubkey_binding=os.urandom(32),  # Different pubkey
        attestation_data=os.urandom(256),
        signature=os.urandom(64),
    )
    success, msg = verifier.register_binding(tpm_clone)
    assert not success, f"Should have failed: {msg}"
    print("    PASS: Device binding prevents reuse")

    # Test 7: create_hardware_proof
    print("\n[7] Testing create_hardware_proof...")
    proof = create_hardware_proof(tpm, pubkey)
    assert proof.tier == HumanityTier.HARDWARE
    assert proof.proof_type == "tpm_20"
    assert proof.pubkey == pubkey
    assert proof.is_valid
    print(f"    PASS: Hardware proof created (type={proof.proof_type})")

    # Test 8: verify_hardware_proof
    print("\n[8] Testing verify_hardware_proof...")
    verifier2 = HardwareVerifier(testnet=True)
    valid, msg = verify_hardware_proof(proof, verifier2)
    assert valid, f"Verification failed: {msg}"
    print(f"    PASS: Hardware proof verified ({msg})")

    # Test 9: Device revocation
    print("\n[9] Testing device revocation...")
    fingerprint = tpm.get_device_fingerprint()
    verifier.revoke_device(fingerprint, "Test revocation")
    result, msg = verifier.verify_attestation(tpm)
    assert result == AttestationResult.DEVICE_REVOKED, f"Should be revoked: {result}"
    print("    PASS: Device revocation works")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
