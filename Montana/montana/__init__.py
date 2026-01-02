"""
Ɉ Montana v3.6 — Mechanism for asymptotic trust in the value of time.

lim(evidence → ∞) 1 Ɉ → 1 second

Built on ATC Layer 3+.

Bootstrap server: 176.124.208.93:19656
"""

__version__ = "3.6.0"
__protocol_version__ = 9

from montana.constants import (
    PROJECT,
    SYMBOL,
    TICKER,
    TOTAL_SUPPLY,
    DEFAULT_PORT,
    PROTOCOL_VERSION,
)

# Core exports
from montana.core.types import Hash, PublicKey, NodeType, ParticipationTier, PrivacyTier
from montana.core.block import Block, BlockHeader
from montana.core.heartbeat import FullHeartbeat, LightHeartbeat
from montana.core.vdf import SHAKE256VDF as VDFComputer
from montana.core.vdf_accumulator import VDFAccumulator, FinalityLevel

# Crypto exports
from montana.crypto.hash import sha3_256, shake256
from montana.crypto.sphincs import sphincs_keygen as generate_sphincs_keypair

# Node exports
from montana.node.full_node import FullNode, FullNodeConfig
from montana.node.light_node import LightNode, LightNodeConfig

__all__ = [
    # Version
    "__version__",
    "__protocol_version__",
    # Constants
    "PROJECT",
    "SYMBOL",
    "TICKER",
    "TOTAL_SUPPLY",
    "DEFAULT_PORT",
    "PROTOCOL_VERSION",
    # Types
    "Hash",
    "PublicKey",
    "NodeType",
    "ParticipationTier",
    "PrivacyTier",
    # Core
    "Block",
    "BlockHeader",
    "FullHeartbeat",
    "LightHeartbeat",
    "VDFComputer",
    "VDFAccumulator",
    "FinalityLevel",
    # Crypto
    "sha3_256",
    "shake256",
    "generate_sphincs_keypair",
    # Nodes
    "FullNode",
    "FullNodeConfig",
    "LightNode",
    "LightNodeConfig",
]
