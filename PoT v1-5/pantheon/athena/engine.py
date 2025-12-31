"""
Proof of Time - Complete Protocol Engine
Unified implementation combining DAG, tiered privacy, and consensus.

Based on:
- ProofOfTime_TechnicalSpec_v1.1.pdf
- ProofOfTime_DAG_Addendum.pdf

This is the main entry point for running a Proof of Time node.

Time is the ultimate proof.
"""

import os
import time
import logging
import threading
import queue
from typing import Dict, List, Optional, Tuple, Callable
from enum import IntEnum

# Core modules
from config import NodeConfig
from pantheon.prometheus import Ed25519
from pantheon.athena import (
    NodeState, NodeStatus, ConsensusCalculator,
    WeightRebalancer, ProbabilityWeights
)

# HAL reputation module (Human Analyse Language)
from pantheon.hal import HalEngine, HalProfile, ReputationEvent, SlashingManager

# DAG modules
from pantheon.hades.dag import DAGBlock, DAGConsensusEngine, DAGBlockProducer
from pantheon.hades.dag_storage import DAGStorage

# Privacy modules
from pantheon.nyx import (
    PrivacyTier, TieredTransaction, TieredTransactionBuilder,
    TierValidator, AnonymitySetManager, TIER_SPECS
)

logger = logging.getLogger("proof_of_time.engine")


# ============================================================================
# ENGINE STATE
# ============================================================================

class EngineState(IntEnum):
    """Engine lifecycle states."""
    STOPPED = 0
    STARTING = 1
    SYNCING = 2
    RUNNING = 3
    STOPPING = 4


# ============================================================================
# PROOF OF TIME NODE
# ============================================================================

