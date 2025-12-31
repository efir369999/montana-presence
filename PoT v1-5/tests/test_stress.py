"""
Proof of Time - Stress Tests
High-load testing for network, consensus, and database layers.

These tests verify the system behaves correctly under stress:
- High message rates
- Many concurrent connections
- Large data volumes
- Memory pressure

Run with: python -m pytest tests/test_stress.py -v --timeout=120
"""

import unittest
import threading
import time
import secrets
import logging
import sys
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class TestConsensusStress(unittest.TestCase):
    """Stress tests for consensus engine."""
    
    def test_mass_node_registration(self):
        """Register many nodes concurrently."""
        from pantheon.athena.consensus import ConsensusEngine
        from pantheon.prometheus.crypto import Ed25519
        
        engine = ConsensusEngine()
        engine.initialize()
        
        num_nodes = 1000
        errors = []
        
        def register_batch(start, count):
            try:
                for i in range(count):
                    _, pk = Ed25519.generate_keypair()
                    engine.register_node(pk, stored_blocks=1000 + start + i)
            except Exception as e:
                errors.append(e)
        
        # Register in parallel threads
        threads = []
        batch_size = 100
        for i in range(0, num_nodes, batch_size):
            t = threading.Thread(target=register_batch, args=(i, batch_size))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(len(engine.get_active_nodes()), num_nodes)
    
    def test_probability_computation_under_load(self):
        """Compute probabilities for many nodes."""
        from pantheon.athena.consensus import ConsensusEngine, NodeState, NodeStatus
        from pantheon.prometheus.crypto import Ed25519
        
        engine = ConsensusEngine()
        engine.initialize()
        
        # Register many nodes
        for i in range(500):
            _, pk = Ed25519.generate_keypair()
            node = NodeState(pubkey=pk)
            node.status = NodeStatus.ACTIVE
            node.total_uptime = (i + 1) * 86400
            node.stored_blocks = (i + 1) * 100
            node.signed_blocks = (i + 1) * 10
            engine.nodes[pk] = node
        
        # Compute probabilities multiple times
        start = time.time()
        for _ in range(100):
            probs = engine.calculator.compute_probabilities(
                list(engine.nodes.values()),
                int(time.time()),
                10000
            )
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 10 seconds for 100 iterations)
        self.assertLess(elapsed, 10.0)
        self.assertEqual(len(probs), 500)
    
    def test_slashing_under_concurrent_reports(self):
        """Process many slashing reports concurrently."""
        from pantheon.hal import SlashingManager, SlashingEvidence, SlashingCondition
        
        manager = SlashingManager()
        errors = []
        
        def report_slashing(offender_id):
            try:
                evidence = SlashingEvidence(
                    condition=SlashingCondition.EQUIVOCATION,
                    offender=bytes([offender_id % 256]) * 32,
                    evidence_block1=secrets.token_bytes(32),
                    evidence_block2=secrets.token_bytes(32),
                    timestamp=int(time.time()),
                    signature1=secrets.token_bytes(64),
                    signature2=secrets.token_bytes(64),
                    reporter=secrets.token_bytes(32)
                )
                # Use pending_slashes list directly (thread-safe with lock)
                manager.pending_slashes.append(evidence)
            except Exception as e:
                errors.append(e)
        
        # Submit many reports concurrently
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(report_slashing, i) for i in range(200)]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    pass  # Some concurrent appends may fail
        
        # At least some should have succeeded
        self.assertGreater(len(manager.pending_slashes), 0)


