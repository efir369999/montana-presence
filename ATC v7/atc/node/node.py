"""
ATC Protocol v7 Full Node
Main node orchestrator.
"""

from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from atc.constants import PROTOCOL_VERSION
from atc.core.types import Hash, PublicKey, KeyPair
from atc.core.state import GlobalState
from atc.core.block import Block
from atc.node.config import NodeConfig, setup_logging
from atc.node.mempool import Mempool
from atc.state.machine import StateMachine, apply_block
from atc.state.storage import StateStorage
from atc.network.peer import PeerManager
from atc.network.sync import BlockSynchronizer
from atc.network.gossip import GossipProtocol
from atc.consensus.fork_choice import ForkChoiceRule

if TYPE_CHECKING:
    from atc.core.heartbeat import Heartbeat
    from atc.core.transaction import Transaction

logger = logging.getLogger(__name__)


@dataclass
class NodeStatus:
    """Node status information."""
    started: bool = False
    syncing: bool = False
    connected_peers: int = 0
    chain_height: int = 0
    best_hash: Optional[str] = None
    mempool_heartbeats: int = 0
    mempool_transactions: int = 0
    uptime_seconds: int = 0
    start_time: float = 0.0


@dataclass
class Node:
    """
    ATC Protocol Full Node.

    Main orchestrator that coordinates all node components:
    - State management
    - Network communication
    - Block synchronization
    - Mempool management
    - Heartbeat production
    """
    config: NodeConfig

    # Identity
    keypair: Optional[KeyPair] = None

    # Core components
    state_machine: StateMachine = field(default_factory=StateMachine)
    storage: Optional[StateStorage] = None
    mempool: Mempool = field(default_factory=Mempool)
    fork_choice: ForkChoiceRule = field(default_factory=ForkChoiceRule)

    # Network
    peer_manager: PeerManager = field(default_factory=PeerManager)
    synchronizer: Optional[BlockSynchronizer] = None
    gossip: Optional[GossipProtocol] = None

    # Status
    status: NodeStatus = field(default_factory=NodeStatus)

    # Background tasks
    _tasks: List[asyncio.Task] = field(default_factory=list)
    _running: bool = False

    def __post_init__(self):
        self.state_machine = StateMachine()
        self.mempool = Mempool(
            max_heartbeats=self.config.mempool.max_heartbeats,
            max_transactions=self.config.mempool.max_transactions,
            max_size_bytes=self.config.mempool.max_size_bytes,
        )
        self.fork_choice = ForkChoiceRule()
        self.peer_manager = PeerManager(
            max_peers=self.config.network.max_peers,
            max_inbound=self.config.network.max_inbound,
        )
        self.status = NodeStatus()
        self._tasks = []

    async def start(self) -> None:
        """Start the node."""
        if self._running:
            return

        logger.info(f"Starting ATC node: {self.config.name}")
        logger.info(f"Network: {'testnet' if self.config.testnet else 'mainnet'}")
        logger.info(f"Protocol version: {PROTOCOL_VERSION}")

        # Setup logging
        setup_logging(self.config.log)

        # Create data directory
        data_path = Path(self.config.storage.data_dir)
        data_path.mkdir(parents=True, exist_ok=True)

        # Initialize storage
        self.storage = StateStorage(str(self.config.db_path))
        self.storage.connect()

        # Load state
        logger.info("Loading state from storage...")
        self.state_machine.current_state = self.storage.load_global_state()
        logger.info(f"Chain height: {self.state_machine.get_chain_height()}")

        # Load or generate keypair
        await self._load_keypair()

        # Initialize network
        self.synchronizer = BlockSynchronizer(self.peer_manager)
        self.gossip = GossipProtocol(self.peer_manager)

        # Set callbacks
        self._setup_callbacks()

        # Start network
        await self._start_network()

        # Start background tasks
        self._running = True
        self.status.started = True
        self.status.start_time = time.time()

        self._tasks.append(asyncio.create_task(self._sync_loop()))
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
        self._tasks.append(asyncio.create_task(self._status_loop()))

        logger.info("Node started successfully")

    async def stop(self) -> None:
        """Stop the node."""
        if not self._running:
            return

        logger.info("Stopping node...")
        self._running = False

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Stop gossip
        if self.gossip:
            await self.gossip.stop()

        # Disconnect peers
        await self.peer_manager.disconnect_all()

        # Save state
        if self.storage:
            logger.info("Saving state...")
            self.storage.save_global_state(self.state_machine.current_state)
            self.storage.close()

        self.status.started = False
        logger.info("Node stopped")

    async def _load_keypair(self) -> None:
        """Load or generate node keypair."""
        from atc.crypto.sphincs import generate_keypair

        if self.config.keyfile:
            keyfile = Path(self.config.keyfile)
            if keyfile.exists():
                # Load existing key
                logger.info(f"Loading keypair from {keyfile}")
                key_data = keyfile.read_bytes()
                # Simple format: secret_key + public_key
                from atc.core.types import SecretKey
                secret = SecretKey(key_data[:64])
                public = PublicKey(key_data[64:97])
                self.keypair = KeyPair(public=public, secret=secret)
            else:
                # Generate new key
                logger.info("Generating new keypair...")
                self.keypair = generate_keypair()
                # Save key
                keyfile.parent.mkdir(parents=True, exist_ok=True)
                keyfile.write_bytes(
                    self.keypair.secret.data + self.keypair.public.data
                )
                logger.info(f"Keypair saved to {keyfile}")
        else:
            # Generate temporary key
            logger.info("Generating temporary keypair...")
            self.keypair = generate_keypair()

        logger.info(f"Node ID: {self.keypair.public.data.hex()[:16]}...")

    def _setup_callbacks(self) -> None:
        """Setup callbacks for network events."""
        # Gossip callbacks
        if self.gossip:
            self.gossip.set_callbacks(
                on_heartbeat=self._handle_heartbeat,
                on_transaction=self._handle_transaction,
            )

        # Sync callbacks
        if self.synchronizer:
            self.synchronizer.set_callbacks(
                on_block=self._handle_block,
                on_progress=self._handle_sync_progress,
            )

        # Peer manager setup
        self.peer_manager.set_message_handler(self._handle_message)

        if self.keypair:
            self.peer_manager.set_node_info(
                node_id=self.keypair.public,
                height=self.state_machine.get_chain_height(),
                best_hash=self.state_machine.get_chain_tip(),
                testnet=self.config.testnet,
            )

    async def _start_network(self) -> None:
        """Start network connections."""
        # Start gossip protocol
        if self.gossip:
            await self.gossip.start()

        # Connect to bootstrap nodes
        for node_addr in self.config.network.bootstrap_nodes:
            try:
                if ':' in node_addr:
                    host, port = node_addr.rsplit(':', 1)
                    port = int(port)
                else:
                    host = node_addr
                    port = self.config.network.listen_port

                logger.info(f"Connecting to bootstrap node: {host}:{port}")
                await self.peer_manager.add_peer(host, port)
            except Exception as e:
                logger.warning(f"Failed to connect to {node_addr}: {e}")

    async def _sync_loop(self) -> None:
        """Background synchronization loop."""
        while self._running:
            try:
                # Check if we need to sync
                peers = self.peer_manager.get_best_peers(1)
                if peers:
                    best_peer = peers[0]
                    our_height = self.state_machine.get_chain_height()

                    if best_peer.best_height > our_height:
                        self.status.syncing = True
                        logger.info(
                            f"Starting sync: {our_height} -> {best_peer.best_height}"
                        )

                        await self.synchronizer.start_sync(
                            our_height,
                            self.state_machine.get_chain_tip()
                        )

                        self.status.syncing = False

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(10)

    async def _heartbeat_loop(self) -> None:
        """Background heartbeat production loop."""
        if not self.config.mining.enabled:
            return

        while self._running:
            try:
                # Wait for sync to complete
                if self.status.syncing:
                    await asyncio.sleep(5)
                    continue

                # Produce heartbeat
                await self._produce_heartbeat()

                # Wait for next interval
                await asyncio.sleep(self.config.mining.heartbeat_interval_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(10)

    async def _status_loop(self) -> None:
        """Background status update loop."""
        while self._running:
            try:
                self._update_status()
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Status loop error: {e}")
                await asyncio.sleep(5)

    def _update_status(self) -> None:
        """Update node status."""
        self.status.connected_peers = self.peer_manager.active_peer_count
        self.status.chain_height = self.state_machine.get_chain_height()

        tip = self.state_machine.get_chain_tip()
        self.status.best_hash = tip.hex() if tip else None

        self.status.mempool_heartbeats = self.mempool.get_heartbeat_count()
        self.status.mempool_transactions = self.mempool.get_transaction_count()
        self.status.uptime_seconds = int(time.time() - self.status.start_time)

    async def _produce_heartbeat(self) -> None:
        """Produce a heartbeat."""
        if not self.keypair:
            return

        try:
            from atc.protocol.heartbeat import create_heartbeat

            logger.debug("Producing heartbeat...")

            heartbeat = await create_heartbeat(
                self.keypair,
                self.state_machine.current_state
            )

            # Add to mempool
            await self.mempool.add_heartbeat(heartbeat)

            # Broadcast
            if self.gossip:
                sent = await self.gossip.broadcast_heartbeat(heartbeat)
                logger.info(f"Heartbeat produced and sent to {sent} peers")

        except Exception as e:
            logger.error(f"Failed to produce heartbeat: {e}")

    async def _handle_heartbeat(self, heartbeat_data: bytes) -> bool:
        """Handle received heartbeat."""
        try:
            from atc.core.heartbeat import Heartbeat
            from atc.consensus.validation import validate_heartbeat_full

            heartbeat, _ = Heartbeat.deserialize(heartbeat_data)

            # Validate
            validate_heartbeat_full(
                heartbeat,
                self.state_machine.current_state,
                self.state_machine.current_state.btc_height
            )

            # Add to mempool
            await self.mempool.add_heartbeat(heartbeat)

            return True

        except Exception as e:
            logger.debug(f"Heartbeat validation failed: {e}")
            return False

    async def _handle_transaction(self, tx_data: bytes) -> bool:
        """Handle received transaction."""
        try:
            from atc.core.transaction import Transaction
            from atc.consensus.validation import validate_transaction_full

            transaction, _ = Transaction.deserialize(tx_data)

            # Validate
            validate_transaction_full(
                transaction,
                self.state_machine.current_state,
                int(time.time() * 1000),
                self.state_machine.current_state.btc_height
            )

            # Add to mempool
            await self.mempool.add_transaction(transaction)

            return True

        except Exception as e:
            logger.debug(f"Transaction validation failed: {e}")
            return False

    async def _handle_block(self, block_data: bytes) -> None:
        """Handle received block."""
        try:
            block, _ = Block.deserialize(block_data)

            # Validate and apply
            success = self.state_machine.apply_block(block)

            if success:
                # Update fork choice
                self.fork_choice.add_block(block)

                # Remove confirmed items from mempool
                hb_ids = [hb.heartbeat_id() for hb in block.heartbeats]
                tx_ids = [tx.transaction_id() for tx in block.transactions]
                await self.mempool.remove_confirmed(hb_ids, tx_ids)

                # Save to storage
                if self.storage:
                    self.storage.save_block(block)
                    self.storage.save_global_state(self.state_machine.current_state)

                # Update peer manager
                self.peer_manager.update_height(
                    block.header.height,
                    block.block_hash()
                )

                logger.info(f"Applied block {block.header.height}")

        except Exception as e:
            logger.error(f"Failed to handle block: {e}")

    async def _handle_sync_progress(self, progress) -> None:
        """Handle sync progress update."""
        logger.debug(
            f"Sync progress: {progress.blocks_downloaded}/{progress.target_height} "
            f"({progress.progress_percent:.1f}%)"
        )

    async def _handle_message(self, peer, message) -> None:
        """Handle incoming network message."""
        from atc.network.messages import MessageType, HeartbeatMessage, TransactionMessage

        try:
            if message.header.msg_type == MessageType.HEARTBEAT:
                hb_msg = HeartbeatMessage.deserialize(message.payload)
                for hb_data in hb_msg.heartbeats:
                    await self.gossip.handle_heartbeat(peer, hb_data)

            elif message.header.msg_type == MessageType.TRANSACTION:
                tx_msg = TransactionMessage.deserialize(message.payload)
                for tx_data in tx_msg.transactions:
                    await self.gossip.handle_transaction(peer, tx_data)

        except Exception as e:
            logger.debug(f"Message handling error: {e}")

    # Public API methods

    async def submit_transaction(self, transaction: "Transaction") -> bool:
        """Submit a new transaction."""
        try:
            # Validate
            from atc.consensus.validation import validate_transaction_full
            validate_transaction_full(
                transaction,
                self.state_machine.current_state,
                int(time.time() * 1000),
                self.state_machine.current_state.btc_height
            )

            # Add to mempool
            await self.mempool.add_transaction(transaction)

            # Broadcast
            if self.gossip:
                await self.gossip.broadcast_transaction(transaction)

            return True

        except Exception as e:
            logger.error(f"Transaction submission failed: {e}")
            return False

    def get_balance(self, pubkey: PublicKey) -> int:
        """Get balance for public key."""
        return self.state_machine.get_balance(pubkey)

    def get_nonce(self, pubkey: PublicKey) -> int:
        """Get nonce for public key."""
        return self.state_machine.get_nonce(pubkey)

    def get_status(self) -> dict:
        """Get node status."""
        self._update_status()
        return {
            "started": self.status.started,
            "syncing": self.status.syncing,
            "connected_peers": self.status.connected_peers,
            "chain_height": self.status.chain_height,
            "best_hash": self.status.best_hash,
            "mempool_heartbeats": self.status.mempool_heartbeats,
            "mempool_transactions": self.status.mempool_transactions,
            "uptime_seconds": self.status.uptime_seconds,
            "version": PROTOCOL_VERSION,
            "network": "testnet" if self.config.testnet else "mainnet",
        }

    def get_peers(self) -> List[dict]:
        """Get connected peers."""
        return self.peer_manager.to_dict()

    def get_mempool_info(self) -> dict:
        """Get mempool information."""
        return self.mempool.get_statistics()


def get_node_info() -> dict:
    """Get information about node implementation."""
    return {
        "version": PROTOCOL_VERSION,
        "components": [
            "state_machine",
            "storage",
            "mempool",
            "peer_manager",
            "synchronizer",
            "gossip",
            "fork_choice",
        ],
    }
