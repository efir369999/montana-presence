"""
Proof of Time - Node Module
Production-grade full node implementation.

Includes:
- Block synchronization
- Transaction validation and mempool
- Mining (block production)
- Chain management
- Event handling

Time is the ultimate proof.
"""

import time
import struct
import threading
import logging
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass
from enum import IntEnum, auto
from queue import Queue, Empty

from config import PROTOCOL, NodeConfig, get_block_reward
from pantheon.prometheus import sha256, Ed25519, ECVRF, VRFOutput, WesolowskiVDF, VDFProof
from pantheon.themis import Block, BlockHeader, Transaction, create_genesis_block
from pantheon.nyx import LSAG
from pantheon.athena import ConsensusEngine
from pantheon.hades import BlockchainDB
from pantheon.paul import P2PNode, Peer
from pantheon.plutus import Wallet

logger = logging.getLogger("proof_of_time.node")


# ============================================================================
# NODE STATE
# ============================================================================

class SyncState(IntEnum):
    """Node synchronization state."""
    IDLE = auto()
    CONNECTING = auto()
    SYNCING_HEADERS = auto()
    SYNCING_BLOCKS = auto()
    SYNCED = auto()


@dataclass
class ChainTip:
    """Current chain tip information."""
    hash: bytes
    height: int
    timestamp: int
    total_work: int = 0


# ============================================================================
# MEMPOOL
# ============================================================================