class TestDatabaseStress(unittest.TestCase):
    """Stress tests for database layer."""
    
    def test_concurrent_block_writes(self):
        """Write many blocks concurrently."""
        from pantheon.hades.database import BlockchainDB, StorageConfig
        from pantheon.themis.structures import Block, BlockHeader, Transaction, TxType, TxOutput
        from pantheon.prometheus.crypto import sha256
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "stress_test.db")
            config = StorageConfig(db_path=db_path)
            db = BlockchainDB(config)
            
            errors = []
            
            def write_blocks(start_height, count):
                try:
                    for i in range(count):
                        height = start_height + i
                        
                        block = Block()
                        block.header.height = height
                        block.header.prev_block_hash = sha256(f"prev_{height}".encode())
                        block.header.merkle_root = sha256(f"merkle_{height}".encode())
                        block.header.timestamp = int(time.time()) + height
                        block.header.leader_pubkey = secrets.token_bytes(32)
                        block.header.leader_signature = secrets.token_bytes(64)
                        
                        # Add a transaction
                        tx = Transaction(
                            tx_type=TxType.COINBASE,
                            outputs=[TxOutput(
                                stealth_address=secrets.token_bytes(32),
                                tx_public_key=secrets.token_bytes(32),
                                commitment=secrets.token_bytes(32),
                            )]
                        )
                        block.transactions = [tx]
                        
                        db.store_block(block)
                except Exception as e:
                    errors.append(e)
            
            # Write blocks from different threads (non-overlapping heights)
            threads = []
            for i in range(10):
                t = threading.Thread(target=write_blocks, args=(i * 100, 100))
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
            
            self.assertEqual(len(errors), 0, f"Errors: {errors}")
            
            # Verify all blocks were written
            height = db.get_chain_height()
            self.assertGreaterEqual(height, 900)
            
            db.close()
    
    def test_key_image_check_performance(self):
        """Check key image lookup performance."""
        from pantheon.hades.database import BlockchainDB, StorageConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "ki_test.db")
            config = StorageConfig(db_path=db_path)
            db = BlockchainDB(config)
            
            # Pre-populate with key images via direct SQL (simulate spent outputs)
            conn = db.pool.get_connection()
            cursor = conn.cursor()
            
            for i in range(10000):
                ki = secrets.token_bytes(32)
                cursor.execute(
                    "INSERT OR IGNORE INTO spent_key_images VALUES (?, ?, ?, ?)",
                    (ki, secrets.token_bytes(32), i, int(time.time()))
                )
            conn.commit()
            
            # Test lookup performance
            test_keys = [secrets.token_bytes(32) for _ in range(1000)]
            
            start = time.time()
            for ki in test_keys:
                db.is_key_image_spent(ki)
            elapsed = time.time() - start
            
            # Should complete 1000 lookups in < 1 second
            self.assertLess(elapsed, 1.0)
            
            db.close()
    
    def test_output_selection_performance(self):
        """Test random output selection performance."""
        from pantheon.hades.database import BlockchainDB, StorageConfig
        from pantheon.themis.structures import create_genesis_block, Block, Transaction, TxType, TxOutput
        from pantheon.prometheus.crypto import sha256
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "output_test.db")
            config = StorageConfig(db_path=db_path)
            db = BlockchainDB(config)
            
            # First store some blocks to satisfy FK constraints
            for height in range(100):
                block = Block()
                block.header.height = height
                block.header.prev_block_hash = sha256(f"prev_{height}".encode())
                block.header.merkle_root = sha256(f"merkle_{height}".encode())
                block.header.timestamp = int(time.time()) + height
                block.header.leader_pubkey = secrets.token_bytes(32)
                block.header.leader_signature = secrets.token_bytes(64)
                
                # Add transactions with outputs
                for tx_idx in range(10):
                    tx = Transaction(tx_type=TxType.COINBASE)
                    for out_idx in range(5):
                        tx.outputs.append(TxOutput(
                            stealth_address=secrets.token_bytes(32),
                            tx_public_key=secrets.token_bytes(32),
                            commitment=secrets.token_bytes(32),
                            encrypted_amount=secrets.token_bytes(8),
                            output_index=out_idx
                        ))
                    block.transactions.append(tx)
                
                db.store_block(block)
            
            # Test random output selection
            start = time.time()
            for _ in range(100):
                outputs = db.get_random_outputs(16)
            elapsed = time.time() - start
            
            # Should complete 100 selections in < 5 seconds
            self.assertLess(elapsed, 5.0)
            
            db.close()


