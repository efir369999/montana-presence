"""
ATC Protocol v7 Consensus
Part X of Technical Specification

Score-based consensus with sqrt(heartbeats) weighting.
"""

from atc.consensus.score import (
    compute_score,
    effective_score,
    compute_block_weight,
)
from atc.consensus.fork_choice import (
    chain_weight,
    select_best_chain,
    ForkChoiceRule,
)

__all__ = [
    # Score
    "compute_score",
    "effective_score",
    "compute_block_weight",
    # Fork Choice
    "chain_weight",
    "select_best_chain",
    "ForkChoiceRule",
]
