"""
ATC Protocol v7 Error Handling
Part XVIII of Technical Specification

All error codes and exception classes.
"""

from enum import IntEnum
from typing import Optional, Any


class ErrorCode(IntEnum):
    """Protocol error codes."""

    # 1xxx - General errors
    UNKNOWN_ERROR = 1000
    INVALID_PARAMETER = 1001
    INTERNAL_ERROR = 1002
    NOT_IMPLEMENTED = 1003

    # 2xxx - Layer 0 (Atomic Time) errors
    INSUFFICIENT_TIME_SOURCES = 2001
    INSUFFICIENT_REGIONS = 2002
    EXCESSIVE_TIME_DRIFT = 2003
    NTP_TIMEOUT = 2004
    NTP_NETWORK_ERROR = 2005

    # 3xxx - Layer 1 (VDF) errors
    VDF_SEED_MISMATCH = 3001
    INSUFFICIENT_VDF_ITERATIONS = 3002
    INVALID_VDF_PROOF = 3003
    VDF_CHECKPOINT_ERROR = 3004
    STARK_VERIFICATION_FAILED = 3005

    # 4xxx - Layer 2 (Bitcoin) errors
    INVALID_BITCOIN_ANCHOR = 4001
    BITCOIN_HEIGHT_TOO_OLD = 4002
    BITCOIN_HASH_MISMATCH = 4003
    BITCOIN_API_UNAVAILABLE = 4004
    NO_BITCOIN_CONSENSUS = 4005
    INVALID_EPOCH = 4006

    # 5xxx - Heartbeat errors
    INVALID_HEARTBEAT_SEQUENCE = 5001
    INVALID_HEARTBEAT_SIGNATURE = 5002
    CROSS_LAYER_INCONSISTENT = 5003
    DUPLICATE_HEARTBEAT = 5004

    # 6xxx - Transaction errors
    SENDER_NOT_FOUND = 6001
    INSUFFICIENT_BALANCE = 6002
    INVALID_NONCE = 6003
    ZERO_AMOUNT = 6004
    INSUFFICIENT_POW_DIFFICULTY = 6005
    INVALID_POW = 6006
    INVALID_TX_SIGNATURE = 6007
    TRANSACTION_EXPIRED = 6008
    INVALID_MEMO_LENGTH = 6009

    # 7xxx - Block errors
    INVALID_VERSION = 7001
    INVALID_HEIGHT = 7002
    INVALID_PARENT_HASH = 7003
    BLOCK_TOO_LARGE = 7004
    TOO_MANY_HEARTBEATS = 7005
    TOO_MANY_TRANSACTIONS = 7006
    INVALID_MERKLE_ROOT = 7007
    INVALID_STATE_ROOT = 7008
    INVALID_SIGNER = 7009

    # 8xxx - Network errors
    PEER_UNREACHABLE = 8001
    HANDSHAKE_FAILED = 8002
    PROTOCOL_MISMATCH = 8003
    MESSAGE_TOO_LARGE = 8004
    INVALID_CHECKSUM = 8005


class ATCError(Exception):
    """Base exception for all ATC protocol errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Any] = None
    ):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"[{code.value}] {message}")

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for API responses."""
        result = {
            "code": self.code.value,
            "name": self.code.name,
            "message": self.message,
        }
        if self.details is not None:
            result["details"] = self.details
        return result


# ==============================================================================
# General Errors (1xxx)
# ==============================================================================

class UnknownError(ATCError):
    def __init__(self, message: str = "Unknown error occurred", details: Any = None):
        super().__init__(ErrorCode.UNKNOWN_ERROR, message, details)


class InvalidParameterError(ATCError):
    def __init__(self, param: str, message: str = ""):
        msg = f"Invalid parameter: {param}"
        if message:
            msg += f" - {message}"
        super().__init__(ErrorCode.INVALID_PARAMETER, msg, {"parameter": param})


class InternalError(ATCError):
    def __init__(self, message: str = "Internal error", details: Any = None):
        super().__init__(ErrorCode.INTERNAL_ERROR, message, details)


class NotImplementedError(ATCError):
    def __init__(self, feature: str):
        super().__init__(
            ErrorCode.NOT_IMPLEMENTED,
            f"Feature not implemented: {feature}",
            {"feature": feature}
        )


