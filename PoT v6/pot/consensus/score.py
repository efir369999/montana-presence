"""
PoT Protocol v6 Score Calculation
Part X of Technical Specification

Score-based consensus using sqrt(heartbeats) weighting.

Formula: Score(n) = √(epoch_heartbeats)
Effective Score: Score × activity_multiplier
"""

from __future__ import annotations
import math
import logging
from typing import List, Optional, TYPE_CHECKING

from pot.constants import (
    SCORE_PRECISION,
    SCORE_MIN_HEARTBEATS,
    SCORE_MAX_MULTIPLIER,
    EPOCH_DURATION_BLOCKS,
    ACTIVITY_WINDOW_BLOCKS,
    INACTIVITY_PENALTY_RATE,
)
from pot.core.types import PublicKey

if TYPE_CHECKING:
    from pot.core.state import GlobalState, AccountState
    from pot.core.block import Block, BlockSigner

logger = logging.getLogger(__name__)


def compute_score(epoch_heartbeats: int) -> float:
    """
    Compute raw score from heartbeat count.

    Per specification (Part X):
    Score(n) = √(epoch_heartbeats)

    The square root provides:
    - Diminishing returns for more heartbeats
    - Democratic distribution of influence
    - Resistance to Sybil attacks

    Args:
        epoch_heartbeats: Number of heartbeats in current epoch

    Returns:
        Raw score as float
    """
    if epoch_heartbeats < SCORE_MIN_HEARTBEATS:
        return 0.0

    return math.sqrt(epoch_heartbeats)


def compute_score_fixed(epoch_heartbeats: int) -> int:
    """
    Compute score as fixed-point integer (score × 10^6).

    Used for serialization and deterministic calculations.

    Args:
        epoch_heartbeats: Number of heartbeats in current epoch

    Returns:
        Score as fixed-point integer
    """
    score = compute_score(epoch_heartbeats)
    return int(score * SCORE_PRECISION)


def score_from_fixed(score_fixed: int) -> float:
    """Convert fixed-point score to float."""
    return score_fixed / SCORE_PRECISION


def effective_score(
    pubkey: PublicKey,
    state: "GlobalState",
    current_height: Optional[int] = None
) -> float:
    """
    Compute effective score with activity multiplier.

    Per specification (Part X):
    - Base score = √(epoch_heartbeats)
    - Activity multiplier based on recent activity
    - Penalty for inactivity

    Effective Score = base_score × activity_multiplier

    Args:
        pubkey: Node's public key
        state: Current global state
        current_height: Current block height (defaults to chain_height)

    Returns:
        Effective score with activity adjustments
    """
    account = state.get_account(pubkey)
    if account is None:
        return 0.0

    base_score = compute_score(account.epoch_heartbeats)
    if base_score == 0.0:
        return 0.0

    # Calculate activity multiplier
    if current_height is None:
        current_height = state.chain_height

    multiplier = compute_activity_multiplier(
        account.last_heartbeat_height,
        current_height
    )

    return base_score * multiplier


def effective_score_fixed(
    pubkey: PublicKey,
    state: "GlobalState",
    current_height: Optional[int] = None
) -> int:
    """Compute effective score as fixed-point integer."""
    score = effective_score(pubkey, state, current_height)
    return int(score * SCORE_PRECISION)


def compute_activity_multiplier(
    last_heartbeat_height: int,
    current_height: int
) -> float:
    """
    Compute activity multiplier based on recency.

    Per specification (Part X):
    - Full multiplier (1.0) if active within ACTIVITY_WINDOW_BLOCKS
    - Decreasing multiplier for longer inactivity
    - Minimum multiplier to maintain some score

    Args:
        last_heartbeat_height: Height of last heartbeat
        current_height: Current block height

    Returns:
        Activity multiplier (0.0 to 1.0)
    """
    if last_heartbeat_height <= 0:
        return 0.0

    blocks_since_active = current_height - last_heartbeat_height

    if blocks_since_active <= ACTIVITY_WINDOW_BLOCKS:
        # Active within window - full multiplier
        return 1.0

    # Calculate decay
    inactive_blocks = blocks_since_active - ACTIVITY_WINDOW_BLOCKS
    decay = inactive_blocks * INACTIVITY_PENALTY_RATE

    # Minimum multiplier of 0.1 to maintain some baseline
    return max(0.1, 1.0 - decay)


