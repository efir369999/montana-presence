"""
HAL — Human Analyse Language

Unified module for proving humanity and analyzing behavior.
Named after Hal Finney (1956-2014), who understood Sybil resistance
before anyone else.

=== COMPONENTS ===

1. REPUTATION (5 Fingers of Adonis):
   - TIME (50%): Bitcoin blocks since halving
   - INTEGRITY (20%): No violations
   - STORAGE (15%): Chain history stored
   - EPOCHS (10%): Halvings survived
   - HANDSHAKE (5%): Trust bonds (12 Apostles)

2. GRADUATED TRUST (Humanity Proofs):
   - Tier 1: Hardware (3 Apostles, weight 0.3)
   - Tier 2: Social (6 Apostles, weight 0.6)
   - Tier 3: Time-Locked (12 Apostles, weight 1.0)

3. BEHAVIORAL ANALYSIS (Sybil Detection):
   - ClusterDetector: Pairwise correlation
   - GlobalByzantineTracker: Fingerprinting

=== SYBIL ECONOMICS ===

Creating N fake identities requires:
- Tier 1: N physical devices ($50-500 each)
- Tier 2: N social networks (months/years)
- Tier 3: N Bitcoin halvings (4 years EACH)

100 fake identities = 400 years waiting.
This is the Hal Finney vision realized.

"Running bitcoin" - Hal Finney, 2009
"""

from .humanity import (
    HumanityTier,
    HumanityProof,
    HumanityVerifier,
    compute_humanity_score,
    get_max_apostles,
    verify_different_humans,
    # Constants
    MAX_APOSTLES_HARDWARE,
    MAX_APOSTLES_SOCIAL,
    MAX_APOSTLES_TIMELOCKED,
    HUMANITY_WEIGHT_HARDWARE,
    HUMANITY_WEIGHT_SOCIAL,
    HUMANITY_WEIGHT_TIMELOCKED,
    HANDSHAKE_MIN_HUMANITY,
)

from .hardware import (
    HardwareAttestation,
    HardwareType,
    TPMAttestation,
    SecureEnclaveAttestation,
    FIDO2Attestation,
    HardwareVerifier,
    create_hardware_proof,
    verify_hardware_proof,
)

from .social import (
    SocialProof,
    SocialGraph,
    SocialVerifier,
    create_social_proof,
    verify_social_proof,
    analyze_sybil_patterns,
)

from .timelock import (
    IdentityCommitment,
    TimeLockProof,
    TimeLockVerifier,
    create_identity_commitment,
    create_time_locked_proof,
    verify_time_locked_proof,
    # Constants
    HALVING_INTERVAL,
    MIN_EPOCHS_FOR_TIMELOCKED,
)

from .behavioral import (
    # Cluster detection (Layer 1 - pairwise correlation)
    ClusterDetector,
    ClusterInfo,
    ActionRecord,
    # Byzantine tracking (Layer 2 - behavioral fingerprinting)
    GlobalByzantineTracker,
    # Constants
    CORRELATION_WINDOW_SECONDS,
    MAX_CORRELATION_THRESHOLD,
    CORRELATION_PENALTY_FACTOR,
    MAX_CLUSTER_INFLUENCE,
    MAX_BYZANTINE_INFLUENCE,
    FINGERPRINT_SIMILARITY_THRESHOLD,
)

from .reputation import (
    # Core types
    ReputationDimension,
    ReputationEvent,
    DimensionScore,
    ReputationRecord,
    Handshake,
    # Main classes
    HalProfile,
    HalEngine,
    EntropyMonitor,
    # Functions
    compute_f_rep,
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
    # Core
    'HumanityTier',
    'HumanityProof',
    'HumanityVerifier',
    'compute_humanity_score',
    'get_max_apostles',
    'verify_different_humans',
    # Hardware
    'HardwareAttestation',
    'HardwareType',
    'TPMAttestation',
    'SecureEnclaveAttestation',
    'FIDO2Attestation',
    'HardwareVerifier',
    'create_hardware_proof',
    'verify_hardware_proof',
    # Social
    'SocialProof',
    'SocialGraph',
    'SocialVerifier',
    'create_social_proof',
    'verify_social_proof',
    'analyze_sybil_patterns',
    # Time-lock
    'IdentityCommitment',
    'TimeLockProof',
    'TimeLockVerifier',
    'create_identity_commitment',
    'create_time_locked_proof',
    'verify_time_locked_proof',
    # Constants
    'MAX_APOSTLES_HARDWARE',
    'MAX_APOSTLES_SOCIAL',
    'MAX_APOSTLES_TIMELOCKED',
    'HUMANITY_WEIGHT_HARDWARE',
    'HUMANITY_WEIGHT_SOCIAL',
    'HUMANITY_WEIGHT_TIMELOCKED',
    'HANDSHAKE_MIN_HUMANITY',
    'HALVING_INTERVAL',
    'MIN_EPOCHS_FOR_TIMELOCKED',
    # Behavioral (Sybil detection)
    'ClusterDetector',
    'ClusterInfo',
    'ActionRecord',
    'GlobalByzantineTracker',
    'CORRELATION_WINDOW_SECONDS',
    'MAX_CORRELATION_THRESHOLD',
    'CORRELATION_PENALTY_FACTOR',
    'MAX_CLUSTER_INFLUENCE',
    'MAX_BYZANTINE_INFLUENCE',
    'FINGERPRINT_SIMILARITY_THRESHOLD',
    # Reputation (5 Fingers)
    'ReputationDimension',
    'ReputationEvent',
    'DimensionScore',
    'ReputationRecord',
    'Handshake',
    'HalProfile',
    'HalEngine',
    'EntropyMonitor',
    'compute_f_rep',
    'create_reputation_modifier',
    # Reputation constants
    'MAX_VOUCHES_PER_DAY',
    'PROFILE_EXPIRATION_SECONDS',
    'MAX_TIMESTAMP_DRIFT',
    'MIN_NETWORK_ENTROPY',
    'ENTROPY_DECAY_RATE',
    'MIN_NODES_FOR_CLUSTER_ANALYSIS',
    'TIMING_VARIANCE_THRESHOLD',
    'MIN_HANDSHAKE_COUNTRIES',
]
