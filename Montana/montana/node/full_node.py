"""
Ɉ Montana Full Node v3.1

Type 1 node with VDF and full history per MONTANA_TECHNICAL_SPECIFICATION.md §1.3.1.
"""

from __future__ import annotations
import asyncio
import logging
import time
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from montana.constants import (
    PROTOCOL_VERSION,
    DEFAULT_PORT,
    VDF_CHECKPOINT_INTERVAL_SEC,
    HEARTBEAT_INTERVAL_MS,
    BLOCK_TIME_TARGET_SEC,
)
from montana.core.types import Hash, NodeType, PublicKey
from montana.core.block import Block, create_block, sign_block
from montana.core.heartbeat import (
    FullHeartbeat,
    create_full_heartbeat,
    sign_heartbeat,
)
from montana.core.vdf import SHAKE256VDF as VDFComputer
from montana.core.vdf_accumulator import VDFAccumulator, FinalityLevel
from montana.network.protocol import ServiceFlags, MessageType
from montana.network.peer import PeerManager
from montana.network.bootstrap import BootstrapManager
from montana.network.handshake import perform_handshake
from montana.network.sync import SyncManager
from montana.state.storage import Database, BlockStore, StateStore
from montana.state.accounts import AccountManager
from montana.state.machine import StateMachine
from montana.consensus.dag import PHANTOMOrdering
from montana.consensus.eligibility import BlockEligibility
from montana.node.mempool import Mempool

logger = logging.getLogger(__name__)


@dataclass
class FullNodeConfig:
    """Full Node configuration."""
    data_dir: str = "./montana_data"
    port: int = DEFAULT_PORT
    max_peers: int = 125
    bootstrap: List[str] = field(default_factory=list)
    enable_mining: bool = True
    user_agent: str = "Montana/0.1.0"


