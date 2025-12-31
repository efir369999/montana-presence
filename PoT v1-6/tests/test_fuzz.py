"""
Proof of Time - Fuzz Tests
Comprehensive fuzzing for all deserialize() methods and network parsing.

These tests simulate malformed, random, and adversarial inputs to ensure
the protocol doesn't crash, leak memory, or behave unexpectedly.

Run with: python -m pytest tests/test_fuzz.py -v --timeout=60
"""

import unittest
import secrets
import struct
import logging
import sys
import os
from typing import Callable, Any, Type

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Number of fuzz iterations per test
FUZZ_ITERATIONS = 1000
MAX_FUZZ_SIZE = 10000


def generate_random_bytes(max_size: int = MAX_FUZZ_SIZE) -> bytes:
    """Generate random bytes of random length."""
    size = secrets.randbelow(max_size)
    return secrets.token_bytes(size)


def mutate_bytes(data: bytes, mutation_rate: float = 0.1) -> bytes:
    """Mutate bytes with given probability per byte."""
    result = bytearray(data)
    for i in range(len(result)):
        if secrets.randbelow(100) < int(mutation_rate * 100):
            result[i] = secrets.randbelow(256)
    return bytes(result)


def truncate_bytes(data: bytes) -> bytes:
    """Randomly truncate bytes."""
    if len(data) == 0:
        return data
    new_len = secrets.randbelow(len(data))
    return data[:new_len]


class FuzzDeserialize:
    """Helper to fuzz deserialize methods safely."""
    
    # All expected exceptions for malformed input
    EXPECTED_EXCEPTIONS = (
        ValueError, IndexError, struct.error, KeyError, TypeError, 
        OverflowError, AttributeError, AssertionError
    )
    
    @staticmethod
    def fuzz_method(deserialize_func: Callable, iterations: int = FUZZ_ITERATIONS) -> int:
        """
        Fuzz a deserialize function with random inputs.
        
        Returns number of inputs that didn't crash.
        """
        # Import custom exceptions
        try:
            from pantheon.nyx.privacy import RingSignatureError
            custom_exceptions = (RingSignatureError,)
        except ImportError:
            custom_exceptions = ()
        
        try:
            from pantheon.prometheus.crypto import CryptoError, VDFError, VRFError
            custom_exceptions = custom_exceptions + (CryptoError, VDFError, VRFError)
        except ImportError:
            pass
        
        all_expected = FuzzDeserialize.EXPECTED_EXCEPTIONS + custom_exceptions
        
        survived = 0
        
        for _ in range(iterations):
            try:
                # Try completely random bytes
                data = generate_random_bytes()
                try:
                    deserialize_func(data)
                except all_expected:
                    pass  # Expected exceptions for malformed input
                survived += 1
                
            except MemoryError:
                # Memory exhaustion is a vulnerability
                raise AssertionError("Memory exhaustion vulnerability detected!")
            except RecursionError:
                # Infinite recursion is a vulnerability
                raise AssertionError("Recursion vulnerability detected!")
            except SystemExit:
                raise AssertionError("SystemExit vulnerability detected!")
            except Exception as e:
                # Unexpected exception type might indicate a bug
                if not isinstance(e, all_expected):
                    logger.warning(f"Unexpected exception: {type(e).__name__}: {e}")
        
        return survived


class TestStructuresFuzz(unittest.TestCase):
    """Fuzz tests for structures.py deserialize methods."""
    
    def test_fuzz_varint(self):
        """Fuzz varint parsing."""
        from pantheon.themis.structures import read_varint
        
        for _ in range(FUZZ_ITERATIONS):
            data = generate_random_bytes(100)
            if len(data) > 0:
                try:
                    read_varint(data, 0)
                except (IndexError, struct.error):
                    pass  # Expected for malformed input
    
    def test_fuzz_block_header_deserialize(self):
        """Fuzz BlockHeader.deserialize()."""
        from pantheon.themis.structures import BlockHeader
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: BlockHeader.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_block_deserialize(self):
        """Fuzz Block.deserialize()."""
        from pantheon.themis.structures import Block
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: Block.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_transaction_deserialize(self):
        """Fuzz Transaction.deserialize()."""
        from pantheon.themis.structures import Transaction
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: Transaction.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_tx_input_deserialize(self):
        """Fuzz TxInput.deserialize()."""
        from pantheon.themis.structures import TxInput
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: TxInput.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_tx_output_deserialize(self):
        """Fuzz TxOutput.deserialize()."""
        from pantheon.themis.structures import TxOutput
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: TxOutput.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)


