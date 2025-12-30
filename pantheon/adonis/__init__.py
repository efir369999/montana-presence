"""
DEPRECATED: pantheon.adonis has been merged into pantheon.hal

The Adonis reputation system is now part of the HAL (Human Analyse Language)
unified module. Please update your imports:

OLD: from pantheon.adonis import AdonisEngine, AdonisProfile
NEW: from pantheon.hal import HalEngine, HalProfile

For backward compatibility, this module re-exports the Hal* classes with
their old Adonis* names. These aliases will be removed in a future version.
"""
import warnings

warnings.warn(
    "pantheon.adonis is deprecated. Use pantheon.hal instead. "
    "AdonisEngine -> HalEngine, AdonisProfile -> HalProfile",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from hal with backward compatibility names
from pantheon.hal import (
    # Core types
    ReputationDimension,
    ReputationEvent,
    DimensionScore,
    ReputationRecord,
    Handshake,
    EntropyMonitor,
    # Main classes (both old and new names)
    HalProfile,
    HalEngine,
    AdonisProfile,  # Alias for HalProfile
    AdonisEngine,   # Alias for HalEngine
    # Functions
    compute_f_rep,
    compute_f_rep_adonis,  # Alias for compute_f_rep
    create_reputation_modifier,
    # Constants
    MAX_VOUCHES_PER_DAY,
    PROFILE_EXPIRATION_SECONDS,
    MAX_TIMESTAMP_DRIFT,
    MIN_NETWORK_ENTROPY,
    ENTROPY_DECAY_RATE,
    MIN_NODES_FOR_CLUSTER_ANALYSIS,
    TIMING_VARIANCE_THRESHOLD,
    MIN_HANDSHAKE_COUNTRIES,
)

__all__ = [
    'ReputationDimension',
    'ReputationEvent',
    'DimensionScore',
    'ReputationRecord',
    'Handshake',
    'EntropyMonitor',
    'HalProfile',
    'HalEngine',
    'AdonisProfile',
    'AdonisEngine',
    'compute_f_rep',
    'compute_f_rep_adonis',
    'create_reputation_modifier',
    'MAX_VOUCHES_PER_DAY',
    'PROFILE_EXPIRATION_SECONDS',
    'MAX_TIMESTAMP_DRIFT',
    'MIN_NETWORK_ENTROPY',
    'ENTROPY_DECAY_RATE',
    'MIN_NODES_FOR_CLUSTER_ANALYSIS',
    'TIMING_VARIANCE_THRESHOLD',
    'MIN_HANDSHAKE_COUNTRIES',
]