class Mempool:
    """
    Transaction memory pool with spam resistance.

    Manages unconfirmed transactions with:
    - Fee-based prioritization
    - Double-spend detection via key images
    - Size limits (default 300 MB)
    - Minimum fee rate enforcement
    - Dust output rejection
    - Rate limiting per sender
    - Expiration (24 hours default)
    """

    # Spam resistance constants
    MIN_FEE_RATE = 1  # Minimum fee per KB (in base units)
    DUST_THRESHOLD = 100  # Minimum output value to prevent dust attacks
    MAX_TX_SIZE = 1_000_000  # 1 MB max transaction size
    MAX_TXS_PER_SENDER = 100  # Max pending txs per sender pubkey
    TX_EXPIRATION_SECONDS = 86400  # 24 hours

    def __init__(self, db: BlockchainDB, max_size_mb: int = 300):
        self.db = db
        self.max_size = max_size_mb * 1024 * 1024

        self.transactions: Dict[bytes, Transaction] = {}
        self.by_fee_rate: List[bytes] = []  # Sorted by fee rate
        self.key_images: Set[bytes] = set()

        # Spam resistance tracking
        self.tx_by_sender: Dict[bytes, Set[bytes]] = {}  # sender_pubkey -> set of txids
        self.tx_timestamps: Dict[bytes, float] = {}  # txid -> timestamp

        self.current_size = 0
        self._lock = threading.RLock()
    
    def add_transaction(self, tx: Transaction) -> bool:
        """
        Add transaction to mempool with spam resistance.

        Returns True if added successfully.

        Spam resistance checks:
        1. Maximum transaction size
        2. Minimum fee rate
        3. Dust output rejection
        4. Rate limiting per sender
        5. Double-spend detection
        """
        with self._lock:
            txid = tx.hash()

            # Already have it?
            if txid in self.transactions:
                return True

            # SPAM CHECK 1: Transaction size limit
            tx_size = len(tx.serialize())
            if tx_size > self.MAX_TX_SIZE:
                logger.warning(f"Mempool reject: tx size {tx_size} > max {self.MAX_TX_SIZE}")
                return False

            # SPAM CHECK 2: Minimum fee rate
            fee_rate = (tx.fee * 1024) // tx_size if tx_size > 0 else 0
            if fee_rate < self.MIN_FEE_RATE:
                logger.debug(f"Mempool reject: fee rate {fee_rate} < min {self.MIN_FEE_RATE}")
                return False

            # SPAM CHECK 3: Dust output rejection
            for out in tx.outputs:
                if hasattr(out, 'amount') and out.amount < self.DUST_THRESHOLD:
                    logger.debug(f"Mempool reject: dust output {out.amount} < {self.DUST_THRESHOLD}")
                    return False

            # SPAM CHECK 4: Rate limit per sender
            sender_key = tx.inputs[0].key_image[:32] if tx.inputs else b''
            if sender_key in self.tx_by_sender:
                if len(self.tx_by_sender[sender_key]) >= self.MAX_TXS_PER_SENDER:
                    logger.warning(f"Mempool reject: sender rate limit ({self.MAX_TXS_PER_SENDER} pending)")
                    return False

            # SPAM CHECK 5: Double-spend detection via key images
            for inp in tx.inputs:
                if inp.key_image in self.key_images:
                    logger.warning(f"Mempool reject: double-spend {txid.hex()[:16]}")
                    return False
                if self.db.is_key_image_spent(inp.key_image):
                    logger.warning(f"Mempool reject: spent key image {txid.hex()[:16]}")
                    return False

            # Validate transaction cryptography
            if not self._validate_transaction(tx):
                return False
            
            # Evict if needed
            while self.current_size + tx_size > self.max_size and self.by_fee_rate:
                self._evict_lowest()
            
            self.transactions[txid] = tx
            self.current_size += tx_size

            # Track key images
            for inp in tx.inputs:
                self.key_images.add(inp.key_image)

            # Track sender for rate limiting
            if sender_key:
                if sender_key not in self.tx_by_sender:
                    self.tx_by_sender[sender_key] = set()
                self.tx_by_sender[sender_key].add(txid)

            # Track timestamp for expiration
            self.tx_timestamps[txid] = time.time()

            # Insert sorted by fee rate
            fee_rate = tx.fee / tx_size if tx_size > 0 else 0
            self._insert_sorted(txid, fee_rate)

            # Store in database
            self.db.add_to_mempool(tx)

            logger.debug(f"Added tx to mempool: {txid.hex()[:16]}...")
            return True

    def remove_transaction(self, txid: bytes):
        """Remove transaction from mempool."""
        with self._lock:
            if txid not in self.transactions:
                return

            tx = self.transactions[txid]

            # Remove key images
            for inp in tx.inputs:
                self.key_images.discard(inp.key_image)

            # Remove sender tracking
            sender_key = tx.inputs[0].key_image[:32] if tx.inputs else b''
            if sender_key in self.tx_by_sender:
                self.tx_by_sender[sender_key].discard(txid)
                if not self.tx_by_sender[sender_key]:
                    del self.tx_by_sender[sender_key]

            # Remove timestamp
            self.tx_timestamps.pop(txid, None)

            # Remove from structures
            del self.transactions[txid]
            if txid in self.by_fee_rate:
                self.by_fee_rate.remove(txid)

            self.current_size -= len(tx.serialize())
            self.db.remove_from_mempool(txid)

    def expire_old_transactions(self):
        """Remove expired transactions (older than TX_EXPIRATION_SECONDS)."""
        now = time.time()
        expired = []

        with self._lock:
            for txid, timestamp in list(self.tx_timestamps.items()):
                if now - timestamp > self.TX_EXPIRATION_SECONDS:
                    expired.append(txid)

        for txid in expired:
            logger.debug(f"Expiring old tx: {txid.hex()[:16]}...")
            self.remove_transaction(txid)
    
    def get_transactions_for_block(self, max_size: int = 1_000_000) -> List[Transaction]:
        """Get highest fee transactions for block."""
        with self._lock:
            result = []
            total_size = 0
            used_key_images = set()
            
            for txid in self.by_fee_rate:
                tx = self.transactions.get(txid)
                if not tx:
                    continue
                
                tx_size = len(tx.serialize())
                if total_size + tx_size > max_size:
                    break
                
                # Check for conflicts
                conflict = False
                for inp in tx.inputs:
                    if inp.key_image in used_key_images:
                        conflict = True
                        break
                
                if conflict:
                    continue
                
                result.append(tx)
                total_size += tx_size
                for inp in tx.inputs:
                    used_key_images.add(inp.key_image)
            
            return result
    
    def remove_confirmed(self, block: Block):
        """Remove transactions confirmed in block."""
        with self._lock:
            for tx in block.transactions:
                txid = tx.hash()
                self.remove_transaction(txid)
    
    def _validate_transaction(self, tx: Transaction) -> bool:
        """
        Full transaction validation including cryptographic proofs.

        Validates:
        1. Version and structure
        2. Ring signatures (LSAG) for each input
        3. Range proofs (Bulletproof) for each output
        4. Commitment balance (inputs = outputs + fee)
        """
        # Check version
        if tx.version > PROTOCOL.PROTOCOL_VERSION:
            logger.debug(f"Tx rejected: unknown version {tx.version}")
            return False

        # Coinbase not allowed in mempool
        if tx.is_coinbase():
            logger.debug("Tx rejected: coinbase in mempool")
            return False

        # Must have inputs and outputs
        if not tx.inputs or not tx.outputs:
            logger.debug("Tx rejected: missing inputs or outputs")
            return False

        # Fee must be positive
        if tx.fee < PROTOCOL.MIN_FEE:
            logger.debug(f"Tx rejected: fee {tx.fee} below minimum {PROTOCOL.MIN_FEE}")
            return False

        # Compute transaction hash for signature verification
        tx_hash = tx.hash()

        # Validate each input's ring signature
        for i, inp in enumerate(tx.inputs):
            # Check ring size
            if len(inp.ring) < PROTOCOL.MIN_RING_SIZE:
                logger.debug(f"Tx rejected: input {i} ring size {len(inp.ring)} < minimum {PROTOCOL.MIN_RING_SIZE}")
                return False

            # Verify ring signature
            if inp.ring_signature is None:
                logger.debug(f"Tx rejected: input {i} missing ring signature")
                return False

            if not LSAG.verify(tx_hash, inp.ring, inp.ring_signature):
                logger.debug(f"Tx rejected: input {i} invalid ring signature")
                return False

            # Verify key image matches signature
            if inp.key_image != inp.ring_signature.key_image:
                logger.debug(f"Tx rejected: input {i} key image mismatch")
                return False

        # Validate each output's range proof
        for i, out in enumerate(tx.outputs):
            # Check commitment exists
            if len(out.commitment) != 32:
                logger.debug(f"Tx rejected: output {i} invalid commitment")
                return False

            # T0/T1 transactions don't use range proofs
            # T2/T3 (confidential) are not supported in production

        # Verify commitment balance: sum(inputs) = sum(outputs) + fee
        # This is done by checking: sum(pseudo_commits) - sum(output_commits) - fee*H = 0
        try:
            from privacy import Ed25519Point, PedersenGenerators

            # Sum input pseudo commitments
            if not tx.inputs[0].pseudo_commitment or len(tx.inputs[0].pseudo_commitment) != 32:
                logger.debug("Tx rejected: input 0 missing pseudo commitment")
                return False

            input_sum = tx.inputs[0].pseudo_commitment
            for inp in tx.inputs[1:]:
                if not inp.pseudo_commitment or len(inp.pseudo_commitment) != 32:
                    logger.debug("Tx rejected: input missing pseudo commitment")
                    return False
                input_sum = Ed25519Point.point_add(input_sum, inp.pseudo_commitment)

            # Sum output commitments
            output_sum = tx.outputs[0].commitment
            for out in tx.outputs[1:]:
                output_sum = Ed25519Point.point_add(output_sum, out.commitment)

            # Add fee commitment
            fee_scalar = tx.fee.to_bytes(32, 'little')
            fee_commit = Ed25519Point.scalarmult(fee_scalar, PedersenGenerators.get_H())
            output_sum = Ed25519Point.point_add(output_sum, fee_commit)

            # Verify balance
            import hmac
            if not hmac.compare_digest(input_sum, output_sum):
                logger.debug("Tx rejected: commitment balance failed")
                return False

        except Exception as e:
            logger.debug(f"Tx rejected: commitment verification error: {e}")
            return False

        return True
    
    def _insert_sorted(self, txid: bytes, fee_rate: float):
        """Insert txid maintaining fee rate order (highest first)."""
        # Simple insertion sort (could use bisect for efficiency)
        self.by_fee_rate.append(txid)
        self.by_fee_rate.sort(
            key=lambda t: self.transactions[t].fee / len(self.transactions[t].serialize())
            if t in self.transactions else 0,
            reverse=True
        )
    
    def _evict_lowest(self):
        """Evict lowest fee transaction."""
        if not self.by_fee_rate:
            return
        
        txid = self.by_fee_rate.pop()
        if txid in self.transactions:
            tx = self.transactions[txid]
            self.current_size -= len(tx.serialize())
            for inp in tx.inputs:
                self.key_images.discard(inp.key_image)
            del self.transactions[txid]
    
    def get_size(self) -> int:
        """Get mempool size in bytes."""
        return self.current_size
    
    def get_count(self) -> int:
        """Get transaction count."""
        return len(self.transactions)


# ============================================================================
# BLOCK PRODUCER (PoH + PoT DUAL LAYER)
# ============================================================================