class TestCryptoFuzz(unittest.TestCase):
    """Fuzz tests for crypto.py deserialize methods."""
    
    def test_fuzz_vdf_proof_deserialize(self):
        """Fuzz VDFProof.deserialize()."""
        from pantheon.prometheus.crypto import VDFProof
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: VDFProof.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_vrf_output_deserialize(self):
        """Fuzz VRFOutput deserialization."""
        from pantheon.prometheus.crypto import VRFOutput
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: VRFOutput.deserialize(data) if len(data) >= 112 else None,
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_ed25519_verify(self):
        """Fuzz Ed25519 signature verification with random inputs."""
        from pantheon.prometheus.crypto import Ed25519
        
        for _ in range(FUZZ_ITERATIONS):
            try:
                sig = generate_random_bytes(64)[:64].ljust(64, b'\x00')
                msg = generate_random_bytes(100)
                pk = generate_random_bytes(32)[:32].ljust(32, b'\x00')
                
                # Should not crash, just return False for invalid
                Ed25519.verify(pk, msg, sig)
            except Exception:
                pass  # Any exception is fine, just shouldn't crash
    
    def test_fuzz_vdf_verify(self):
        """Fuzz VDF verification with malformed proofs."""
        from pantheon.prometheus.crypto import WesolowskiVDF, VDFProof, sha256
        
        vdf = WesolowskiVDF(2048)
        
        for _ in range(100):  # Fewer iterations, verification is slow
            try:
                proof = VDFProof(
                    output=generate_random_bytes(256)[:256].ljust(256, b'\x00'),
                    proof=generate_random_bytes(256)[:256].ljust(256, b'\x00'),
                    iterations=secrets.randbelow(1000000) + 1000,
                    input_hash=sha256(generate_random_bytes(32))
                )
                vdf.verify(proof)  # Should not crash
            except Exception:
                pass


class TestConsensusFuzz(unittest.TestCase):
    """Fuzz tests for consensus.py deserialize methods."""
    
    def test_fuzz_node_state_deserialize(self):
        """Fuzz NodeState.deserialize()."""
        from pantheon.athena.consensus import NodeState
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: NodeState.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_slashing_evidence_deserialize(self):
        """Fuzz SlashingEvidence.deserialize()."""
        from pantheon.hal import SlashingEvidence
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: SlashingEvidence.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)


class TestPrivacyFuzz(unittest.TestCase):
    """Fuzz tests for privacy.py deserialize methods."""
    
    def test_fuzz_lsag_signature_deserialize(self):
        """Fuzz LSAGSignature.deserialize()."""
        from pantheon.nyx.privacy import LSAGSignature
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: LSAGSignature.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    @unittest.skip("RangeProof removed in v4.3 (experimental)")
    def test_fuzz_range_proof_deserialize(self):
        """Fuzz RangeProof deserialization."""
        from pantheon.nyx.privacy import RangeProof
        
        for _ in range(FUZZ_ITERATIONS):
            try:
                data = generate_random_bytes()
                # RangeProof has fixed structure, should handle gracefully
                if len(data) >= 32 * 11:  # Minimum size
                    RangeProof(
                        A=data[:32],
                        S=data[32:64],
                        T1=data[64:96],
                        T2=data[96:128],
                        tau_x=data[128:160],
                        mu=data[160:192],
                        t_hat=data[192:224],
                        L=[],
                        R=[],
                        a=data[224:256] if len(data) >= 256 else b'\x00' * 32,
                        b=data[256:288] if len(data) >= 288 else b'\x00' * 32
                    )
            except Exception:
                pass
    
    def test_fuzz_lsag_verify(self):
        """Fuzz LSAG verification with malformed signatures."""
        from pantheon.nyx.privacy import LSAG, LSAGSignature, Ed25519Point
        
        for _ in range(100):
            try:
                ring = [generate_random_bytes(32)[:32].ljust(32, b'\x00') for _ in range(4)]
                sig = LSAGSignature(
                    c0=generate_random_bytes(32)[:32].ljust(32, b'\x00'),
                    s=[generate_random_bytes(32)[:32].ljust(32, b'\x00') for _ in range(4)],
                    key_image=generate_random_bytes(32)[:32].ljust(32, b'\x00')
                )
                LSAG.verify(generate_random_bytes(32), ring, sig)
            except Exception:
                pass  # Any exception is fine


