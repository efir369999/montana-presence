"""
ATHENA - God of Consensus (DAG Architecture)

In DAG architecture, there is no leader selection.
Any eligible node can produce blocks, ordered by PHANTOM + VDF.

Components:
- NodeState, NodeStatus: Node tracking
- ConsensusCalculator: Probability calculation for eligibility
- ConsensusEngine: Main consensus coordinator
- BootstrapManager: Network bootstrapping

Note: Slashing is now handled by HAL (pantheon.hal.slashing)
"""
from .consensus import *
from .engine import *