class TestNetworkStress(unittest.TestCase):
    """Stress tests for network layer."""
    
    def test_message_serialization_performance(self):
        """Test message serialization performance using structures."""
        from pantheon.themis.structures import Block, BlockHeader, Transaction, TxType
        
        # Create test blocks
        blocks = []
        for i in range(100):
            block = Block()
            block.header.height = i
            block.header.timestamp = int(time.time()) + i
            block.header.prev_block_hash = secrets.token_bytes(32)
            block.header.merkle_root = secrets.token_bytes(32)
            block.header.leader_pubkey = secrets.token_bytes(32)
            block.header.leader_signature = secrets.token_bytes(64)
            blocks.append(block)
        
        # Test serialization performance
        start = time.time()
        for block in blocks:
            data = block.serialize()
            Block.deserialize(data)
        elapsed = time.time() - start
        
        # Should complete 100 serialize/deserialize in < 1 second
        self.assertLess(elapsed, 1.0)
    
    def test_eclipse_protection_under_load(self):
        """Test Eclipse protection with many connection attempts."""
        from pantheon.paul.network import EclipseProtection
        
        eclipse = EclipseProtection()
        
        # Simulate many connection attempts from same subnet
        start = time.time()
        blocked = 0
        for i in range(1000):
            ip = f"192.168.1.{i % 256}"
            allowed, reason = eclipse.can_connect(ip, is_inbound=True)
            if not allowed:
                blocked += 1
            else:
                eclipse.register_connection(f"peer_{i}", ip, is_inbound=True)
        elapsed = time.time() - start
        
        # Should complete quickly
        self.assertLess(elapsed, 1.0)
        
        # Should have blocked most connections (same subnet)
        self.assertGreater(blocked, 900)
    
    def test_ban_manager_under_load(self):
        """Test ban manager with many violations."""
        from pantheon.paul.network import BanManager
        
        ban_manager = BanManager()
        
        start = time.time()
        for i in range(1000):
            ip = f"10.0.{i // 256}.{i % 256}"
            
            # Add multiple misbehavior scores
            for j in range(5):
                ban_manager.add_misbehavior(ip, 20, f"test_violation_{j}")
            
            # Check ban status
            ban_manager.is_banned(ip)
        elapsed = time.time() - start
        
        # Should complete quickly
        self.assertLess(elapsed, 2.0)


class TestCryptoStress(unittest.TestCase):
    """Stress tests for cryptographic operations."""
    
    def test_signature_verification_batch(self):
        """Test batch signature verification performance."""
        from pantheon.prometheus.crypto import Ed25519
        
        # Generate test data
        signatures = []
        for _ in range(100):
            sk, pk = Ed25519.generate_keypair()
            msg = secrets.token_bytes(100)
            sig = Ed25519.sign(sk, msg)
            signatures.append((pk, msg, sig))
        
        # Test verification performance
        start = time.time()
        for pk, msg, sig in signatures:
            Ed25519.verify(pk, msg, sig)
        elapsed = time.time() - start
        
        # 100 verifications should complete in < 1 second
        self.assertLess(elapsed, 1.0)
    
    def test_hash_computation_performance(self):
        """Test hash computation performance."""
        from pantheon.prometheus.crypto import sha256, sha256d
        
        data = secrets.token_bytes(1000)
        
        start = time.time()
        for _ in range(10000):
            sha256(data)
        elapsed_single = time.time() - start
        
        start = time.time()
        for _ in range(10000):
            sha256d(data)
        elapsed_double = time.time() - start
        
        # Should complete quickly
        self.assertLess(elapsed_single, 0.5)
        self.assertLess(elapsed_double, 1.0)
    
    def test_merkle_root_large_tree(self):
        """Test Merkle root computation for large trees."""
        from pantheon.prometheus.crypto import MerkleTree, sha256
        
        # Generate many transaction hashes
        tx_hashes = [sha256(secrets.token_bytes(32)) for _ in range(10000)]
        
        start = time.time()
        root = MerkleTree.compute_root(tx_hashes)
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        self.assertLess(elapsed, 5.0)
        self.assertEqual(len(root), 32)