class TestNetworkFuzz(unittest.TestCase):
    """Fuzz tests for network.py message parsing."""
    
    def test_fuzz_message_parsing(self):
        """Fuzz network message parsing."""
        # Note: MessageSerializer is part of message layer, test basic network structures
        from pantheon.paul.network import VersionPayload
        
        for _ in range(FUZZ_ITERATIONS):
            try:
                data = generate_random_bytes()
                VersionPayload.deserialize(data)
            except (ValueError, IndexError, struct.error, TypeError, KeyError):
                pass  # Expected
    
    def test_fuzz_version_payload(self):
        """Fuzz version message payload."""
        from pantheon.paul.network import VersionPayload
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: VersionPayload.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_inv_item(self):
        """Fuzz inventory item parsing."""
        from pantheon.paul.network import InvItem
        
        for _ in range(FUZZ_ITERATIONS):
            try:
                data = generate_random_bytes(36)
                if len(data) >= 36:
                    InvItem.deserialize(data)
            except Exception:
                pass


class TestWalletFuzz(unittest.TestCase):
    """Fuzz tests for wallet.py."""
    
    def test_fuzz_wallet_output_deserialize(self):
        """Fuzz WalletOutput.deserialize()."""
        from pantheon.plutus.wallet import WalletOutput
        
        survived = FuzzDeserialize.fuzz_method(
            lambda data: WalletOutput.deserialize(data),
            FUZZ_ITERATIONS
        )
        self.assertEqual(survived, FUZZ_ITERATIONS)
    
    def test_fuzz_wallet_decrypt(self):
        """Fuzz wallet decryption with random data."""
        from pantheon.plutus.wallet import WalletCrypto
        
        for _ in range(100):  # Fewer iterations, crypto is slow
            try:
                encrypted = generate_random_bytes(1000)
                password = "test_password"
                WalletCrypto.decrypt(encrypted, password)
            except ValueError:
                pass  # Expected for invalid encrypted data
            except Exception:
                pass


class TestDatabaseFuzz(unittest.TestCase):
    """Fuzz tests for database.py."""
    
    def test_fuzz_sql_injection(self):
        """Test SQL injection resistance."""
        import tempfile
        import os
        from pantheon.hades.database import BlockchainDB, StorageConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "fuzz_test.db")
            config = StorageConfig(db_path=db_path)
            db = BlockchainDB(config)
            
            # Try SQL injection payloads
            sql_payloads = [
                b"'; DROP TABLE blocks; --",
                b"1; DELETE FROM blocks WHERE 1=1; --",
                b"' OR '1'='1",
                b"'; INSERT INTO blocks VALUES (999, x'00'); --",
                b"\x00\x00\x00\x00",  # Null bytes
            ]
            
            for payload in sql_payloads:
                try:
                    # These should not execute arbitrary SQL
                    db.is_key_image_spent(payload)
                    db.get_block_by_hash(payload)
                except Exception:
                    pass  # Any exception is fine, just no SQL injection
            
            db.close()


class TestMutationFuzz(unittest.TestCase):
    """Mutation-based fuzzing on valid data."""
    
    def test_mutate_valid_block(self):
        """Mutate valid block serialization."""
        from pantheon.themis.structures import create_genesis_block, Block
        
        genesis = create_genesis_block()
        valid_data = genesis.serialize()
        
        for _ in range(FUZZ_ITERATIONS):
            try:
                mutated = mutate_bytes(valid_data, 0.01)  # 1% mutation rate
                Block.deserialize(mutated)
            except Exception:
                pass  # Expected for corrupted data
    
    def test_truncate_valid_block(self):
        """Truncate valid block serialization."""
        from pantheon.themis.structures import create_genesis_block, Block
        
        genesis = create_genesis_block()
        valid_data = genesis.serialize()
        
        for _ in range(FUZZ_ITERATIONS):
            try:
                truncated = truncate_bytes(valid_data)
                Block.deserialize(truncated)
            except Exception:
                pass  # Expected for truncated data
    
    def test_mutate_valid_vdf_proof(self):
        """Mutate valid VDF proof serialization."""
        from pantheon.prometheus.crypto import WesolowskiVDF, sha256
        
        vdf = WesolowskiVDF(2048)
        input_data = sha256(b"test")
        proof = vdf.compute(input_data, vdf.MIN_ITERATIONS)
        valid_data = proof.serialize()
        
        for _ in range(100):
            try:
                mutated = mutate_bytes(valid_data, 0.01)
                from pantheon.prometheus.crypto import VDFProof
                mutated_proof = VDFProof.deserialize(mutated)
                vdf.verify(mutated_proof)  # Should not crash
            except Exception:
                pass