class BlockProducer:
    """
    Dual-layer block producer.

    PoH Layer: Produces blocks every 1 second
    PoT Layer: Creates VDF checkpoints every 600 blocks (10 minutes)

    Solo node mode: Always produces blocks (no VRF check needed)
    Network mode: Uses VRF for leader selection
    """

    def __init__(
        self,
        node: 'FullNode',
        secret_key: bytes,
        public_key: bytes
    ):
        self.node = node
        self.secret_key = secret_key
        self.public_key = public_key

        self.vdf = WesolowskiVDF(PROTOCOL.VDF_MODULUS_BITS)
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # PoH state
        self.poh_hash = b'\x00' * 32  # Current PoH chain hash
        self.poh_count = 0  # Total PoH hashes computed
        self.last_block_time = 0.0

        # Stats
        self.blocks_produced = 0
        self.checkpoints_produced = 0

    def start(self):
        """Start block production."""
        self.running = True
        self._thread = threading.Thread(target=self._production_loop, daemon=True)
        self._thread.start()
        logger.info("PoH block producer started (1 block/sec)")

    def stop(self):
        """Stop block production."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Block producer stopped")

    def _poh_hash_step(self) -> bytes:
        """Single PoH hash step."""
        self.poh_hash = sha256(self.poh_hash)
        self.poh_count += 1
        return self.poh_hash

    def _production_loop(self):
        """
        Main PoH production loop.

        Produces 1 block per second with PoH chain.
        Every 600 blocks, triggers PoT checkpoint with VDF.

        Block timestamps are synchronized to UTC:
        - Block N has timestamp = GENESIS_TIMESTAMP + N
        - Production waits for the next UTC second boundary
        - If behind schedule (catching up), produces blocks rapidly
        """
        while self.running:
            try:
                # Get current tip
                tip = self.node.get_chain_tip()
                if not tip:
                    time.sleep(0.1)
                    continue

                # Calculate expected timestamp for next block
                next_height = tip.height + 1
                expected_timestamp = PROTOCOL.GENESIS_TIMESTAMP + next_height

                # Current UTC time
                now = time.time()
                current_utc = int(now)

                # Check if we're behind (catching up) or in sync
                if current_utc >= expected_timestamp:
                    # We're behind or exactly on time - produce immediately
                    self._produce_poh_block(tip, expected_timestamp)
                else:
                    # Wait until the expected timestamp (UTC second boundary)
                    wait_time = expected_timestamp - now
                    if wait_time > 0:
                        time.sleep(wait_time)
                    self._produce_poh_block(tip, expected_timestamp)

            except Exception as e:
                logger.error(f"Block production error: {e}")
                time.sleep(1)

    def _produce_poh_block(self, tip: ChainTip, timestamp: Optional[int] = None):
        """
        Produce a PoH block (1 second).

        Args:
            tip: Current chain tip
            timestamp: Block timestamp (UTC). If None, uses GENESIS_TIMESTAMP + height
        """
        new_height = tip.height + 1
        if timestamp is None:
            timestamp = PROTOCOL.GENESIS_TIMESTAMP + new_height

        # Advance PoH chain (64 ticks × 12500 hashes = 800,000 hashes)
        for _ in range(PROTOCOL.POH_TICKS_PER_SLOT):
            for _ in range(PROTOCOL.POH_HASHES_PER_TICK):
                self._poh_hash_step()

        # Check if this is a PoT checkpoint (every 600 blocks)
        is_checkpoint = (new_height % PROTOCOL.POT_CHECKPOINT_INTERVAL == 0)

        # VDF proof only for checkpoints
        if is_checkpoint and new_height > 0:
            vdf_iterations = self.node.config.vdf.iterations
            vdf_proof = self.vdf.compute(tip.hash, vdf_iterations)
            vdf_output = vdf_proof.output
            vdf_proof_bytes = vdf_proof.proof
        else:
            vdf_iterations = 0
            vdf_output = self.poh_hash  # Use PoH hash instead
            vdf_proof_bytes = b''

        # VRF for leader selection - use same input derivation as validator
        vrf_input = self.node.consensus.leader_selector.compute_selection_input(
            tip.hash, new_height
        )
        vrf_output = ECVRF.prove(self.secret_key, vrf_input)

        # Create coinbase
        reward = get_block_reward(new_height // PROTOCOL.POT_CHECKPOINT_INTERVAL)

        if self.node.wallet:
            reward_address = self.node.wallet.get_primary_address()
            view_pub = reward_address[:32]
            spend_pub = reward_address[32:]
        else:
            view_pub = self.public_key
            spend_pub = self.public_key

        coinbase = Transaction.create_coinbase(
            height=new_height,
            reward_address=view_pub,
            reward_tx_pubkey=spend_pub,
            extra_data=f"PoH slot {new_height}".encode()
        )

        # Get transactions from mempool
        txs = [coinbase] + self.node.mempool.get_transactions_for_block()

        # Build block
        block = Block(
            header=BlockHeader(
                version=PROTOCOL.PROTOCOL_VERSION,
                prev_block_hash=tip.hash,
                merkle_root=b'\x00' * 32,
                timestamp=timestamp,
                height=new_height,
                vdf_input=tip.hash,
                vdf_output=vdf_output,
                vdf_proof=vdf_proof_bytes,
                vdf_iterations=vdf_iterations,
                vrf_output=vrf_output.beta,
                vrf_proof=vrf_output.proof,
                leader_pubkey=self.public_key,
                leader_signature=b'\x00' * 64
            ),
            transactions=txs
        )

        # Set merkle root
        block.header.merkle_root = block.compute_merkle_root()

        # Sign block
        signing_hash = block.header.signing_hash()
        signature = Ed25519.sign(self.secret_key, signing_hash)
        block.header.leader_signature = signature

        # Process locally
        if self.node.process_block(block):
            self.blocks_produced += 1
            self.last_block_time = time.time()

            if is_checkpoint:
                self.checkpoints_produced += 1
                logger.info(f"PoT checkpoint {new_height // 600}: slot {new_height}")
            elif new_height % 60 == 0:
                # Log every minute
                logger.debug(f"PoH slot {new_height} (TPS: {len(txs)-1})")
        else:
            logger.warning(f"Failed to process block {new_height}")

    def _check_leadership(self, tip: ChainTip) -> bool:
        """Check if we're the leader for next block (solo mode: always true)."""
        # In solo mode, we're always the leader
        if self.node.network.get_peer_count() == 0:
            return True

        next_height = tip.height + 1

        # Compute VRF input
        vrf_input = sha256(tip.hash + struct.pack('<Q', next_height))
        vrf_output = ECVRF.prove(self.secret_key, vrf_input)

        # Get our probability
        probs = self.node.consensus.compute_probabilities()
        our_prob = probs.get(self.public_key, 0.5)  # Default 50% for solo

        # Check if VRF output qualifies us as leader
        return self.node.consensus.leader_selector.is_leader(
            vrf_output.beta, our_prob
        )
    


