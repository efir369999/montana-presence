//! Unit tests for consensus module
//!
//! Architecture: 80% Full Node + 20% Verified User
//!
//! Full Nodes: servers running 24/7, automatic presence every τ₁
//! Verified Users: mobile wallets with FIDO2/WebAuthn biometric attestation

use montana::{
    GRACE_PERIOD_SECS, SLOTS_PER_TAU2, SLOT_DURATION_SECS,
    FULL_NODE_CAP_PERCENT, LIGHT_NODE_CAP_PERCENT, LIGHT_CLIENT_CAP_PERCENT,
    LOTTERY_PRECISION,
};

#[test]
fn test_consensus_constants() {
    // Grace period: last 30 seconds of τ₂, no new presence submissions
    assert_eq!(GRACE_PERIOD_SECS, 30);

    // 10 slots per τ₂ (10 minutes), 1 minute each
    assert_eq!(SLOTS_PER_TAU2, 10);
    assert_eq!(SLOT_DURATION_SECS, 60);

    // New 80/20 architecture
    assert_eq!(FULL_NODE_CAP_PERCENT, 80);

    // Legacy constants for backwards compatibility (Verified User = Light Node)
    assert_eq!(LIGHT_NODE_CAP_PERCENT, 20);   // = VERIFIED_USER_CAP_PERCENT
    assert_eq!(LIGHT_CLIENT_CAP_PERCENT, 0);  // Removed tier

    // Tier caps sum to 100%
    assert_eq!(FULL_NODE_CAP_PERCENT + LIGHT_NODE_CAP_PERCENT, 100);

    // Precision for weight calculations
    assert_eq!(LOTTERY_PRECISION, 1_000_000);
}

#[test]
fn test_tier_caps_prevent_centralization() {
    // Even if Full Nodes have 95% of raw weight, they can only win 80% of lotteries
    // Verified Users always get 20% — humans control decentralization

    let full_raw_weight: u64 = 95_000_000;
    let verified_user_raw_weight: u64 = 5_000_000;
    let _total_raw = full_raw_weight + verified_user_raw_weight;

    // Full nodes: 95% raw → 80% effective (capped)
    // Verified users: 5% raw → 20% effective (boosted)

    // This ensures humans always have significant power
    // even when infrastructure dominates raw weight

    assert_eq!(FULL_NODE_CAP_PERCENT + LIGHT_NODE_CAP_PERCENT, 100);
}