# ==============================================================================
# Layer 0 Errors (2xxx) - Atomic Time
# ==============================================================================

class InsufficientTimeSourcesError(ATCError):
    def __init__(self, count: int, required: int):
        super().__init__(
            ErrorCode.INSUFFICIENT_TIME_SOURCES,
            f"Insufficient time sources: {count} < {required}",
            {"count": count, "required": required}
        )


class InsufficientRegionsError(ATCError):
    def __init__(self, count: int, required: int):
        super().__init__(
            ErrorCode.INSUFFICIENT_REGIONS,
            f"Insufficient regions: {count} < {required}",
            {"count": count, "required": required}
        )


class ExcessiveTimeDriftError(ATCError):
    def __init__(self, drift_ms: int, max_drift_ms: int):
        super().__init__(
            ErrorCode.EXCESSIVE_TIME_DRIFT,
            f"Excessive time drift: {drift_ms}ms > {max_drift_ms}ms",
            {"drift_ms": drift_ms, "max_drift_ms": max_drift_ms}
        )


class NTPTimeoutError(ATCError):
    def __init__(self, server: str):
        super().__init__(
            ErrorCode.NTP_TIMEOUT,
            f"NTP query timeout: {server}",
            {"server": server}
        )


class NTPNetworkError(ATCError):
    def __init__(self, server: str, error: str):
        super().__init__(
            ErrorCode.NTP_NETWORK_ERROR,
            f"NTP network error for {server}: {error}",
            {"server": server, "error": error}
        )


# ==============================================================================
# Layer 1 Errors (3xxx) - VDF
# ==============================================================================

class VDFSeedMismatchError(ATCError):
    def __init__(self, expected: bytes, got: bytes):
        super().__init__(
            ErrorCode.VDF_SEED_MISMATCH,
            "VDF seed does not match expected value",
            {"expected": expected.hex(), "got": got.hex()}
        )


class InsufficientVDFIterationsError(ATCError):
    def __init__(self, iterations: int, required: int):
        super().__init__(
            ErrorCode.INSUFFICIENT_VDF_ITERATIONS,
            f"Insufficient VDF iterations: {iterations} < {required}",
            {"iterations": iterations, "required": required}
        )


class InvalidVDFProofError(ATCError):
    def __init__(self, reason: str = ""):
        msg = "Invalid VDF proof"
        if reason:
            msg += f": {reason}"
        super().__init__(ErrorCode.INVALID_VDF_PROOF, msg)


class VDFCheckpointError(ATCError):
    def __init__(self, checkpoint_index: int, reason: str):
        super().__init__(
            ErrorCode.VDF_CHECKPOINT_ERROR,
            f"VDF checkpoint error at index {checkpoint_index}: {reason}",
            {"checkpoint_index": checkpoint_index, "reason": reason}
        )


class STARKVerificationFailedError(ATCError):
    def __init__(self, reason: str = ""):
        msg = "STARK proof verification failed"
        if reason:
            msg += f": {reason}"
        super().__init__(ErrorCode.STARK_VERIFICATION_FAILED, msg)


# ==============================================================================
# Layer 2 Errors (4xxx) - Bitcoin
# ==============================================================================

class InvalidBitcoinAnchorError(ATCError):
    def __init__(self, reason: str):
        super().__init__(
            ErrorCode.INVALID_BITCOIN_ANCHOR,
            f"Invalid Bitcoin anchor: {reason}"
        )


class BitcoinHeightTooOldError(ATCError):
    def __init__(self, height: int, current: int, max_drift: int):
        super().__init__(
            ErrorCode.BITCOIN_HEIGHT_TOO_OLD,
            f"Bitcoin height too old: {height} (current: {current}, max drift: {max_drift})",
            {"height": height, "current": current, "max_drift": max_drift}
        )


class BitcoinHashMismatchError(ATCError):
    def __init__(self, height: int, expected: bytes, got: bytes):
        super().__init__(
            ErrorCode.BITCOIN_HASH_MISMATCH,
            f"Bitcoin hash mismatch at height {height}",
            {"height": height, "expected": expected.hex(), "got": got.hex()}
        )