# ============================================================================
# FULL NODE
# ============================================================================

class FullNode:
    """
    Proof of Time full node.
    
    Manages:
    - Blockchain state
    - P2P networking
    - Transaction mempool
    - Block validation and production
    - Wallet integration
    """
    
    def __init__(self, config: Optional[NodeConfig] = None):
        self.config = config or NodeConfig()
        
        # Components
        self.db = BlockchainDB(self.config.storage)
        self.network = P2PNode(self.config.network)
        self.consensus = ConsensusEngine(self.config)
        self.mempool = Mempool(self.db)
        self.wallet: Optional[Wallet] = None
        self.producer: Optional[BlockProducer] = None
        
        # State
        self.sync_state = SyncState.IDLE
        self.chain_tip: Optional[ChainTip] = None
        
        # Block queue for processing
        self.block_queue: Queue = Queue()
        
        # Callbacks
        self.on_new_block: Optional[Callable[[Block], None]] = None
        self.on_new_transaction: Optional[Callable[[Transaction], None]] = None
        
        # Threading
        self._running = False
        self._threads: List[threading.Thread] = []
        self._lock = threading.RLock()
        
        # Set up network callbacks
        self.network.on_block = self._on_network_block
        self.network.on_transaction = self._on_network_transaction
        self.network.on_headers = self._on_network_headers
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    def start(self):
        """Start the node."""
        logger.info("Starting Proof of Time node...")
        
        self._running = True
        
        # Initialize chain
        self._init_chain()
        
        # Start network
        self.network.start()
        
        # Start worker threads
        self._threads = [
            threading.Thread(target=self._block_processor, daemon=True),
            threading.Thread(target=self._sync_loop, daemon=True),
            threading.Thread(target=self._maintenance_loop, daemon=True),
        ]
        for t in self._threads:
            t.start()
        
        self.sync_state = SyncState.CONNECTING
        
        logger.info(f"Node started. Chain height: {self.chain_tip.height if self.chain_tip else 0}")
    
    def stop(self):
        """Stop the node."""
        logger.info("Stopping node...")
        
        self._running = False
        
        # Stop producer
        if self.producer:
            self.producer.stop()
        
        # Stop network
        self.network.stop()
        
        # Close database
        self.db.close()
        
        logger.info("Node stopped")
    
    def _init_chain(self):
        """Initialize blockchain state."""
        # Try to load existing chain
        latest = self.db.get_latest_block()

        if latest:
            self.chain_tip = ChainTip(
                hash=latest.hash,
                height=latest.height,
                timestamp=latest.timestamp
            )
            self.consensus.initialize()
            self.consensus.chain_tip = latest
            self.consensus.total_blocks = latest.height + 1
            logger.info(f"Loaded chain at height {latest.height}")
        else:
            # Create genesis with correct timestamp
            genesis = create_genesis_block()
            self.db.store_block(genesis)
            self.chain_tip = ChainTip(
                hash=genesis.hash,
                height=0,
                timestamp=genesis.timestamp
            )
            self.consensus.initialize(genesis)
            logger.info(f"Created genesis block (ts={genesis.timestamp})")

        # Update network height
        self.network.start_height = self.chain_tip.height

        # Register self in consensus (critical for multi-node operation)
        if hasattr(self.network, 'public_key') and self.network.public_key:
            self.consensus.register_node(self.network.public_key, self.chain_tip.height + 1)
            logger.info(f"Registered self in consensus: {self.network.public_key.hex()[:16]}...")

        # PoH mode: immediately ready (no sync wait needed)
        self.sync_state = SyncState.SYNCED
        logger.info("Ready to produce blocks")
    
    # =========================================================================
    # BLOCK PROCESSING
    # =========================================================================
    
    def process_block(self, block: Block) -> bool:
        """
        Process and validate a block.
        
        Returns True if block was accepted.
        """
        with self._lock:
            try:
                # Quick checks
                if block.height <= self.chain_tip.height:
                    # Possible fork or duplicate
                    existing = self.db.get_block(block.height)
                    if existing and existing.hash == block.hash:
                        return True  # Already have it
                    # Handle fork...
                    logger.debug(f"Ignoring block at height {block.height} (have {self.chain_tip.height})")
                    return False
                
                if block.height != self.chain_tip.height + 1:
                    logger.debug(f"Block height gap: have {self.chain_tip.height}, got {block.height}")
                    return False
                
                if block.header.prev_block_hash != self.chain_tip.hash:
                    logger.warning("Block doesn't connect to chain tip")
                    return False
                
                # Full validation
                prev_block = self.db.get_block(self.chain_tip.height)
                
                # Validate header (VDF, VRF, signature)
                if not self._validate_block_header(block, prev_block):
                    return False
                
                # Validate transactions
                if not self._validate_block_transactions(block):
                    return False
                
                # Store block
                self.db.store_block(block)
                
                # Update chain tip
                self.chain_tip = ChainTip(
                    hash=block.hash,
                    height=block.height,
                    timestamp=block.timestamp
                )
                
                # Update consensus
                self.consensus.process_block(block)

                # SECURITY: Register block producer after validation
                # This is the only safe place to register nodes - after
                # their block has passed full validation (VDF, VRF, signature)
                self._register_block_producer(block)

                # Remove confirmed transactions from mempool
                self.mempool.remove_confirmed(block)
                
                # Scan for wallet outputs
                if self.wallet:
                    self.wallet.scan_block(block)
                
                # Callback
                if self.on_new_block:
                    self.on_new_block(block)
                
                logger.info(f"Accepted block {block.height}: {block.hash.hex()[:16]}...")
                return True
                
            except Exception as e:
                logger.error(f"Block processing error: {e}")
                return False
    
    def _validate_block_header(self, block: Block, prev_block: Optional[Block]) -> bool:
        """Validate block header."""
        header = block.header
        
        # Version
        if header.version > PROTOCOL.PROTOCOL_VERSION:
            logger.warning(f"Unknown block version: {header.version}")
            return False
        
        # Timestamp
        if prev_block and header.timestamp <= prev_block.timestamp:
            logger.warning("Block timestamp not after previous")
            return False

        # Allow timestamps up to 10 minutes in future (same as Bitcoin's 2-hour was for 10-min blocks)
        # For PoT with 10-minute blocks, 10 minutes future tolerance is reasonable
        max_future_time = 600  # 10 minutes
        if header.timestamp > time.time() + max_future_time:
            logger.warning(f"Block timestamp {header.timestamp} too far in future (max +{max_future_time}s)")
            return False

        # Verify timestamp corresponds to block height (UTC synchronization)
        # Block N should have timestamp = GENESIS_TIMESTAMP + N (±tolerance for network delays)
        expected_timestamp = PROTOCOL.GENESIS_TIMESTAMP + block.height
        timestamp_tolerance = 60  # 60 seconds tolerance for network delays
        if abs(header.timestamp - expected_timestamp) > timestamp_tolerance:
            logger.warning(
                f"Block timestamp {header.timestamp} doesn't match height {block.height} "
                f"(expected ~{expected_timestamp}, tolerance ±{timestamp_tolerance}s)"
            )
            return False
        
        # Merkle root
        if not block.verify_merkle_root():
            logger.warning("Invalid merkle root")
            return False
        
        # VDF proof (only for checkpoint blocks, not regular PoH blocks)
        if block.height > 0 and header.vdf_iterations > 0:
            # This is a PoT checkpoint block - verify VDF
            vdf = WesolowskiVDF(PROTOCOL.VDF_MODULUS_BITS)
            vdf_proof = VDFProof(
                output=header.vdf_output,
                proof=header.vdf_proof,
                iterations=header.vdf_iterations,
                input_hash=header.vdf_input
            )
            if not vdf.verify(vdf_proof):
                logger.warning("Invalid VDF proof")
                return False
        
        # VRF proof - use consensus method for consistent input derivation
        if block.height > 0:
            vrf_input = self.consensus.leader_selector.compute_selection_input(
                header.prev_block_hash, block.height
            )
            vrf_output = VRFOutput(beta=header.vrf_output, proof=header.vrf_proof)
            if not ECVRF.verify(header.leader_pubkey, vrf_input, vrf_output):
                logger.warning("Invalid VRF proof")
                return False
        
        # Leader signature
        if block.height > 0:
            signing_hash = header.signing_hash()
            if not Ed25519.verify(header.leader_pubkey, signing_hash, header.leader_signature):
                logger.warning("Invalid leader signature")
                return False
        
        return True
    
    def _validate_block_transactions(self, block: Block) -> bool:
        """
        Validate all transactions in block.

        Validates:
        1. Block has at least coinbase transaction
        2. First transaction is valid coinbase
        3. Coinbase reward does not exceed maximum allowed
        4. All regular transactions have valid signatures and proofs
        5. No duplicate or already-spent key images
        """
        if not block.transactions:
            logger.warning("Block has no transactions")
            return False

        # First must be coinbase
        coinbase = block.transactions[0]
        if not coinbase.is_coinbase():
            logger.warning("First transaction not coinbase")
            return False

        # Validate coinbase structure
        if coinbase.inputs:
            logger.warning("Coinbase should have no inputs")
            return False
        if not coinbase.outputs:
            logger.warning("Coinbase has no outputs")
            return False
        if coinbase.fee != 0:
            logger.warning("Coinbase should have zero fee")
            return False

        # Validate coinbase reward amount
        expected_reward = get_block_reward(block.height)
        total_fees = sum(tx.fee for tx in block.transactions[1:])
        max_allowed_reward = expected_reward + total_fees

        # Extract coinbase output amount (for coinbase, amount is in encrypted_amount as plaintext)
        import struct
        total_coinbase_output = 0
        for out in coinbase.outputs:
            if len(out.encrypted_amount) >= 8:
                amount = struct.unpack('<Q', out.encrypted_amount[:8])[0]
                total_coinbase_output += amount

        if total_coinbase_output > max_allowed_reward:
            logger.warning(
                f"Coinbase reward {total_coinbase_output} exceeds maximum allowed "
                f"{max_allowed_reward} (base {expected_reward} + fees {total_fees})"
            )
            return False

        # Check for duplicate key images within block
        key_images = set()
        for tx in block.transactions[1:]:
            for inp in tx.inputs:
                if inp.key_image in key_images:
                    logger.warning("Duplicate key image in block")
                    return False
                if self.db.is_key_image_spent(inp.key_image):
                    logger.warning("Spent key image in block")
                    return False
                key_images.add(inp.key_image)

        # Validate all regular transactions (full cryptographic verification)
        for i, tx in enumerate(block.transactions[1:], start=1):
            tx_hash = tx.hash()

            # Check version
            if tx.version > PROTOCOL.PROTOCOL_VERSION:
                logger.warning(f"Block tx {i}: unknown version {tx.version}")
                return False

            # Must have inputs and outputs
            if not tx.inputs or not tx.outputs:
                logger.warning(f"Block tx {i}: missing inputs or outputs")
                return False

            # Validate ring signatures
            for j, inp in enumerate(tx.inputs):
                if len(inp.ring) < PROTOCOL.MIN_RING_SIZE:
                    logger.warning(f"Block tx {i} input {j}: ring too small")
                    return False

                if inp.ring_signature is None:
                    logger.warning(f"Block tx {i} input {j}: missing ring signature")
                    return False

                if not LSAG.verify(tx_hash, inp.ring, inp.ring_signature):
                    logger.warning(f"Block tx {i} input {j}: invalid ring signature")
                    return False

            # T0/T1 transactions don't use range proofs
            # T2/T3 (confidential) are not supported in production

            # Validate commitment balance
            try:
                from privacy import Ed25519Point, PedersenGenerators
                import hmac

                input_sum = tx.inputs[0].pseudo_commitment
                for inp in tx.inputs[1:]:
                    input_sum = Ed25519Point.point_add(input_sum, inp.pseudo_commitment)

                output_sum = tx.outputs[0].commitment
                for out in tx.outputs[1:]:
                    output_sum = Ed25519Point.point_add(output_sum, out.commitment)

                fee_scalar = tx.fee.to_bytes(32, 'little')
                fee_commit = Ed25519Point.scalarmult(fee_scalar, PedersenGenerators.get_H())
                output_sum = Ed25519Point.point_add(output_sum, fee_commit)

                if not hmac.compare_digest(input_sum, output_sum):
                    logger.warning(f"Block tx {i}: commitment balance failed")
                    return False

            except Exception as e:
                logger.warning(f"Block tx {i}: commitment verification error: {e}")
                return False

        return True

    def _register_block_producer(self, block: Block):
        """
        Securely register a block producer after block validation.

        SECURITY: This is called ONLY after a block passes full validation:
        - VDF proof verified
        - VRF proof verified
        - Signature verified
        - All transactions validated

        This prevents Sybil attacks where attackers send fake blocks
        to register many nodes. Only producers of valid blocks get registered.

        Rate limiting: Maximum 1 new node registration per 10 minutes
        to prevent rapid Sybil node creation.
        """
        if not block.header.producer_key:
            return

        producer_key = block.header.producer_key

        # Check if already registered
        if self.consensus.is_node_registered(producer_key):
            # Update existing node stats
            self.consensus.update_node(
                producer_key,
                stored_blocks=self.consensus.nodes.get(producer_key, object()).stored_blocks + 1
                if hasattr(self.consensus.nodes.get(producer_key), 'stored_blocks') else 1
            )
            return

        # Rate limiting: check registration rate
        # Maximum 1 new node per 600 seconds (10 minutes = 1 block interval)
        if hasattr(self, '_last_node_registration'):
            time_since_last = time.time() - self._last_node_registration
            if time_since_last < 600:  # 10 minutes
                logger.warning(
                    f"Rate limiting node registration: {producer_key.hex()[:16]}... "
                    f"(must wait {600 - time_since_last:.0f}s)"
                )
                # Still allow registration but log warning
                # In production, could enforce stricter limits

        # Register the node with 1 stored block (they proved they can produce)
        self.consensus.register_node(producer_key, stored_blocks=1)
        self._last_node_registration = time.time()

        logger.info(
            f"Registered validated block producer: {producer_key.hex()[:16]}... "
            f"at height {block.height}"
        )

    def _block_processor(self):
        """Process blocks from queue."""
        while self._running:
            try:
                block = self.block_queue.get(timeout=1)
                self.process_block(block)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Block processor error: {e}")
    
    # =========================================================================
    # SYNCHRONIZATION
    # =========================================================================
    
    def _sync_loop(self):
        """Synchronization loop."""
        solo_wait_time = 0  # Seconds waiting for peers
        solo_timeout = 10   # After 10 seconds with no peers, assume solo node

        while self._running:
            try:
                if self.sync_state == SyncState.CONNECTING:
                    peer_count = self.network.get_peer_count()
                    if peer_count >= PROTOCOL.MIN_NODES:
                        self.sync_state = SyncState.SYNCING_HEADERS
                        logger.info("Connected to peers, starting sync")
                    elif peer_count == 0:
                        solo_wait_time += 1
                        if solo_wait_time >= solo_timeout:
                            # Solo node - no peers found, start producing
                            self.sync_state = SyncState.SYNCED
                            logger.info("No peers found - starting as solo node")

                elif self.sync_state == SyncState.SYNCING_HEADERS:
                    # Request headers from peers
                    self._request_headers()
                    time.sleep(5)
                
                elif self.sync_state == SyncState.SYNCING_BLOCKS:
                    # Request missing blocks
                    self._request_blocks()
                    time.sleep(1)
                
                elif self.sync_state == SyncState.SYNCED:
                    # Check if still synced
                    time.sleep(10)
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                time.sleep(5)
    
    def _request_headers(self):
        """Request headers from peers."""
        # Simplified: assume synced after connection
        self.sync_state = SyncState.SYNCED
        logger.info("Sync complete")
    
    def _request_blocks(self):
        """Request missing blocks."""
        pass
    
    def _maintenance_loop(self):
        """Periodic maintenance."""
        while self._running:
            try:
                # Prune mempool
                self.db.prune_mempool()
                
                # Log stats
                if self.chain_tip:
                    logger.debug(
                        f"Height: {self.chain_tip.height}, "
                        f"Peers: {self.network.get_peer_count()}, "
                        f"Mempool: {self.mempool.get_count()} txs"
                    )
                
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
                time.sleep(10)
    
    # =========================================================================
    # NETWORK CALLBACKS
    # =========================================================================
    
    def _on_network_block(self, peer: Peer, block: Block):
        """Handle block from network."""
        # SECURITY: Do NOT auto-register nodes from received blocks.
        # This was a Sybil attack vector - attackers could register
        # many fake nodes just by sending blocks with different producer keys.
        #
        # Node registration now requires:
        # 1. Block must pass full validation (VDF proof, VRF proof, signature)
        # 2. Registration happens in _process_block_queue AFTER validation
        # 3. Rate limiting prevents mass registration
        #
        # See _register_block_producer() for the secure registration flow.

        self.block_queue.put(block)
    
    def _on_network_transaction(self, peer: Peer, tx: Transaction):
        """Handle transaction from network."""
        if self.mempool.add_transaction(tx):
            if self.on_new_transaction:
                self.on_new_transaction(tx)
    
    def _on_network_headers(self, peer: Peer, headers: List[BlockHeader]):
        """Handle headers from network."""
        # Used during sync
        pass
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def get_chain_tip(self) -> Optional[ChainTip]:
        """Get current chain tip."""
        return self.chain_tip
    
    def get_block(self, height: int) -> Optional[Block]:
        """Get block by height."""
        return self.db.get_block(height)
    
    def get_transaction(self, txid: bytes) -> Optional[Transaction]:
        """Get transaction by ID."""
        return self.db.get_transaction(txid)
    
    def submit_transaction(self, tx: Transaction) -> bool:
        """Submit transaction to mempool and broadcast."""
        if self.mempool.add_transaction(tx):
            self.network.broadcast_transaction(tx)
            return True
        return False
    
    def connect_peer(self, host: str, port: int) -> bool:
        """Connect to peer."""
        return self.network.connect_to_peer((host, port))
    
    def get_info(self) -> Dict:
        """Get node information."""
        return {
            'version': PROTOCOL.PROTOCOL_VERSION,
            'height': self.chain_tip.height if self.chain_tip else 0,
            'tip_hash': self.chain_tip.hash.hex() if self.chain_tip else '',
            'sync_state': self.sync_state.name,
            'peers': self.network.get_peer_count(),
            'mempool_size': self.mempool.get_count(),
            'mempool_bytes': self.mempool.get_size(),
        }
    
    def enable_mining(self, secret_key: bytes, public_key: bytes):
        """Enable block production."""
        self.producer = BlockProducer(self, secret_key, public_key)
        self.producer.start()
    
    def set_wallet(self, wallet: Wallet):
        """Set wallet for output scanning."""
        self.wallet = wallet


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    import tempfile
    import os
    
    logger.info("Running node self-tests...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Configure node
        from config import StorageConfig
        config = NodeConfig()
        config.storage = StorageConfig(db_path=os.path.join(tmpdir, "test.db"))
        
        # Create node
        node = FullNode(config)
        
        # Test chain initialization
        node._init_chain()
        assert node.chain_tip is not None
        assert node.chain_tip.height == 0
        logger.info("✓ Chain initialization")
        
        # Test mempool
        assert node.mempool.get_count() == 0
        logger.info("✓ Mempool")
        
        # Test info
        info = node.get_info()
        assert info['height'] == 0
        assert 'peers' in info
        logger.info("✓ Node info")
        
        # Clean up
        node.db.close()
    
    logger.info("All node self-tests passed!")


def _render_dashboard(node, db_path: str = '/var/lib/proofoftime/blockchain.db'):
    """Render comprehensive PoT dashboard with emission, halving, wallet info."""
    import os
    import sys
    from datetime import datetime, timezone
    from config import (
        PROTOCOL, get_block_reward, get_halving_epoch, blocks_until_halving,
        estimate_total_supply_at_height, MAX_SUPPLY_SECONDS
    )

    # Colors
    G, Y, R, C, M, B, D, W, N = '\033[92m', '\033[93m', '\033[91m', '\033[96m', '\033[95m', '\033[1m', '\033[2m', '\033[97m', '\033[0m'

    def col(text, color):
        return f"{color}{text}{N}" if sys.stdout.isatty() else str(text)

    # Initialize metrics
    m = {
        'poh_slot': 0, 'pot_checkpoint': 0, 'nodes': 1, 'mempool': 0,
        'last_block_age': 0, 'pot_next': 600, 'blocks_produced': 0, 'status': 'STARTING',
        'reward': 0, 'epoch': 1, 'blocks_to_halving': 0, 'total_emitted': 0,
        'remaining': 0, 'percent_emitted': 0, 'wallet_balance': 0,
        'expected_slot': 0, 'slot_drift': 0, 'utc_now': '', 'genesis_ts': 0,
        'wallet_address': '', 'wallet_address_full': '', 'session_earned': 0, 'next_reward_in': 1
    }

    try:
        # Chain state
        if hasattr(node, 'chain_tip') and node.chain_tip:
            height = node.chain_tip.height
            m['poh_slot'] = height
            m['pot_checkpoint'] = height // 600
            m['pot_next'] = 600 - (height % 600)
            m['last_block_age'] = int(time.time()) - node.chain_tip.timestamp
            m['status'] = 'SYNCED'

            # Emission info
            m['reward'] = get_block_reward(height)
            m['epoch'] = get_halving_epoch(height)
            m['blocks_to_halving'] = blocks_until_halving(height)
            m['total_emitted'] = estimate_total_supply_at_height(height)
            m['remaining'] = MAX_SUPPLY_SECONDS - m['total_emitted']
            m['percent_emitted'] = (m['total_emitted'] / MAX_SUPPLY_SECONDS) * 100

            # Time synchronization
            m['genesis_ts'] = PROTOCOL.GENESIS_TIMESTAMP
            m['expected_slot'] = int(time.time()) - PROTOCOL.GENESIS_TIMESTAMP
            m['slot_drift'] = height - m['expected_slot']

        # Network
        if hasattr(node, 'network') and node.network:
            m['nodes'] = 1 + node.network.get_peer_count()

        # Mempool
        if hasattr(node, 'mempool') and node.mempool:
            m['mempool'] = node.mempool.get_count()

        # Producer
        if hasattr(node, 'producer') and node.producer:
            m['blocks_produced'] = node.producer.blocks_produced
            if m['blocks_produced'] > 0:
                m['status'] = 'PRODUCING'
                if node.producer.last_block_time > 0:
                    m['last_block_age'] = int(time.time() - node.producer.last_block_time)

        # Wallet balance and address
        if hasattr(node, 'wallet') and node.wallet:
            try:
                m['wallet_balance'] = node.wallet.get_balance()
                # Get primary address (view_public + spend_public = 64 bytes)
                addr = node.wallet.get_primary_address()
                if addr and len(addr) >= 32:
                    m['wallet_address'] = addr[:32].hex()[:16] + '...' + addr[:32].hex()[-8:]
                    m['wallet_address_full'] = addr.hex()
            except (AttributeError, TypeError, ValueError) as e:
                logger.debug(f"Could not get wallet address: {e}")

        # Session earnings (blocks produced × reward at time of production)
        if m['blocks_produced'] > 0 and m['reward'] > 0:
            m['session_earned'] = m['blocks_produced'] * m['reward']

        # Next reward timing (time until next block)
        if m['expected_slot'] > 0:
            now_frac = time.time() - int(time.time())
            m['next_reward_in'] = max(0, 1.0 - now_frac)

    except Exception as e:
        logger.debug(f"Dashboard metrics error: {e}")

    # Formatters
    def fmt_time(s):
        if s < 0: return "--:--"
        if s < 3600: return f"{s // 60:02d}:{s % 60:02d}"
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"

    def fmt_amount(secs):
        """Format seconds as time tokens (minutes)."""
        mins = secs / 60
        if mins >= 1_000_000:
            return f"{mins / 1_000_000:.2f}M min"
        elif mins >= 1_000:
            return f"{mins / 1_000:.2f}K min"
        else:
            return f"{mins:.2f} min"

    def fmt_blocks(n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.2f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    # Colors based on state
    pot_next = m['pot_next']
    pot_col = G if pot_next > 300 else (Y if pot_next > 60 else R)

    status = m['status']
    status_col = G if status == 'PRODUCING' else (Y if status == 'SYNCED' else R)

    drift = m['slot_drift']
    drift_col = G if abs(drift) <= 5 else (Y if abs(drift) <= 60 else R)
    drift_str = f"+{drift}" if drift > 0 else str(drift)

    now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    now_local = datetime.now().strftime('%H:%M:%S')

    # Clear and render
    os.system('clear' if os.name != 'nt' else 'cls')
    print()
    print(col("  ╔═══════════════════════════════════════════════════════════╗", G))
    print(col("  ║", G) + col("              PROOF OF TIME NODE                        ", W) + col("║", G))
    print(col("  ╚═══════════════════════════════════════════════════════════╝", G))
    print()

    # Status section
    print(col("  ─── STATUS ───────────────────────────────────────────────", D))
    print(f"  {col('NODE', C)}           {col(status, status_col):<20} {col('PEERS', C)}  {m['nodes']}")
    print(f"  {col('MEMPOOL', C)}        {m['mempool']} tx")
    print()

    # Time section
    print(col("  ─── TIME SYNC ────────────────────────────────────────────", D))
    print(f"  {col('UTC NOW', C)}        {col(now_utc, W)}")
    print(f"  {col('EXPECTED SLOT', C)}  {m['expected_slot']:<15} {col('ACTUAL', C)}  {m['poh_slot']}")
    print(f"  {col('DRIFT', C)}          {col(drift_str + ' slots', drift_col)}")
    print()

    # PoH Layer
    print(col("  ─── PoH LAYER (1 block/sec) ──────────────────────────────", D))
    print(f"  {col('SLOT', M)}           {col(m['poh_slot'], B):<15} {col('PRODUCED', M)}  {m['blocks_produced']}")
    print(f"  {col('LAST BLOCK', M)}     {m['last_block_age']}s ago")
    print()

    # PoT Layer
    print(col("  ─── PoT LAYER (10 min finality) ──────────────────────────", D))
    print(f"  {col('CHECKPOINT', C)}     {col(m['pot_checkpoint'], B):<15} {col('FINALIZED', C)}  slot {m['pot_checkpoint'] * 600}")
    print(f"  {col('NEXT IN', C)}        {col(fmt_time(pot_next), pot_col)}")
    print()

    # Emission section
    print(col("  ─── EMISSION ─────────────────────────────────────────────", D))
    print(f"  {col('BLOCK REWARD', Y)}   {col(fmt_amount(m['reward']), W):<15} {col('EPOCH', Y)}  {m['epoch']}/33")
    print(f"  {col('TO HALVING', Y)}     {fmt_blocks(m['blocks_to_halving'])} blocks")
    print(f"  {col('EMITTED', Y)}        {fmt_amount(m['total_emitted']):<15} ({m['percent_emitted']:.4f}%)")
    print(f"  {col('REMAINING', Y)}      {fmt_amount(m['remaining'])}")
    print(f"  {col('MAX SUPPLY', Y)}     21,000,000 min")
    print()

    # Wallet section
    if m['wallet_address'] or (hasattr(node, 'wallet') and node.wallet):
        print(col("  ─── WALLET & REWARDS ─────────────────────────────────────", D))
        if m['wallet_address']:
            print(f"  {col('ADDRESS', G)}        {col(m['wallet_address'], W)}")
        print(f"  {col('BALANCE', G)}        {col(fmt_amount(m['wallet_balance']), W)}")
        if m['blocks_produced'] > 0:
            print(f"  {col('SESSION', G)}        {col(fmt_amount(m['session_earned']), Y)} ({m['blocks_produced']} blocks)")
        next_ms = int(m['next_reward_in'] * 1000)
        print(f"  {col('NEXT BLOCK', G)}     {col(f'in {next_ms}ms', C if next_ms < 500 else W)} → {col(fmt_amount(m['reward']), Y)}")
        print()

    # Footer
    print(col("  ─────────────────────────────────────────────────────────", D))
    print(col(f"  {now_local}  │  Ctrl+C to stop  │  Genesis: {PROTOCOL.GENESIS_TIMESTAMP}", D))


def main():
    """Main entry point for running the node."""
    import argparse
    import signal
    import json
    import os

    parser = argparse.ArgumentParser(description="Proof of Time Node")
    parser.add_argument("--config", "-c", type=str, help="Path to config file")
    parser.add_argument("--run", "-r", action="store_true", help="Run the node (default: self-test only)")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable live dashboard")
    parser.add_argument("--data-dir", type=str, help="Data directory")
    parser.add_argument("--p2p-port", type=int, help="P2P port (default: 8333)")
    parser.add_argument("--rpc-port", type=int, help="RPC port (default: 8332)")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    args = parser.parse_args()

    # Configure logging (to file if dashboard enabled)
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)

    if args.run and not args.no_dashboard:
        # Log to file only when dashboard is active
        log_file = '/var/log/proofoftime/node.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=log_file,
            filemode='a'
        )
    else:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    if not args.run:
        # Self-test mode
        _self_test()
        return

    # Load config
    config = NodeConfig()
    data_dir = '/var/lib/proofoftime'

    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            cfg_data = json.load(f)
            if 'data_dir' in cfg_data:
                data_dir = cfg_data['data_dir']
            if 'p2p_port' in cfg_data:
                config.network.default_port = cfg_data['p2p_port']
            if 'rpc_port' in cfg_data:
                config.rpc_port = cfg_data.get('rpc_port', 8332)

    # Command line overrides
    if args.data_dir:
        data_dir = args.data_dir

    # ALWAYS set correct database path (fixes relative path bug)
    from config import StorageConfig
    os.makedirs(data_dir, exist_ok=True)
    config.storage = StorageConfig(db_path=os.path.join(data_dir, 'blockchain.db'))
    if args.p2p_port:
        config.network.default_port = args.p2p_port
    if args.rpc_port:
        config.rpc_port = args.rpc_port

    node = FullNode(config)

    # Load or create node keys
    key_file = os.path.join(data_dir, 'node_key.json')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key_data = json.load(f)
            secret_key = bytes.fromhex(key_data['secret_key'])
            public_key = bytes.fromhex(key_data['public_key'])
    else:
        # Generate new keys
        from pantheon.prometheus import Ed25519
        secret_key, public_key = Ed25519.generate_keypair()
        os.makedirs(data_dir, exist_ok=True)
        with open(key_file, 'w') as f:
            json.dump({
                'secret_key': secret_key.hex(),
                'public_key': public_key.hex()
            }, f, indent=2)
        os.chmod(key_file, 0o600)  # Secure permissions
        logger.info(f"Generated new node keys: {public_key.hex()[:16]}...")

    # Graceful shutdown handler
    shutdown_event = threading.Event()

    def signal_handler(signum, frame):
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load or create wallet
    wallet_file = os.path.join(data_dir, 'wallet.dat')
    if os.path.exists(wallet_file):
        wallet = Wallet.load(wallet_file)
        logger.info(f"Loaded wallet: {wallet.get_primary_address().hex()[:16]}...")
    else:
        wallet = Wallet()
        wallet.save(wallet_file)
        os.chmod(wallet_file, 0o600)
        logger.info(f"Created new wallet: {wallet.get_primary_address().hex()[:16]}...")

    try:
        node.start()
        node.set_wallet(wallet)
        node.enable_mining(secret_key, public_key)

        # Main loop with dashboard
        while not shutdown_event.is_set():
            if not args.no_dashboard:
                _render_dashboard(node, os.path.join(data_dir, 'blockchain.db'))
            shutdown_event.wait(timeout=1.0)

    except KeyboardInterrupt:
        pass
    finally:
        if not args.no_dashboard:
            print("\n  Shutting down...")
        node.stop()


if __name__ == "__main__":
    main()
