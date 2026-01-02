"""
Ɉ Montana Light Node v3.1

Type 2 node per MONTANA_TECHNICAL_SPECIFICATION.md §1.3.1.
"""

from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from montana.constants import (
    PROTOCOL_VERSION,
    DEFAULT_PORT,
    HEARTBEAT_INTERVAL_MS,
)
from montana.core.types import Hash, NodeType, PublicKey
from montana.core.block import Block, BlockHeader
from montana.core.heartbeat import (
    LightHeartbeat,
    create_light_heartbeat,
    sign_heartbeat,
)
from montana.network.protocol import ServiceFlags, MessageType
from montana.network.peer import Peer, PeerManager
from montana.network.bootstrap import BootstrapManager
from montana.network.handshake import perform_handshake

logger = logging.getLogger(__name__)


@dataclass
class LightNodeConfig:
    """Light Node configuration."""
    port: int = 0  # 0 = don't listen
    max_peers: int = 8
    bootstrap: List[str] = field(default_factory=list)
    user_agent: str = "Montana-Light/0.1.0"


class LightNode:
    """
    Light Node (Type 2) implementation.

    Capabilities:
    - Header chain only (no full blocks)
    - Heartbeat generation (no VDF)
    - Transaction submission
    - SPV verification

    From §1.3.1:
    "Light Nodes connect to existing Full Nodes, storing history from
    connection point only. They participate through heartbeats at Tier 2."
    """

    def __init__(
        self,
        config: LightNodeConfig,
        secret_key,
        public_key: PublicKey,
    ):
        self.config = config
        self.secret_key = secret_key
        self.public_key = public_key
        self.node_id = Hash(public_key.serialize()[:32])
        self.node_type = NodeType.LIGHT

        # Network
        self.peer_manager: Optional[PeerManager] = None
        self.bootstrap_manager: Optional[BootstrapManager] = None

        # Header chain
        self._headers: Dict[Hash, BlockHeader] = {}
        self._best_header: Optional[BlockHeader] = None
        self._height = 0

        # State
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._last_heartbeat_hash = Hash.zero()
        self._connected_full_node: Optional[Peer] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def services(self) -> int:
        return ServiceFlags.NODE_NETWORK

    @property
    def height(self) -> int:
        return self._height

    async def start(self):
        """Start the light node."""
        if self._running:
            return

        logger.info(f"Starting Light Node {self.node_id.hex()[:16]}...")

        # Initialize network
        self.peer_manager = PeerManager(
            local_services=self.services,
            max_peers=self.config.max_peers,
            max_outbound=self.config.max_peers,
            max_inbound=0,  # Light nodes don't accept connections
        )
        self.peer_manager.on_peer_ready(self._on_peer_ready)

        self.bootstrap_manager = BootstrapManager(self.peer_manager)

        self._running = True

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._sync_headers_loop()),
        ]

        # Connect to bootstrap
        await self.bootstrap_manager.connect_to_bootstrap(min_connections=2)

        # Perform handshakes
        for peer in list(self.peer_manager.peers.values()):
            result = await perform_handshake(
                peer,
                self.peer_manager,
                self.services,
                self._height,
                self.config.user_agent,
            )
            if result.success:
                self._connected_full_node = peer
                logger.info(f"Connected to Full Node: {peer.address}")

        logger.info("Light Node started")

    async def stop(self):
        """Stop the light node."""
        if not self._running:
            return

        logger.info("Stopping Light Node...")

        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []

        # Disconnect peers
        if self.peer_manager:
            for addr in list(self.peer_manager.peers.keys()):
                await self.peer_manager.disconnect_peer(addr)

        logger.info("Light Node stopped")

    async def _on_peer_ready(self, peer: Peer):
        """Called when peer handshake completes."""
        logger.info(f"Peer ready: {peer.address}")

        # Request headers
        await self._request_headers(peer)

    async def _request_headers(self, peer: Peer):
        """Request headers from peer."""
        # Would send GetHeaders message
        # For now, placeholder
        pass

    async def _heartbeat_loop(self):
        """Generate heartbeats."""
        logger.info("Starting heartbeat loop")

        while self._running:
            try:
                # Create light heartbeat (no VDF proof)
                heartbeat = create_light_heartbeat(
                    node_id=self.node_id,
                    public_key=self.public_key,
                    prev_heartbeat_hash=self._last_heartbeat_hash,
                )

                # Sign heartbeat
                heartbeat = sign_heartbeat(heartbeat, self.secret_key)
                self._last_heartbeat_hash = heartbeat.hash()

                logger.debug(f"Generated heartbeat {self._last_heartbeat_hash.hex()[:16]}")

                # Send to connected full node
                if self._connected_full_node and self._connected_full_node.is_ready:
                    await self._connected_full_node.send_message(
                        MessageType.HEARTBEAT,
                        heartbeat.serialize()
                    )

                await asyncio.sleep(HEARTBEAT_INTERVAL_MS / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(1.0)

    async def _sync_headers_loop(self):
        """Sync headers from peers."""
        while self._running:
            try:
                # Request headers periodically
                if self._connected_full_node and self._connected_full_node.is_ready:
                    await self._request_headers(self._connected_full_node)

                await asyncio.sleep(30.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Header sync error: {e}")
                await asyncio.sleep(10.0)

    async def submit_transaction(self, tx_data: bytes) -> bool:
        """
        Submit transaction to network.

        Args:
            tx_data: Serialized transaction

        Returns:
            True if submitted successfully
        """
        if not self._connected_full_node or not self._connected_full_node.is_ready:
            logger.warning("No connected Full Node for transaction submission")
            return False

        return await self._connected_full_node.send_message(
            MessageType.TX,
            tx_data
        )

    async def verify_spv(
        self,
        tx_hash: Hash,
        block_hash: Hash,
        merkle_proof: List[Hash],
    ) -> bool:
        """
        Verify transaction inclusion with SPV proof.

        Args:
            tx_hash: Transaction hash
            block_hash: Block containing transaction
            merkle_proof: Merkle proof

        Returns:
            True if transaction is included in block
        """
        from montana.crypto.hash import sha3_256

        # Get block header
        header = self._headers.get(block_hash)
        if not header:
            logger.warning(f"Unknown block: {block_hash.hex()[:16]}")
            return False

        # Verify Merkle proof
        current = tx_hash
        for sibling in merkle_proof:
            # Combine in order (left or right based on hash comparison)
            if current.data < sibling.data:
                combined = current.data + sibling.data
            else:
                combined = sibling.data + current.data
            current = sha3_256(combined)

        # Check against tx_root
        if current == header.tx_root:
            return True

        logger.warning("SPV verification failed: root mismatch")
        return False

    def get_status(self) -> Dict:
        """Get node status."""
        return {
            "node_id": self.node_id.hex(),
            "node_type": "LIGHT",
            "running": self._running,
            "height": self._height,
            "peers": self.peer_manager.peer_count if self.peer_manager else 0,
            "headers": len(self._headers),
            "connected_full_node": (
                self._connected_full_node.address
                if self._connected_full_node else None
            ),
        }