class BitcoinAPIUnavailableError(ATCError):
    def __init__(self, apis_tried: int):
        super().__init__(
            ErrorCode.BITCOIN_API_UNAVAILABLE,
            f"All Bitcoin APIs unavailable ({apis_tried} tried)",
            {"apis_tried": apis_tried}
        )


class NoBitcoinConsensusError(ATCError):
    def __init__(self, responses: int, required: int):
        super().__init__(
            ErrorCode.NO_BITCOIN_CONSENSUS,
            f"No Bitcoin consensus: {responses} agreeing < {required} required",
            {"responses": responses, "required": required}
        )


class InvalidEpochError(ATCError):
    def __init__(self, epoch: int, expected: int):
        super().__init__(
            ErrorCode.INVALID_EPOCH,
            f"Invalid epoch: {epoch} (expected: {expected})",
            {"epoch": epoch, "expected": expected}
        )


# ==============================================================================
# Heartbeat Errors (5xxx)
# ==============================================================================

class InvalidHeartbeatSequenceError(ATCError):
    def __init__(self, sequence: int, expected: int):
        super().__init__(
            ErrorCode.INVALID_HEARTBEAT_SEQUENCE,
            f"Invalid heartbeat sequence: {sequence} (expected: {expected})",
            {"sequence": sequence, "expected": expected}
        )


class InvalidHeartbeatSignatureError(ATCError):
    def __init__(self):
        super().__init__(
            ErrorCode.INVALID_HEARTBEAT_SIGNATURE,
            "Heartbeat signature verification failed"
        )


class CrossLayerInconsistentError(ATCError):
    def __init__(self, reason: str):
        super().__init__(
            ErrorCode.CROSS_LAYER_INCONSISTENT,
            f"Cross-layer time inconsistency: {reason}"
        )


class DuplicateHeartbeatError(ATCError):
    def __init__(self, heartbeat_id: bytes):
        super().__init__(
            ErrorCode.DUPLICATE_HEARTBEAT,
            f"Duplicate heartbeat: {heartbeat_id.hex()[:16]}...",
            {"heartbeat_id": heartbeat_id.hex()}
        )


# ==============================================================================
# Transaction Errors (6xxx)
# ==============================================================================

class SenderNotFoundError(ATCError):
    def __init__(self, pubkey: bytes):
        super().__init__(
            ErrorCode.SENDER_NOT_FOUND,
            f"Sender account not found: {pubkey.hex()[:16]}...",
            {"pubkey": pubkey.hex()}
        )


class InsufficientBalanceError(ATCError):
    def __init__(self, balance: int, amount: int):
        super().__init__(
            ErrorCode.INSUFFICIENT_BALANCE,
            f"Insufficient balance: {balance} < {amount}",
            {"balance": balance, "amount": amount}
        )


class InvalidNonceError(ATCError):
    def __init__(self, nonce: int, expected: int):
        super().__init__(
            ErrorCode.INVALID_NONCE,
            f"Invalid nonce: {nonce} (expected: {expected})",
            {"nonce": nonce, "expected": expected}
        )


class ZeroAmountError(ATCError):
    def __init__(self):
        super().__init__(
            ErrorCode.ZERO_AMOUNT,
            "Transaction amount cannot be zero"
        )


class InsufficientPOWDifficultyError(ATCError):
    def __init__(self, difficulty: int, required: int):
        super().__init__(
            ErrorCode.INSUFFICIENT_POW_DIFFICULTY,
            f"Insufficient PoW difficulty: {difficulty} < {required}",
            {"difficulty": difficulty, "required": required}
        )


class InvalidPOWError(ATCError):
    def __init__(self, reason: str = ""):
        msg = "Invalid proof of work"
        if reason:
            msg += f": {reason}"
        super().__init__(ErrorCode.INVALID_POW, msg)


class InvalidTxSignatureError(ATCError):
    def __init__(self):
        super().__init__(
            ErrorCode.INVALID_TX_SIGNATURE,
            "Transaction signature verification failed"
        )


class TransactionExpiredError(ATCError):
    def __init__(self, age_ms: int, max_age_ms: int):
        super().__init__(
            ErrorCode.TRANSACTION_EXPIRED,
            f"Transaction expired: {age_ms}ms > {max_age_ms}ms",
            {"age_ms": age_ms, "max_age_ms": max_age_ms}
        )