def compute_block_weight(signers: List["BlockSigner"]) -> float:
    """
    Compute total weight of block signers.

    Per specification (Part X):
    Block weight = Σ(signer_scores)

    Args:
        signers: List of block signers with their scores

    Returns:
        Total block weight
    """
    return sum(signer.score() for signer in signers)


def compute_block_weight_fixed(signers: List["BlockSigner"]) -> int:
    """Compute block weight as fixed-point integer."""
    return sum(signer.score_fixed for signer in signers)


def compute_chain_score(
    blocks: List["Block"],
    state: "GlobalState"
) -> float:
    """
    Compute cumulative score of a chain.

    Per specification (Part X):
    Chain score = Σ(block_weights)

    Args:
        blocks: List of blocks in the chain
        state: Global state for score lookups

    Returns:
        Total chain score
    """
    total = 0.0
    for block in blocks:
        total += compute_block_weight(block.signers)
    return total


def is_eligible_signer(
    pubkey: PublicKey,
    state: "GlobalState",
    min_heartbeats: int = SCORE_MIN_HEARTBEATS
) -> bool:
    """
    Check if a node is eligible to sign blocks.

    Per specification (Part X):
    - Must have minimum heartbeats in epoch
    - Must have been active recently

    Args:
        pubkey: Node's public key
        state: Current global state
        min_heartbeats: Minimum heartbeat requirement

    Returns:
        True if eligible to sign
    """
    account = state.get_account(pubkey)
    if account is None:
        return False

    if account.epoch_heartbeats < min_heartbeats:
        return False

    # Check activity
    blocks_since_active = state.chain_height - account.last_heartbeat_height
    if blocks_since_active > ACTIVITY_WINDOW_BLOCKS * 2:
        return False

    return True


def rank_signers(
    pubkeys: List[PublicKey],
    state: "GlobalState"
) -> List[tuple]:
    """
    Rank potential signers by effective score.

    Args:
        pubkeys: List of candidate public keys
        state: Current global state

    Returns:
        List of (pubkey, score) tuples sorted by score descending
    """
    ranked = []
    for pk in pubkeys:
        score = effective_score(pk, state)
        if score > 0:
            ranked.append((pk, score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def compute_score_percentile(
    pubkey: PublicKey,
    state: "GlobalState"
) -> float:
    """
    Compute a node's score percentile among all active accounts.

    Args:
        pubkey: Node's public key
        state: Current global state

    Returns:
        Percentile (0.0 to 100.0)
    """
    target_score = effective_score(pubkey, state)
    if target_score == 0:
        return 0.0

    all_scores = []
    for pk in state.get_all_pubkeys():
        score = effective_score(pk, state)
        if score > 0:
            all_scores.append(score)

    if not all_scores:
        return 0.0

    all_scores.sort()
    position = sum(1 for s in all_scores if s <= target_score)

    return (position / len(all_scores)) * 100.0


def normalize_scores(scores: List[float]) -> List[float]:
    """
    Normalize scores to sum to 1.0.

    Used for weighted random selection.

    Args:
        scores: List of raw scores

    Returns:
        Normalized scores summing to 1.0
    """
    total = sum(scores)
    if total == 0:
        return [0.0] * len(scores)
    return [s / total for s in scores]


def get_score_info() -> dict:
    """Get information about score calculation."""
    return {
        "formula": "Score(n) = √(epoch_heartbeats)",
        "precision": SCORE_PRECISION,
        "min_heartbeats": SCORE_MIN_HEARTBEATS,
        "max_multiplier": SCORE_MAX_MULTIPLIER,
        "activity_window_blocks": ACTIVITY_WINDOW_BLOCKS,
        "inactivity_penalty_rate": INACTIVITY_PENALTY_RATE,
    }
