"""
Montana v4.0 - The Twelve Apostles

Trust system based on real human relationships.

Each node chooses exactly 12 trust partners. No more. No less for full participation.
These are your Apostles - people you vouch for with your reputation.

Why Twelve?
- Dunbar's inner circle: Humans maintain ~12-15 close relationships
- Manageable responsibility: You can truly know 12 people
- Game-theoretic limit: Prevents trust dilution

Slashing one node slashes all vouchers.
Attack the network, lose your friends.

Trust is sacred.
"""

from .handshake import (
    Handshake,
    HandshakeRequest,
    HandshakeResponse,
    HandshakeProtocol,
    ApostleManager,
    MAX_APOSTLES,
    MIN_INTEGRITY_FOR_HANDSHAKE
)

from .slashing import (
    SlashingEvidence,
    SlashingReport,
    SlashingManager,
    SlashingPenalties,
    ATTACKER_QUARANTINE_BLOCKS,
    VOUCHER_INTEGRITY_PENALTY,
    ASSOCIATE_INTEGRITY_PENALTY
)

__all__ = [
    # Handshake
    'Handshake',
    'HandshakeRequest',
    'HandshakeResponse',
    'HandshakeProtocol',
    'ApostleManager',
    'MAX_APOSTLES',
    'MIN_INTEGRITY_FOR_HANDSHAKE',
    # Slashing
    'SlashingEvidence',
    'SlashingReport',
    'SlashingManager',
    'SlashingPenalties',
    'ATTACKER_QUARANTINE_BLOCKS',
    'VOUCHER_INTEGRITY_PENALTY',
    'ASSOCIATE_INTEGRITY_PENALTY'
]