class FullNode:
    """
    Full Node (Type 1) implementation.

    Capabilities:
    - Full timechain history
    - VDF computation and verification
    - Block production
    - Heartbeat generation
    - Transaction relay
    - Peer discovery
    """

    def __init__(
        self,
        config: FullNodeConfig,
        secret_key,
        public_key: PublicKey,
    ):
        self.config = config
        self.secret_key = secret_key
        self.public_key = public_key
        self.node_id = Hash(public_key.serialize()[:32])
        self.node_type = NodeType.FULL

        # Components (initialized in start())
        self.db: Optional[Database] = None
        self.block_store: Optional[BlockStore] = None
        self.state_store: Optional[StateStore] = None
        self.accounts: Optional[AccountManager] = None
        self.state_machine: Optional[StateMachine] = None
        self.peer_manager: Optional[PeerManager] = None
        self.bootstrap_manager: Optional[BootstrapManager] = None
        self.sync_manager: Optional[SyncManager] = None
        self.mempool: Optional[Mempool] = None
        self.dag: Optional[PHANTOMOrdering] = None
        self.eligibility: Optional[BlockEligibility] = None

        # VDF components
        self.vdf: Optional[VDFComputer] = None
        self.vdf_accumulator: Optional[VDFAccumulator] = None

        # State
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._last_heartbeat_hash = Hash.zero()
        self._pending_heartbeats: List[FullHeartbeat] = []

        # Server
        self._server: Optional[asyncio.Server] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def services(self) -> int:
        return (
            ServiceFlags.NODE_NETWORK |
            ServiceFlags.NODE_VDF
        )

    async def start(self):
        """Start the full node."""
        if self._running:
            return

        logger.info(f"Starting Full Node {self.node_id.hex()[:16]}...")

        # Initialize database
        self.db = Database(f"{self.config.data_dir}/montana.db")
        await self.db.open()

        # Initialize stores
        self.block_store = BlockStore(self.db)
        self.state_store = StateStore(self.db)
        self.accounts = AccountManager(self.db)

        # Initialize state machine
        self.state_machine = StateMachine(
            self.db,
            self.block_store,
            self.state_store,
            self.accounts,
        )

        # Initialize DAG
        self.dag = PHANTOMOrdering(k=3)

        # Initialize mempool
        self.mempool = Mempool()

        # Initialize VDF
        self.vdf = VDFComputer()
        self.vdf_accumulator = VDFAccumulator()

        # Initialize eligibility
        self.eligibility = BlockEligibility()

        # Initialize network
        self.peer_manager = PeerManager(
            local_services=self.services,
            max_peers=self.config.max_peers,
        )
        self.peer_manager.on_peer_ready(self._on_peer_ready)

        self.bootstrap_manager = BootstrapManager(self.peer_manager)

        self.sync_manager = SyncManager(
            self.peer_manager,
            get_best_height=lambda: self.block_store.get_height() if self.block_store else -1,
            get_block=lambda h: self.block_store.get_block(h) if self.block_store else None,
            add_block=self._add_block,
        )

        self._running = True

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._vdf_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._block_production_loop()),
            asyncio.create_task(self._peer_maintenance_loop()),
        ]

        # Start server
        self._server = await asyncio.start_server(
            self._handle_connection,
            "0.0.0.0",
            self.config.port,
        )

        logger.info(f"Listening on port {self.config.port}")

        # Bootstrap network
        await self.bootstrap_manager.bootstrap_network()

        # Start sync
        await self.sync_manager.start_sync()

        logger.info("Full Node started")

    async def stop(self):
        """Stop the full node."""
        if not self._running:
            return

        logger.info("Stopping Full Node...")

        self._running = False

        # Stop sync
        if self.sync_manager:
            await self.sync_manager.stop_sync()

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []

        # Stop server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Disconnect peers
        if self.peer_manager:
            for addr in list(self.peer_manager.peers.keys()):
                await self.peer_manager.disconnect_peer(addr)

        # Close database
        if self.db:
            await self.db.close()

        logger.info("Full Node stopped")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Handle incoming connection."""
        peer = await self.peer_manager.accept_peer(reader, writer)
        if not peer:
            return

        # Perform handshake
        result = await perform_handshake(
            peer,
            self.peer_manager,
            self.services,
            await self.block_store.get_height() if self.block_store else 0,
            self.config.user_agent,
        )

        if not result.success:
            logger.warning(f"Handshake failed: {result.error}")
            await self.peer_manager.disconnect_peer(peer.address)
            return

        # Start message loop
        asyncio.create_task(self._message_loop(peer))

    async def _on_peer_ready(self, peer):
        """Called when peer handshake completes."""
        logger.info(
            f"Peer ready: {peer.address[0]}:{peer.address[1]} "
            f"v{peer.info.version} {peer.info.user_agent}"
        )

    async def _message_loop(self, peer):
        """Process messages from peer."""
        while self._running and peer.is_ready:
            try:
                result = await peer.receive_message(timeout=30.0)
                if not result:
                    continue

                msg_type, payload = result
                await self._handle_message(peer, msg_type, payload)

            except Exception as e:
                logger.error(f"Message loop error: {e}")
                break

    async def _handle_message(self, peer, msg_type: MessageType, payload: bytes):
        """Handle received message."""
        if msg_type == MessageType.PING:
            from montana.network.messages import PingMessage
            ping = PingMessage.deserialize(payload)
            await peer.send_pong(ping.nonce)

        elif msg_type == MessageType.PONG:
            from montana.network.messages import PongMessage
            pong = PongMessage.deserialize(payload)
            peer.handle_pong(pong.nonce)

        elif msg_type == MessageType.INV:
            from montana.network.messages import InvMessage
            inv = InvMessage.deserialize(payload)
            await self.sync_manager.handle_inv(peer, inv)

        elif msg_type == MessageType.BLOCK:
            block, _ = Block.deserialize(payload)
            await self.sync_manager.handle_block(peer, block)

        # Additional message types would be handled here

    async def _vdf_loop(self):
        """Continuous VDF computation."""
        logger.info("Starting VDF computation loop")

        # Initial VDF input
        current_input = await self._get_vdf_input()

        while self._running:
            try:
                # Compute VDF checkpoint
                start = time.time()
                result = self.vdf.compute_checkpoint(current_input)
                elapsed = time.time() - start

                # Add to accumulator
                block_hash = await self.state_store.get_best_block_hash()
                if block_hash:
                    level = self.vdf_accumulator.add_checkpoint(
                        block_hash,
                        result.iterations,
                        result.output,
                        result.proof,
                    )

                    if level != FinalityLevel.NONE:
                        logger.info(
                            f"VDF finality: {level.name} for {block_hash.hex()[:16]}"
                        )

                # Next input is current output
                current_input = result.output

                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"VDF loop error: {e}")
                await asyncio.sleep(1.0)

    async def _get_vdf_input(self) -> Hash:
        """Get initial VDF input."""
        # Use best block hash as VDF input
        block_hash = await self.state_store.get_best_block_hash()
        if block_hash:
            return block_hash
        return Hash.zero()

    async def _heartbeat_loop(self):
        """Generate heartbeats."""
        logger.info("Starting heartbeat loop")

        while self._running:
            try:
                # Get current VDF state
                vdf_output = self.vdf.current_output if self.vdf else Hash.zero()
                vdf_iterations = self.vdf.total_iterations if self.vdf else 0
                vdf_proof = self.vdf.get_proof() if self.vdf else b""

                # Create heartbeat
                heartbeat = create_full_heartbeat(
                    node_id=self.node_id,
                    public_key=self.public_key,
                    prev_heartbeat_hash=self._last_heartbeat_hash,
                    vdf_input=await self._get_vdf_input(),
                    vdf_output=vdf_output,
                    vdf_iterations=vdf_iterations,
                    vdf_proof=vdf_proof,
                )

                # Sign heartbeat
                heartbeat = sign_heartbeat(heartbeat, self.secret_key)

                # Store for block inclusion
                self._pending_heartbeats.append(heartbeat)
                self._last_heartbeat_hash = heartbeat.hash()

                logger.debug(f"Generated heartbeat {self._last_heartbeat_hash.hex()[:16]}")

                # Wait for next heartbeat interval
                await asyncio.sleep(HEARTBEAT_INTERVAL_MS / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(1.0)

    async def _block_production_loop(self):
        """Produce blocks when eligible."""
        logger.info("Starting block production loop")

        while self._running:
            try:
                if not self.config.enable_mining:
                    await asyncio.sleep(10.0)
                    continue

                # Check sync status
                if self.sync_manager and not self.sync_manager.is_caught_up:
                    await asyncio.sleep(1.0)
                    continue

                # Check eligibility
                vrf_output = Hash(secrets.token_bytes(32))  # Would use actual VRF
                is_eligible = self.eligibility.check_eligibility(
                    vrf_output,
                    self.node_id,
                    1.0,  # Would use actual score
                )

                if is_eligible:
                    await self._produce_block()

                await asyncio.sleep(BLOCK_TIME_TARGET_SEC)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Block production error: {e}")
                await asyncio.sleep(1.0)

    async def _produce_block(self):
        """Produce a new block."""
        logger.info("Producing block...")

        # Get parent blocks (DAG tips)
        tips = self.dag.get_tips() if self.dag else []
        if not tips:
            tip = await self.block_store.get_tip()
            if tip:
                tips = [tip.hash()]
            else:
                tips = []

        height = (await self.block_store.get_height()) + 1

        # Collect heartbeats
        heartbeats = [hb.serialize() for hb in self._pending_heartbeats[:100]]
        self._pending_heartbeats = self._pending_heartbeats[100:]

        # Collect transactions from mempool
        transactions = self.mempool.get_transactions(100) if self.mempool else []
        tx_bytes = [tx.serialize() for tx in transactions]

        # Create block
        vdf_output = self.vdf.current_output if self.vdf else Hash.zero()
        vdf_iterations = self.vdf.total_iterations if self.vdf else 0

        block = create_block(
            parent_hashes=tips,
            height=height,
            producer_id=self.node_id,
            vdf_output=vdf_output,
            vdf_iterations=vdf_iterations,
            heartbeats=heartbeats,
            transactions=tx_bytes,
            state_root=await self.state_machine.compute_state_root(),
        )

        # Sign block
        block = sign_block(block, self.secret_key)

        # Apply to local state
        result = await self.state_machine.apply_block(block)
        if result.success:
            logger.info(f"Produced block {block.hash().hex()[:16]} at height {height}")

            # Broadcast to peers
            await self._broadcast_block(block)
        else:
            logger.error(f"Failed to apply produced block: {result.error}")

    async def _broadcast_block(self, block: Block):
        """Broadcast block to all peers."""
        from montana.network.messages import InvMessage, InventoryItem
        from montana.network.protocol import InventoryType

        inv = InvMessage(items=[
            InventoryItem(InventoryType.BLOCK, block.hash())
        ])

        for peer in self.peer_manager.ready_peers:
            await peer.send_message(MessageType.INV, inv.serialize())

    async def _add_block(self, block: Block) -> bool:
        """Add block from network."""
        result = await self.state_machine.apply_block(block)
        return result.success

    async def _peer_maintenance_loop(self):
        """Maintain peer connections."""
        while self._running:
            try:
                # Ping peers
                for peer in self.peer_manager.ready_peers:
                    if time.time() - peer.last_send > 60:
                        await peer.send_ping()

                # Try to connect to more peers if below target
                if self.peer_manager.can_connect_outbound():
                    addresses = self.peer_manager.get_addresses_for_peer(10)
                    for addr, _, _ in addresses[:3]:
                        if (addr[0], addr[1]) not in self.peer_manager.peers:
                            await self.peer_manager.connect_peer((addr[0], int(addr[1])))

                await asyncio.sleep(30.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Peer maintenance error: {e}")
                await asyncio.sleep(10.0)

    def get_status(self) -> Dict:
        """Get node status."""
        return {
            "node_id": self.node_id.hex(),
            "node_type": "FULL",
            "running": self._running,
            "height": asyncio.get_event_loop().run_until_complete(
                self.block_store.get_height()
            ) if self.block_store else -1,
            "peers": self.peer_manager.peer_count if self.peer_manager else 0,
            "sync": self.sync_manager.get_sync_status() if self.sync_manager else None,
            "vdf_iterations": self.vdf.total_iterations if self.vdf else 0,
        }