class InvalidMemoLengthError(ATCError):
    def __init__(self, length: int, max_length: int):
        super().__init__(
            ErrorCode.INVALID_MEMO_LENGTH,
            f"Memo too long: {length} > {max_length}",
            {"length": length, "max_length": max_length}
        )


# ==============================================================================
# Block Errors (7xxx)
# ==============================================================================

class InvalidVersionError(ATCError):
    def __init__(self, version: int, expected: int):
        super().__init__(
            ErrorCode.INVALID_VERSION,
            f"Invalid protocol version: {version} (expected: {expected})",
            {"version": version, "expected": expected}
        )


class InvalidHeightError(ATCError):
    def __init__(self, height: int, expected: int):
        super().__init__(
            ErrorCode.INVALID_HEIGHT,
            f"Invalid block height: {height} (expected: {expected})",
            {"height": height, "expected": expected}
        )


class InvalidParentHashError(ATCError):
    def __init__(self, expected: bytes, got: bytes):
        super().__init__(
            ErrorCode.INVALID_PARENT_HASH,
            "Block parent hash mismatch",
            {"expected": expected.hex(), "got": got.hex()}
        )


class BlockTooLargeError(ATCError):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            ErrorCode.BLOCK_TOO_LARGE,
            f"Block too large: {size} > {max_size}",
            {"size": size, "max_size": max_size}
        )


class TooManyHeartbeatsError(ATCError):
    def __init__(self, count: int, max_count: int):
        super().__init__(
            ErrorCode.TOO_MANY_HEARTBEATS,
            f"Too many heartbeats in block: {count} > {max_count}",
            {"count": count, "max_count": max_count}
        )


class TooManyTransactionsError(ATCError):
    def __init__(self, count: int, max_count: int):
        super().__init__(
            ErrorCode.TOO_MANY_TRANSACTIONS,
            f"Too many transactions in block: {count} > {max_count}",
            {"count": count, "max_count": max_count}
        )


class InvalidMerkleRootError(ATCError):
    def __init__(self, field: str, expected: bytes, got: bytes):
        super().__init__(
            ErrorCode.INVALID_MERKLE_ROOT,
            f"Invalid {field} Merkle root",
            {"field": field, "expected": expected.hex(), "got": got.hex()}
        )


class InvalidStateRootError(ATCError):
    def __init__(self, expected: bytes, got: bytes):
        super().__init__(
            ErrorCode.INVALID_STATE_ROOT,
            "Invalid state root",
            {"expected": expected.hex(), "got": got.hex()}
        )


class InvalidSignerError(ATCError):
    def __init__(self, pubkey: bytes, reason: str):
        super().__init__(
            ErrorCode.INVALID_SIGNER,
            f"Invalid block signer {pubkey.hex()[:16]}...: {reason}",
            {"pubkey": pubkey.hex(), "reason": reason}
        )


# ==============================================================================
# Network Errors (8xxx)
# ==============================================================================

class PeerUnreachableError(ATCError):
    def __init__(self, address: str):
        super().__init__(
            ErrorCode.PEER_UNREACHABLE,
            f"Peer unreachable: {address}",
            {"address": address}
        )


class HandshakeFailedError(ATCError):
    def __init__(self, peer: str, reason: str):
        super().__init__(
            ErrorCode.HANDSHAKE_FAILED,
            f"Handshake failed with {peer}: {reason}",
            {"peer": peer, "reason": reason}
        )


class ProtocolMismatchError(ATCError):
    def __init__(self, peer_version: int, our_version: int):
        super().__init__(
            ErrorCode.PROTOCOL_MISMATCH,
            f"Protocol version mismatch: peer={peer_version}, ours={our_version}",
            {"peer_version": peer_version, "our_version": our_version}
        )


class MessageTooLargeError(ATCError):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            ErrorCode.MESSAGE_TOO_LARGE,
            f"Message too large: {size} > {max_size}",
            {"size": size, "max_size": max_size}
        )


class InvalidChecksumError(ATCError):
    def __init__(self):
        super().__init__(
            ErrorCode.INVALID_CHECKSUM,
            "Message checksum verification failed"
        )