class ProofOfTimeNode:
    """
    Complete Proof of Time node implementation.
    
    Combines:
    - DAG-based block structure
    - PHANTOM-PoT ordering
    - Tiered privacy (T0-T3)
    - Proof of Time (PoT) consensus with VDF finality
    - Time-weighted node influence (HAL)
    """
    
    def __init__(
        self,
        config: Optional[NodeConfig] = None,
        private_key: Optional[bytes] = None
    ):
        self.config = config or NodeConfig()
        
        # Generate or use provided keys
        if private_key:
            self.private_key = private_key
            self.public_key = Ed25519.derive_public_key(private_key)
        else:
            self.private_key, self.public_key = Ed25519.generate_keypair()
        
        # State
        self.state = EngineState.STOPPED
        self._lock = threading.RLock()

        # Safety gate: refuse to run without explicit opt-in while critical
        # production gaps (finality, economic validation, audited crypto) remain.
        if os.getenv("POT_ALLOW_UNSAFE") != "1":
            raise RuntimeError(
                "Proof of Time node is blocked: critical features (finality, "
                "economic validation, audited privacy/VDF fallback) are incomplete. "
                "Set POT_ALLOW_UNSAFE=1 to run at your own risk."
            )
        
        # Initialize components
        self._init_components()
        
        logger.info(f"ProofOfTimeNode initialized with pubkey {self.public_key.hex()[:16]}...")
    
    def _init_components(self):
        """Initialize all node components."""
        # Storage
        self.storage = DAGStorage(self.config.storage)
        
        # DAG consensus
        self.dag_engine = DAGConsensusEngine()
        
        # Block producer
        self.block_producer = DAGBlockProducer(
            self.dag_engine,
            self.private_key,
            self.public_key
        )
        
        # Consensus calculators (DAG - no leader selection)
        self.consensus_calc = ConsensusCalculator()

        # Weight rebalancer with default weights
        self.weight_rebalancer = WeightRebalancer(ProbabilityWeights())

        # Slashing manager (from HAL)
        self.slashing_manager = SlashingManager()

        # HAL reputation engine
        self.hal = HalEngine()
        
        # Node state
        self.node_state = NodeState(
            pubkey=self.public_key,
            uptime_start=int(time.time()),
            total_uptime=0,
            stored_blocks=0,
            signed_blocks=0,
            status=NodeStatus.ACTIVE,
            last_seen=int(time.time())
        )
        
        # Anonymity set manager for T3 decoys
        self.anonymity_manager = AnonymitySetManager()
        
        # Transaction queues
        self.mempool: Dict[bytes, TieredTransaction] = {}
        self.pending_blocks: queue.Queue = queue.Queue()
        
        # Event handlers
        self.on_new_block: Optional[Callable[[DAGBlock], None]] = None
        self.on_new_transaction: Optional[Callable[[TieredTransaction], None]] = None
        
        # Processing threads
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    def start(self):
        """Start the node."""
        with self._lock:
            if self.state != EngineState.STOPPED:
                logger.warning("Node already running")
                return
            
            self.state = EngineState.STARTING
            self._stop_event.clear()
            
            logger.info("Starting Proof of Time node...")
            
            # Load state from storage
            self._load_state()
            
            # Start processing threads
            self._start_threads()
            
            self.state = EngineState.RUNNING
            logger.info("Proof of Time node started")
    
    def stop(self):
        """Stop the node."""
        with self._lock:
            if self.state == EngineState.STOPPED:
                return
            
            self.state = EngineState.STOPPING
            logger.info("Stopping Proof of Time node...")
            
            # Signal threads to stop
            self._stop_event.set()
            
            # Wait for threads
            for thread in self._threads:
                thread.join(timeout=5)
            
            self._threads.clear()
            
            # Save state
            self._save_state()
            
            # Close storage
            self.storage.close()
            
            self.state = EngineState.STOPPED
            logger.info("Proof of Time node stopped")
    
    def _load_state(self):
        """Load node state from storage."""
        # Load DAG tips and recent blocks
        tips = self.storage.get_dag_tips()
        for tip in tips:
            block = self.storage.get_dag_block(tip)
            if block:
                self.dag_engine.dag.add_block(block)
        
        # Load node weight
        weight = self.storage.get_node_weight(self.public_key)
        if weight:
            self.dag_engine.update_node_weight(self.public_key, weight)
        
        logger.info(f"Loaded {len(tips)} DAG tips")
    
    def _save_state(self):
        """Save node state to storage."""
        # Get current weight from DAG engine
        weight = self.dag_engine.node_weights.get(self.public_key, 0.0)
        
        # Update node state
        self.storage.store_node_state(
            pubkey=self.public_key,
            weight=weight,
            uptime=self.node_state.total_uptime,
            stored_blocks=self.node_state.stored_blocks,
            signed_blocks=self.node_state.signed_blocks,
            status=self.node_state.status
        )
        
        logger.info("Node state saved")
    
    def _start_threads(self):
        """Start background processing threads."""
        # Block processing thread
        block_thread = threading.Thread(
            target=self._block_processing_loop,
            name="block-processor",
            daemon=True
        )
        block_thread.start()
        self._threads.append(block_thread)
        
        # Weight update thread
        weight_thread = threading.Thread(
            target=self._weight_update_loop,
            name="weight-updater",
            daemon=True
        )
        weight_thread.start()
        self._threads.append(weight_thread)
    
    def _block_processing_loop(self):
        """Process incoming blocks."""
        while not self._stop_event.is_set():
            try:
                block = self.pending_blocks.get(timeout=1)
                self._process_block(block)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing block: {e}")
    
    def _weight_update_loop(self):
        """Periodically update node weights."""
        while not self._stop_event.is_set():
            try:
                self._update_weights()
                time.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Error updating weights: {e}")
    
    # =========================================================================
    # BLOCK OPERATIONS
    # =========================================================================
    
    def produce_block(self) -> Optional[DAGBlock]:
        """
        Produce a new DAG block.

        Only eligible if node weight ≥ 10% threshold.
        """
        with self._lock:
            if not self.dag_engine.can_produce_block(self.public_key):
                logger.debug("Node weight below production threshold")
                return None

            # Select transactions from mempool
            transactions = self._select_transactions()

            # Create block
            block = self.block_producer.create_block(transactions)

            if block:
                # Add to DAG
                success, reason = self.dag_engine.add_block(block)

                if success:
                    # Store block
                    self.storage.store_dag_block(block)

                    # Remove included transactions from mempool
                    for tx in transactions:
                        self.mempool.pop(tx.hash(), None)

                    # Update node state
                    self.node_state.signed_blocks += 1

                    # Update HAL reputation
                    self.hal.record_event(
                        self.public_key,
                        ReputationEvent.BLOCK_PRODUCED,
                        height=block.header.height
                    )

                    # Notify handlers
                    if self.on_new_block:
                        self.on_new_block(block)

                    logger.info(f"Produced block {block.block_hash.hex()[:16]} "
                               f"with {len(transactions)} transactions")
                else:
                    logger.warning(f"Block rejected: {reason}")
                    return None

            return block
    
    def receive_block(self, block: DAGBlock) -> Tuple[bool, str]:
        """
        Receive and validate block from network.
        """
        # Add to processing queue
        self.pending_blocks.put(block)
        return True, "Queued for processing"
    
    def _process_block(self, block: DAGBlock) -> Tuple[bool, str]:
        """Process a received block."""
        with self._lock:
            # Validate and add to DAG
            success, reason = self.dag_engine.add_block(block)

            if success:
                # Store block
                self.storage.store_dag_block(block)

                # Update anonymity set
                for tx in block.transactions:
                    for out in tx.outputs:
                        if hasattr(out, 'tier'):
                            self.anonymity_manager.add_output(out)

                # Notify handlers
                if self.on_new_block:
                    self.on_new_block(block)

                logger.debug(f"Processed block {block.block_hash.hex()[:16]}")

        return success, reason
    
    # =========================================================================
    # TRANSACTION OPERATIONS
    # =========================================================================
    
    def create_transaction(
        self,
        outputs: List[Tuple[bytes, bytes, int, PrivacyTier]],  # (view_pk, spend_pk, amount, tier)
        inputs: List[Tuple[bytes, int, bytes]] = None  # (txid, index, private_key)
    ) -> Optional[TieredTransaction]:
        """
        Create a new tiered transaction.
        
        Args:
            outputs: List of (view_public, spend_public, amount, tier) tuples
            inputs: Optional list of (prev_txid, prev_index, private_key) tuples
        
        Returns:
            Created transaction or None if failed
        """
        builder = TieredTransactionBuilder()
        
        for view_pk, spend_pk, amount, tier in outputs:
            if tier == PrivacyTier.T0_PUBLIC:
                # For T0, use spend_pk as address
                builder.add_public_output(spend_pk, amount)
            elif tier == PrivacyTier.T1_STEALTH:
                builder.add_stealth_output(view_pk, spend_pk, amount)
            elif tier == PrivacyTier.T2_CONFIDENTIAL:
                builder.add_confidential_output(view_pk, spend_pk, amount)
            elif tier == PrivacyTier.T3_RING:
                builder.add_ring_output(view_pk, spend_pk, amount)
        
        # Add inputs if provided
        if inputs:
            for prev_txid, prev_index, private_key in inputs:
                builder.add_public_input(prev_txid, prev_index, private_key)
        
        # Calculate and set fee
        tx = builder.build()
        required_fee = tx.calculate_fee()
        builder.set_fee(required_fee)
        
        try:
            tx = builder.build()
            
            # Validate
            valid, reason = TierValidator.validate_transaction(tx)
            if not valid:
                logger.warning(f"Transaction validation failed: {reason}")
                return None
            
            return tx
            
        except ValueError as e:
            logger.warning(f"Transaction creation failed: {e}")
            return None
    
    def submit_transaction(self, tx: TieredTransaction) -> Tuple[bool, str]:
        """
        Submit transaction to mempool.
        """
        with self._lock:
            # Validate
            spent_images = {self.storage.is_key_image_spent(ki) for inp in tx.inputs
                           if hasattr(inp, 'key_image') for ki in [inp.key_image] if ki}

            if any(spent_images):
                return False, "Key image already spent"

            valid, reason = TierValidator.validate_transaction(tx)
            if not valid:
                return False, reason

            # Add to mempool
            txid = tx.hash()
            self.mempool[txid] = tx

            # Add to storage mempool
            self.storage.add_to_mempool(tx)

            # Notify handlers
            if self.on_new_transaction:
                self.on_new_transaction(tx)

            logger.debug(f"Transaction {txid.hex()[:16]} added to mempool")
            return True, "OK"
    
    def _select_transactions(self, max_count: int = 1000) -> List:
        """Select transactions from mempool for block inclusion."""
        # Get transactions sorted by fee rate
        txs = sorted(
            self.mempool.values(),
            key=lambda t: t.fee / t.estimate_size() if t.estimate_size() > 0 else 0,
            reverse=True
        )
        
        return txs[:max_count]
    
    # =========================================================================
    # CONSENSUS
    # =========================================================================
    
    def _update_weights(self):
        """Update node weights based on time, space, reputation."""
        with self._lock:
            now = int(time.time())

            # Update own uptime
            self.node_state.total_uptime = now - self.node_state.uptime_start
            self.node_state.last_seen = now

            # Calculate own weight using raw probability
            # (simplified - in production would use full probability calculation)
            total_blocks = self.storage.get_stats().get('total_blocks', 1) or 1
            weight = self.consensus_calc.compute_raw_probability(
                self.node_state,
                now,
                total_blocks
            )

            # Update in DAG engine
            self.dag_engine.update_node_weight(
                self.public_key,
                weight
            )

            # Store updated state
            self.storage.store_node_state(
                pubkey=self.public_key,
                weight=weight,
                uptime=self.node_state.total_uptime,
                stored_blocks=self.node_state.stored_blocks,
                signed_blocks=self.node_state.signed_blocks,
                status=self.node_state.status
            )
    
    def get_node_weight(self, pubkey: bytes) -> float:
        """Get consensus weight for a node."""
        return self.dag_engine.node_weights.get(pubkey, 0.0)
    
    def get_top_nodes(self, limit: int = 100) -> List[Tuple[bytes, float]]:
        """Get top nodes by weight."""
        return self.storage.get_top_nodes(limit)
    
    # =========================================================================
    # STATUS AND STATS
    # =========================================================================
    
    def get_status(self) -> dict:
        """Get node status."""
        return {
            'state': self.state.name,
            'public_key': self.public_key.hex(),
            'weight': self.dag_engine.node_weights.get(self.public_key, 0.0),
            'uptime': self.node_state.total_uptime,
            'signed_blocks': self.node_state.signed_blocks,
            'stored_blocks': self.node_state.stored_blocks,
            'mempool_size': len(self.mempool),
            'dag_tips': len(self.dag_engine.dag.get_tips()),
            'can_produce': self.dag_engine.can_produce_block(self.public_key)
        }
    
    def get_stats(self) -> dict:
        """Get comprehensive statistics."""
        storage_stats = self.storage.get_stats()
        anon_stats = self.anonymity_manager.get_pool_stats()
        hal_stats = self.hal.get_stats()

        return {
            'node': self.get_status(),
            'storage': storage_stats,
            'anonymity': anon_stats,
            'hal': hal_stats,
            'tier_specs': {
                tier.name: TIER_SPECS[tier]
                for tier in PrivacyTier
            }
        }

    def get_hal_profile(self, pubkey: Optional[bytes] = None) -> Optional[HalProfile]:
        """Get HAL reputation profile for a node."""
        if pubkey is None:
            pubkey = self.public_key
        return self.hal.get_profile(pubkey)

    def vouch_for_node(self, peer_pubkey: bytes) -> bool:
        """Vouch for a peer node's reputation."""
        return self.hal.add_vouch(self.public_key, peer_pubkey)

    def get_reputation_score(self, pubkey: Optional[bytes] = None) -> float:
        """Get HAL reputation score for a node."""
        if pubkey is None:
            pubkey = self.public_key
        return self.hal.get_reputation_score(pubkey)

    def report_slashing_event(
        self,
        offender_pubkey: bytes,
        condition: int,
        height: int,
        evidence_hash: Optional[bytes] = None
    ):
        """
        Report a slashing event to HAL reputation system.

        Maps SlashingCondition to ReputationEvent:
        - EQUIVOCATION -> ReputationEvent.EQUIVOCATION
        - INVALID_VDF -> ReputationEvent.VDF_INVALID
        - INVALID_VRF -> ReputationEvent.VRF_INVALID
        """
        from pantheon.hal import SlashingCondition

        event_map = {
            SlashingCondition.EQUIVOCATION: ReputationEvent.EQUIVOCATION,
            SlashingCondition.INVALID_VDF: ReputationEvent.VDF_INVALID,
            SlashingCondition.INVALID_VRF: ReputationEvent.VRF_INVALID,
        }

        event_type = event_map.get(SlashingCondition(condition))
        if event_type:
            self.hal.record_event(
                offender_pubkey,
                event_type,
                height=height,
                evidence=evidence_hash
            )
            logger.warning(
                f"Slashing event recorded for {offender_pubkey.hex()[:16]}...: "
                f"{event_type.name}"
            )

    def record_block_validation(self, validator_pubkey: bytes, height: int, valid: bool):
        """Record block validation event for HAL."""
        if valid:
            self.hal.record_event(
                validator_pubkey,
                ReputationEvent.BLOCK_VALIDATED,
                height=height
            )
        else:
            self.hal.record_event(
                validator_pubkey,
                ReputationEvent.BLOCK_INVALID,
                height=height
            )

    def record_uptime_checkpoint(self):
        """Record uptime checkpoint for this node."""
        self.hal.record_event(
            self.public_key,
            ReputationEvent.UPTIME_CHECKPOINT,
            height=self._current_height if hasattr(self, '_current_height') else 0
        )

    # =========================================================================
    # NETWORK INTERFACE
    # =========================================================================
    
    def get_tips(self) -> List[bytes]:
        """Get current DAG tips for network sync."""
        return self.dag_engine.dag.get_tips()
    
    def get_block(self, block_hash: bytes) -> Optional[DAGBlock]:
        """Get block by hash."""
        return self.storage.get_dag_block(block_hash)
    
    def get_ordered_transactions(self) -> List:
        """Get all transactions in canonical order."""
        return self.dag_engine.get_ordered_transactions()