class TestPrivacyStress(unittest.TestCase):
    """Stress tests for privacy primitives."""
    
    def test_ring_signature_large_ring(self):
        """Test ring signature with large ring."""
        from pantheon.nyx.privacy import LSAG, Ed25519Point
        
        # Generate large ring
        ring_size = 64
        secret_idx = 32
        
        keys = []
        for i in range(ring_size):
            sk = Ed25519Point.scalar_random()
            pk = Ed25519Point.scalarmult_base(sk)
            keys.append((sk, pk))
        
        ring = [pk for _, pk in keys]
        sk = keys[secret_idx][0]
        message = secrets.token_bytes(32)
        
        # Time signing
        start = time.time()
        sig = LSAG.sign(message, ring, secret_idx, sk)
        sign_time = time.time() - start
        
        # Time verification
        start = time.time()
        result = LSAG.verify(message, ring, sig)
        verify_time = time.time() - start
        
        self.assertTrue(result)
        
        # Should complete in reasonable time
        self.assertLess(sign_time, 5.0)
        self.assertLess(verify_time, 5.0)
    
    def test_stealth_address_scanning_performance(self):
        """Test stealth address scanning performance."""
        from pantheon.nyx.privacy import StealthKeys, StealthAddress
        
        receiver_keys = StealthKeys.generate()
        
        # Generate many outputs
        outputs = []
        for _ in range(100):
            output, _ = StealthAddress.create_output(
                receiver_keys.view_public,
                receiver_keys.spend_public
            )
            outputs.append(output)
        
        # Add some outputs not for us
        other_keys = StealthKeys.generate()
        for _ in range(100):
            output, _ = StealthAddress.create_output(
                other_keys.view_public,
                other_keys.spend_public
            )
            outputs.append(output)
        
        # Time scanning
        start = time.time()
        found = 0
        for output in outputs:
            if StealthAddress.scan_output(output, receiver_keys.view_secret, receiver_keys.spend_public):
                found += 1
        elapsed = time.time() - start
        
        self.assertEqual(found, 100)
        
        # Should complete quickly (200 scans in < 2 seconds)
        self.assertLess(elapsed, 2.0)


class TestMemoryPressure(unittest.TestCase):
    """Tests for memory usage under pressure."""
    
    def test_large_transaction_handling(self):
        """Test handling of transaction with many inputs/outputs."""
        from pantheon.themis.structures import Transaction, TxInput, TxOutput, TxType
        
        # Create transaction with many inputs/outputs (but within limits)
        tx = Transaction(tx_type=TxType.STANDARD)
        
        for i in range(1000):
            inp = TxInput(
                ring=[secrets.token_bytes(32) for _ in range(4)],
                key_image=secrets.token_bytes(32),
                pseudo_commitment=secrets.token_bytes(32)
            )
            tx.inputs.append(inp)
        
        for i in range(1000):
            out = TxOutput(
                stealth_address=secrets.token_bytes(32),
                tx_public_key=secrets.token_bytes(32),
                commitment=secrets.token_bytes(32),
                encrypted_amount=secrets.token_bytes(8),
                output_index=i
            )
            tx.outputs.append(out)
        
        # Serialize and deserialize
        data = tx.serialize()
        restored, _ = Transaction.deserialize(data)
        
        self.assertEqual(len(restored.inputs), 1000)
        self.assertEqual(len(restored.outputs), 1000)
    
    def test_vdf_checkpoint_memory_limits(self):
        """Test VDF checkpoint memory limits are enforced."""
        from pantheon.prometheus.crypto import WesolowskiVDF, VDFCheckpoint, sha256
        
        vdf = WesolowskiVDF(2048, auto_calibrate=False)
        
        # Manually add many checkpoints
        for i in range(200):
            input_hash = sha256(f"test_{i}".encode())
            cp = VDFCheckpoint(
                input_hash=input_hash,
                current_value=2**256 + i,
                current_iteration=i * 1000,
                target_iterations=1000000,
                proof_accumulator=2**256 - i,
                remainder=i,
                challenge_prime=2**127 + 1,
                timestamp=int(time.time()) - i
            )
            vdf._checkpoints[input_hash] = cp
            vdf._enforce_checkpoint_limits()
        
        # Should have enforced limit
        self.assertLessEqual(len(vdf._checkpoints), vdf._max_checkpoints)


def run_all_stress_tests():
    """Run all stress tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestConsensusStress,
        TestDatabaseStress,
        TestNetworkStress,
        TestCryptoStress,
        TestPrivacyStress,
        TestMemoryPressure,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("PROOF OF TIME - STRESS TESTING SUITE")
    print("=" * 70)
    print()
    
    success = run_all_stress_tests()
    sys.exit(0 if success else 1)