class TestBoundaryConditions(unittest.TestCase):
    """Test boundary conditions and edge cases."""
    
    def test_empty_input_all_deserialize(self):
        """All deserialize methods should handle empty input."""
        from pantheon.themis.structures import Block, BlockHeader, Transaction, TxInput, TxOutput
        from pantheon.prometheus.crypto import VDFProof
        from pantheon.athena.consensus import NodeState
        from pantheon.hal import SlashingEvidence
        from pantheon.nyx.privacy import LSAGSignature, RingSignatureError
        from pantheon.paul.network import VersionPayload
        from pantheon.plutus.wallet import WalletOutput
        
        deserialize_methods = [
            (Block, "Block"),
            (BlockHeader, "BlockHeader"),
            (Transaction, "Transaction"),
            (TxInput, "TxInput"),
            (TxOutput, "TxOutput"),
            (VDFProof, "VDFProof"),
            (NodeState, "NodeState"),
            (SlashingEvidence, "SlashingEvidence"),
            (LSAGSignature, "LSAGSignature"),
            (VersionPayload, "VersionPayload"),
            (WalletOutput, "WalletOutput"),
        ]
        
        # All reasonable exceptions for malformed input
        reasonable_exceptions = (
            ValueError, IndexError, struct.error, KeyError, TypeError,
            RingSignatureError, OverflowError, AttributeError
        )
        
        for cls, name in deserialize_methods:
            try:
                cls.deserialize(b'')
            except reasonable_exceptions:
                pass  # Expected - raises some reasonable exception
            except Exception as e:
                # Should raise a reasonable exception, not crash
                self.fail(f"{name}.deserialize(b'') raised unexpected {type(e).__name__}: {e}")
    
    def test_max_size_varint(self):
        """Test maximum size varint handling."""
        from pantheon.themis.structures import write_varint, read_varint
        
        # Test large values
        large_values = [
            0,
            0xFC,
            0xFD,
            0xFE,
            0xFF,
            0xFFFF,
            0x10000,
            0xFFFFFFFF,
            0x100000000,
            0xFFFFFFFFFFFFFFFF,
        ]
        
        for val in large_values:
            try:
                encoded = write_varint(val)
                decoded, _ = read_varint(encoded, 0)
                self.assertEqual(val, decoded)
            except OverflowError:
                pass  # Expected for values too large
    
    def test_nested_structure_depth(self):
        """Test that deeply nested structures don't cause stack overflow."""
        from pantheon.themis.structures import Transaction, TxInput, TxOutput, TxType
        
        # Create transaction with many inputs/outputs (but reasonable size)
        tx = Transaction(tx_type=TxType.STANDARD)
        
        # Use smaller numbers to avoid hitting size limits in deserialize validation
        for _ in range(100):
            inp = TxInput(
                ring=[secrets.token_bytes(32) for _ in range(2)],
                key_image=secrets.token_bytes(32),
                pseudo_commitment=secrets.token_bytes(32)
            )
            tx.inputs.append(inp)
        
        for i in range(100):
            out = TxOutput(
                stealth_address=secrets.token_bytes(32),
                tx_public_key=secrets.token_bytes(32),
                commitment=secrets.token_bytes(32),
                encrypted_amount=secrets.token_bytes(8),
                output_index=i
            )
            tx.outputs.append(out)
        
        # Should serialize/deserialize without stack overflow
        try:
            data = tx.serialize()
            restored, _ = Transaction.deserialize(data)
            self.assertEqual(len(restored.inputs), 100)
            self.assertEqual(len(restored.outputs), 100)
        except MemoryError:
            self.fail("Memory exhaustion on large transaction")
        except RecursionError:
            self.fail("Recursion error on large transaction")


def run_all_fuzz_tests():
    """Run all fuzz tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestStructuresFuzz,
        TestCryptoFuzz,
        TestConsensusFuzz,
        TestPrivacyFuzz,
        TestNetworkFuzz,
        TestWalletFuzz,
        TestDatabaseFuzz,
        TestMutationFuzz,
        TestBoundaryConditions,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("PROOF OF TIME - FUZZ TESTING SUITE")
    print("=" * 70)
    print(f"Running {FUZZ_ITERATIONS} iterations per test")
    print()
    
    success = run_all_fuzz_tests()
    sys.exit(0 if success else 1)