# ============================================================================
# PROTOCOL RUNNER
# ============================================================================

class ProtocolRunner:
    """
    High-level protocol runner for Proof of Time.
    
    Manages node lifecycle and provides simple API.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config = NodeConfig.from_file(config_path)
        else:
            self.config = NodeConfig()
        
        self.node: Optional[ProofOfTimeNode] = None
    
    def run(self):
        """Run the protocol."""
        try:
            self.node = ProofOfTimeNode(self.config)
            self.node.start()
            
            logger.info("Proof of Time protocol running. Press Ctrl+C to stop.")
            
            # Main loop
            while True:
                time.sleep(1)
                
                # Attempt block production
                if self.node.state == EngineState.RUNNING:
                    self.node.produce_block()
                
        except KeyboardInterrupt:
            logger.info("Shutdown requested...")
        finally:
            if self.node:
                self.node.stop()
    
    def get_node(self) -> Optional[ProofOfTimeNode]:
        """Get the running node instance."""
        return self.node


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run engine self-tests."""
    import tempfile
    import os
    
    logger.info("Running engine self-tests...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create config
        from config import StorageConfig
        storage_config = StorageConfig(db_path=os.path.join(tmpdir, "test.db"))
        node_config = NodeConfig(storage=storage_config)
        
        # Create node
        node = ProofOfTimeNode(config=node_config)
        assert node.state == EngineState.STOPPED
        logger.info("✓ Node creation")
        
        # Start node
        node.start()
        assert node.state == EngineState.RUNNING
        logger.info("✓ Node start")
        
        # Check status
        status = node.get_status()
        assert 'state' in status
        assert 'weight' in status
        logger.info("✓ Status retrieval")
        
        # Create transaction
        sk1, pk1 = Ed25519.generate_keypair()
        sk2, pk2 = Ed25519.generate_keypair()
        
        tx = node.create_transaction([
            (pk1, pk2, 1000, PrivacyTier.T0_PUBLIC)
        ])
        assert tx is not None
        logger.info("✓ Transaction creation")
        
        # Submit transaction
        success, _ = node.submit_transaction(tx)
        assert success
        assert len(node.mempool) > 0
        logger.info("✓ Transaction submission")
        
        # Get stats
        stats = node.get_stats()
        assert 'node' in stats
        assert 'storage' in stats
        logger.info("✓ Statistics retrieval")
        
        # Stop node
        node.stop()
        assert node.state == EngineState.STOPPED
        logger.info("✓ Node stop")
    
    logger.info("All engine self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    _self_test()

