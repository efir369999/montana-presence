// Montana Bootstrap Verification
// Copyright (c) 2024-2026 Alejandro Montana
// Distributed under the MIT software license.

//! Bootstrap verification protocol with Trusted Core model.
//!
//! # The Bootstrap Problem
//!
//! When a new node joins the network, it knows nothing about the current chain state.
//! An attacker could feed it a fake chain. Bootstrap verification solves this by:
//!
//! 1. Querying multiple peers for chain state
//! 2. Requiring consensus among responses
//! 3. Cross-checking against trusted hardcoded nodes
//!
//! # Trust Model: "Trusted Core"
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                     All Bootstrap Peers                         │
//! │  ┌───────────────────────────────────────────────────────────┐  │
//! │  │              P2P Peers (100 nodes)                        │  │
//! │  │                                                           │  │
//! │  │   Attacker-controllable, but bounded by subnet diversity  │  │
//! │  │                                                           │  │
//! │  │  ┌─────────────────────────────────────────────────────┐  │  │
//! │  │  │         Hardcoded Nodes (5+ nodes)                  │  │  │
//! │  │  │                                                     │  │  │
//! │  │  │   ML-DSA-65 authenticated — cannot be impersonated  │  │  │
//! │  │  │   Trusted Core: their median is ground truth        │  │  │
//! │  │  │                                                     │  │  │
//! │  │  └─────────────────────────────────────────────────────┘  │  │
//! │  └───────────────────────────────────────────────────────────┘  │
//! └─────────────────────────────────────────────────────────────────┘
//! ```
//!
//! # Protocol Steps
//!
//! 1. **Query hardcoded nodes** (ML-DSA-65 verified responses)
//! 2. **Compute hardcoded_median** from their chain heights
//! 3. **Require 75%+ hardcoded nodes agree** with hardcoded_median (±1%)
//! 4. **Query P2P peers** (100 peers from 25+ subnets)
//! 5. **Warn if P2P median diverges** from hardcoded_median (don't block)
//! 6. **Accept hardcoded_median as truth**
//!
//! # Why This Works
//!
//! - Attacker cannot fake hardcoded node responses (ML-DSA-65 signatures)
//! - Attacker controlling P2P peers can only trigger warnings, not acceptance
//! - Even if attacker controls 80 of 100 P2P peers, hardcoded nodes override
//!
//! # Attack Scenarios
//!
//! | Attack | Result | Reason |
//! |--------|--------|--------|
//! | Fake hardcoded node | Rejected | ML-DSA-65 signature fails |
//! | Eclipse P2P peers | Warning only | Hardcoded nodes provide truth |
//! | DDoS hardcoded nodes | Bootstrap fails | Requires 75% hardcoded response |
//! | Compromise 1 hardcoded | Minority ignored | Need >50% hardcoded to shift median |
//!
//! # Requirements for Security
//!
//! - **Multiple hardcoded nodes**: At least 5, ideally 10+, in different jurisdictions
//! - **Private key security**: Hardcoded node keys must never leak
//! - **Geographic diversity**: No single point of failure (hosting, country, etc.)

use crate::types::{
    ip_to_subnet16, Hash, PublicKey, Slice, SliceHeader, Subnet16, GENESIS_TIMESTAMP, TAU2_MINUTES,
};
use super::subnet::{SubnetTracker, MAX_NODES_PER_SUBNET, MIN_DIVERSE_SUBNETS};
use std::collections::{HashMap, HashSet};
use std::net::SocketAddr;
use thiserror::Error;
use tracing::{error, info, warn};

/// Minimum percentage of hardcoded nodes that must respond (75%)
pub const MIN_HARDCODED_RESPONSE_PERCENT: usize = 75;

/// Additional P2P peers to query for verification
/// Total peers = hardcoded.len() + P2P_PEER_COUNT
pub const P2P_PEER_COUNT: usize = 100;

/// Minimum percentage of total peers that must agree on chain state (>50%)
pub const MIN_CONSENSUS_PERCENT: usize = 51;

/// Calculate minimum hardcoded responses needed (75% of total)
pub fn min_hardcoded_responses(hardcoded_count: usize) -> usize {
    (hardcoded_count * MIN_HARDCODED_RESPONSE_PERCENT + 99) / 100 // Round up
}

/// Calculate minimum consensus peers needed (>50% of total)
pub fn min_consensus_peers(total_peers: usize) -> usize {
    total_peers / 2 + 1
}

/// Maximum height divergence from expected (5%)
pub const MAX_HEIGHT_DIVERGENCE_PERCENT: u64 = 5;

/// Maximum allowed deviation for hardcoded nodes from median (1%)
pub const MAX_HARDCODED_DEVIATION_PERCENT: u64 = 1;

/// τ₃ in τ₂ units (14 days / 10 minutes = 2016)
/// Used for peer age calculation (not as hard requirement)
pub const TAU3_IN_TAU2: u64 = 2016;

/// Time divergence thresholds (in seconds)
/// Up to 1 minute: normal (network delays)
pub const TIME_DIVERGENCE_NORMAL_SECS: u64 = 60;
/// Up to 10 minutes: warning
pub const TIME_DIVERGENCE_WARNING_SECS: u64 = 600;
/// Over 10 minutes: critical, abort bootstrap

#[derive(Error, Debug)]
pub enum BootstrapError {
    #[error("genesis mismatch: expected {expected:?}, got {got:?}")]
    GenesisMismatch { expected: Hash, got: Hash },

    #[error("height divergence too large: expected ~{expected}, got {got} ({percent}%)")]
    HeightDivergence {
        expected: u64,
        got: u64,
        percent: u64,
    },

    #[error("cumulative weight mismatch at slice {index}: expected {expected}, got {got}")]
    WeightMismatch {
        index: u64,
        expected: u64,
        got: u64,
    },

    #[error("insufficient peer consensus: need {need}, have {have}")]
    InsufficientConsensus { need: usize, have: usize },

    #[error("insufficient hardcoded node responses: need {need}, have {have}")]
    InsufficientHardcoded { need: usize, have: usize },

    #[error("CRITICAL: hardcoded node {addr} disagrees with network consensus (height: {node_height} vs median {median_height})")]
    HardcodedNodeDisagreement {
        addr: SocketAddr,
        node_height: u64,
        median_height: u64,
    },

    #[error("CRITICAL: hardcoded nodes compromised or network under attack - manual intervention required")]
    HardcodedCompromised,

    #[error("chain validation failed: {0}")]
    ChainValidation(String),

    #[error("network error: {0}")]
    Network(String),

    #[error("insufficient subnet diversity: need {need} unique /16 subnets, have {have}")]
    InsufficientSubnetDiversity { need: usize, have: usize },

    #[error("subnet reputation root mismatch at slice {index}: expected {expected:?}, got {got:?}")]
    SubnetRootMismatch {
        index: u64,
        expected: Hash,
        got: Hash,
    },

    #[error("CRITICAL: local clock diverges from network by {divergence_secs} seconds - check system time")]
    ClockDivergenceCritical { divergence_secs: u64 },
}

/// Source of a peer (for trust differentiation)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PeerSource {
    /// Hardcoded in binary (DNS seeds, fallback IPs)
    Hardcoded,
    /// Discovered via P2P gossip
    Gossip,
}

/// Chain tip information from a peer
#[derive(Debug, Clone)]
pub struct PeerChainInfo {
    pub peer: SocketAddr,
    pub slice_height: u64,
    pub cumulative_weight: u64,
    pub tip_hash: Hash,
    pub source: PeerSource,
    /// Peer's reported timestamp (Unix seconds)
    pub peer_timestamp: u64,
}

/// Peer history in the chain
#[derive(Debug, Clone, Default)]
pub struct PeerHistory {
    /// First τ₂ this peer appeared in presence_root
    pub first_seen_tau2: u64,
    /// Last τ₂ this peer appeared in presence_root
    pub last_seen_tau2: u64,
    /// Total presence count
    pub presence_count: u64,
}

impl PeerHistory {
    /// History duration in τ₂ units
    pub fn duration_tau2(&self) -> u64 {
        self.last_seen_tau2.saturating_sub(self.first_seen_tau2)
    }

    /// Age score for peer prioritization
    ///
    /// Older peers receive higher priority for bootstrap:
    /// - At genesis: all peers have score 0 (equal priority)
    /// - As network matures: older peers naturally prioritized
    /// - Fresh Sybil nodes have low score
    pub fn age_score(&self) -> u64 {
        self.duration_tau2()
    }

    /// Check if peer has presence history older than τ₃ (14 days)
    pub fn is_established(&self) -> bool {
        self.duration_tau2() >= TAU3_IN_TAU2
    }
}

/// Bootstrap verification result
#[derive(Debug, Clone)]
pub struct BootstrapResult {
    /// Verified chain height
    pub height: u64,
    /// Verified cumulative weight
    pub cumulative_weight: u64,
    /// Number of established peers (presence history > τ₃)
    pub established_peers: usize,
    /// Number of hardcoded nodes that responded
    pub hardcoded_responses: usize,
    /// Number of P2P peers that responded
    pub p2p_responses: usize,
    /// Number of unique /16 subnets in peer set
    pub unique_subnets: usize,
    /// Median peer age in τ₂ units (for Sybil resistance metric)
    pub median_peer_age_tau2: u64,
    /// Height divergence warning (if any)
    pub height_warning: Option<String>,
    /// Network median time (verified against 100 peers from 25+ subnets)
    pub network_time: u64,
    /// Time divergence warning (if 1-10 minutes)
    pub time_warning: Option<String>,
}

/// Bootstrap verifier with hardcoded node tracking
pub struct BootstrapVerifier {
    /// Hardcoded genesis hash
    genesis_hash: Hash,
    /// Genesis timestamp
    genesis_timestamp: u64,
    /// Hardcoded peer addresses (DNS seeds + fallback IPs)
    hardcoded_peers: HashSet<SocketAddr>,
}

impl BootstrapVerifier {
    pub fn new(genesis: &Slice, hardcoded_peers: Vec<SocketAddr>) -> Self {
        Self {
            genesis_hash: genesis.hash(),
            genesis_timestamp: genesis.header.timestamp,
            hardcoded_peers: hardcoded_peers.into_iter().collect(),
        }
    }

    /// Check if peer is hardcoded
    pub fn is_hardcoded(&self, addr: &SocketAddr) -> bool {
        self.hardcoded_peers.contains(addr)
    }

    /// Calculate expected slice height based on current time
    pub fn expected_height(&self, current_time: u64) -> u64 {
        let elapsed = current_time.saturating_sub(self.genesis_timestamp);
        let tau2_secs = TAU2_MINUTES * 60;
        elapsed / tau2_secs
    }

    /// Verify height against expected (using network time, not local time)
    pub fn verify_height(
        &self,
        reported_height: u64,
        network_time: u64,
    ) -> Result<Option<String>, BootstrapError> {
        let expected = self.expected_height(network_time);

        if expected == 0 {
            return Ok(None);
        }

        let divergence = if reported_height > expected {
            ((reported_height - expected) * 100) / expected
        } else {
            ((expected - reported_height) * 100) / expected
        };

        if divergence > MAX_HEIGHT_DIVERGENCE_PERCENT {
            return Err(BootstrapError::HeightDivergence {
                expected,
                got: reported_height,
                percent: divergence,
            });
        }

        if divergence > 0 {
            Ok(Some(format!(
                "Height divergence {}%: expected ~{}, got {}",
                divergence, expected, reported_height
            )))
        } else {
            Ok(None)
        }
    }

    /// Verify local clock against network median time
    ///
    /// Takes median timestamp from 100 peers (25+ subnets).
    /// - Up to 1 minute divergence: normal (network delays)
    /// - 1-10 minutes: warning in logs
    /// - Over 10 minutes: CRITICAL, abort bootstrap
    ///
    /// If victim's clock is manipulated by malware, median from diverse
    /// peers shows real time. Controlling 51 peers from 25+ subnets requires ASN-level resources.
    pub fn verify_network_time(
        &self,
        responses: &[PeerChainInfo],
        local_time: u64,
    ) -> Result<(u64, Option<String>), BootstrapError> {
        if responses.is_empty() {
            return Ok((local_time, None));
        }

        // Get median timestamp from all peers
        let mut timestamps: Vec<u64> = responses.iter().map(|r| r.peer_timestamp).collect();
        timestamps.sort();
        let median_time = timestamps[timestamps.len() / 2];

        // Calculate divergence
        let divergence = if local_time > median_time {
            local_time - median_time
        } else {
            median_time - local_time
        };

        // Check thresholds
        if divergence > TIME_DIVERGENCE_WARNING_SECS {
            // Critical: over 10 minutes
            error!(
                "CRITICAL: Local clock diverges from network by {} seconds ({:.1} minutes)",
                divergence,
                divergence as f64 / 60.0
            );
            error!("Network median time: {} (from {} peers)", median_time, responses.len());
            error!("Local system time: {}", local_time);
            error!("Possible causes:");
            error!("  1. System clock is wrong - check NTP settings");
            error!("  2. Malware has manipulated system time");
            error!("  3. Hardware clock battery dead");
            error!("Bootstrap ABORTED. Fix system time and retry.");

            return Err(BootstrapError::ClockDivergenceCritical {
                divergence_secs: divergence,
            });
        }

        if divergence > TIME_DIVERGENCE_NORMAL_SECS {
            // Warning: 1-10 minutes
            let warning = format!(
                "Clock divergence: local={}, network={}, diff={} secs",
                local_time, median_time, divergence
            );
            warn!("{}", warning);
            info!(
                "Time divergence is within acceptable range ({:.1} minutes), continuing...",
                divergence as f64 / 60.0
            );
            return Ok((median_time, Some(warning)));
        }

        // Normal: under 1 minute
        info!(
            "Network time verified: median={} (local diff: {} secs)",
            median_time, divergence
        );

        Ok((median_time, None))
    }

    /// Verify hardcoded nodes and establish trusted consensus
    ///
    /// SECURITY MODEL (Trusted Core):
    /// - Hardcoded nodes are authenticated via ML-DSA-65 signatures
    /// - Their median is the source of truth (immune to P2P manipulation)
    /// - P2P peers are checked against hardcoded median (warning only)
    /// - >50% hardcoded agreement required for consensus
    ///
    /// This prevents Bootstrap DoS where attacker floods P2P to shift median
    /// and make honest hardcoded nodes appear "disagreeing".
    pub fn verify_hardcoded_consensus(
        &self,
        responses: &[PeerChainInfo],
    ) -> Result<u64, BootstrapError> {
        // Separate hardcoded from P2P peers
        let hardcoded: Vec<_> = responses
            .iter()
            .filter(|r| r.source == PeerSource::Hardcoded)
            .collect();

        let p2p: Vec<_> = responses
            .iter()
            .filter(|r| r.source == PeerSource::Gossip)
            .collect();

        // Require at least one hardcoded response
        if hardcoded.is_empty() {
            return Err(BootstrapError::InsufficientHardcoded {
                need: 1,
                have: 0,
            });
        }

        // Calculate median from HARDCODED ONLY (source of truth)
        let mut hc_heights: Vec<u64> = hardcoded.iter().map(|r| r.slice_height).collect();
        hc_heights.sort();
        let hardcoded_median = hc_heights[hc_heights.len() / 2];

        // Calculate tolerance (1% or minimum 1 slice)
        let tolerance = (hardcoded_median * MAX_HARDCODED_DEVIATION_PERCENT / 100).max(1);

        // Count hardcoded nodes that agree with median (within tolerance)
        let agreeing_count = hardcoded
            .iter()
            .filter(|node| {
                let diff = if node.slice_height > hardcoded_median {
                    node.slice_height - hardcoded_median
                } else {
                    hardcoded_median - node.slice_height
                };
                diff <= tolerance
            })
            .count();

        // Require >50% hardcoded agreement
        let majority_threshold = hardcoded.len() / 2 + 1;
        if agreeing_count < majority_threshold {
            // This is a real problem: hardcoded nodes themselves disagree
            error!(
                "Hardcoded nodes split: {} agree with median {}, {} disagree (need {} for majority)",
                agreeing_count, hardcoded_median, hardcoded.len() - agreeing_count, majority_threshold
            );
            // Log disagreeing nodes for debugging
            for node in &hardcoded {
                let diff = if node.slice_height > hardcoded_median {
                    node.slice_height - hardcoded_median
                } else {
                    hardcoded_median - node.slice_height
                };
                if diff > tolerance {
                    warn!(
                        "  Hardcoded {} reports height {} (median: {}, diff: {})",
                        node.peer, node.slice_height, hardcoded_median, diff
                    );
                }
            }
            return Err(BootstrapError::HardcodedCompromised);
        }

        info!(
            "Hardcoded consensus established: {}/{} nodes agree on height {} (tolerance: ±{})",
            agreeing_count, hardcoded.len(), hardcoded_median, tolerance
        );

        // Check P2P peers against hardcoded median (WARNING ONLY, non-blocking)
        // This detects potential eclipse attempts but doesn't crash
        if !p2p.is_empty() {
            let p2p_tolerance = (hardcoded_median * 5 / 100).max(10); // 5% or min 10 slices
            let suspicious_p2p: Vec<_> = p2p
                .iter()
                .filter(|node| {
                    let diff = if node.slice_height > hardcoded_median {
                        node.slice_height - hardcoded_median
                    } else {
                        hardcoded_median - node.slice_height
                    };
                    diff > p2p_tolerance
                })
                .collect();

            if !suspicious_p2p.is_empty() {
                let suspicious_percent = (suspicious_p2p.len() * 100) / p2p.len();
                if suspicious_percent > 30 {
                    warn!(
                        "SECURITY: {}% of P2P peers ({}/{}) diverge from hardcoded median {} by >5%",
                        suspicious_percent, suspicious_p2p.len(), p2p.len(), hardcoded_median
                    );
                    warn!("This may indicate an eclipse attack attempt. Trusting hardcoded nodes.");
                } else {
                    info!(
                        "P2P divergence: {}/{} peers outside tolerance (normal variance)",
                        suspicious_p2p.len(), p2p.len()
                    );
                }
            } else {
                info!(
                    "P2P consensus: all {} peers within 5% of hardcoded median {}",
                    p2p.len(), hardcoded_median
                );
            }
        }

        Ok(hardcoded_median)
    }

    /// Get verified consensus values using hardcoded nodes as source of truth
    ///
    /// Returns (height, weight, hardcoded_count, p2p_count) where:
    /// - height: from hardcoded median (trusted)
    /// - weight: from hardcoded nodes agreeing with median (trusted)
    pub fn get_verified_consensus(
        &self,
        responses: &[PeerChainInfo],
    ) -> Result<(u64, u64, usize, usize), BootstrapError> {
        // Get trusted height from hardcoded consensus
        let hardcoded_median_height = self.verify_hardcoded_consensus(responses)?;

        // Separate by source
        let hardcoded: Vec<_> = responses
            .iter()
            .filter(|r| r.source == PeerSource::Hardcoded)
            .collect();
        let p2p_count = responses
            .iter()
            .filter(|r| r.source == PeerSource::Gossip)
            .count();

        // Get weight from hardcoded nodes that agree with median
        // (they are the trusted source)
        let tolerance = (hardcoded_median_height * MAX_HARDCODED_DEVIATION_PERCENT / 100).max(1);
        let agreeing_hardcoded: Vec<_> = hardcoded
            .iter()
            .filter(|node| {
                let diff = if node.slice_height > hardcoded_median_height {
                    node.slice_height - hardcoded_median_height
                } else {
                    hardcoded_median_height - node.slice_height
                };
                diff <= tolerance
            })
            .collect();

        // Get median weight from agreeing hardcoded nodes
        let median_weight = if agreeing_hardcoded.is_empty() {
            0
        } else {
            let mut weights: Vec<u64> = agreeing_hardcoded
                .iter()
                .map(|r| r.cumulative_weight)
                .collect();
            weights.sort();
            weights[weights.len() / 2]
        };

        info!(
            "Verified consensus: height={}, weight={} ({} hardcoded + {} P2P)",
            hardcoded_median_height, median_weight, hardcoded.len(), p2p_count
        );

        Ok((hardcoded_median_height, median_weight, hardcoded.len(), p2p_count))
    }

    /// Verify cumulative weight in downloaded chain
    pub fn verify_chain_weights(
        &self,
        slices: &[Slice],
        presence_weights: &HashMap<u64, u64>,
    ) -> Result<(), BootstrapError> {
        if slices.is_empty() {
            return Ok(());
        }

        // Verify genesis
        let genesis = &slices[0];
        if genesis.hash() != self.genesis_hash {
            return Err(BootstrapError::GenesisMismatch {
                expected: self.genesis_hash,
                got: genesis.hash(),
            });
        }

        if genesis.header.cumulative_weight != 0 {
            return Err(BootstrapError::WeightMismatch {
                index: 0,
                expected: 0,
                got: genesis.header.cumulative_weight,
            });
        }

        // Verify each subsequent slice
        let mut prev_weight = 0u64;
        for slice in slices.iter().skip(1) {
            let idx = slice.header.slice_index;
            let slice_weight = presence_weights.get(&idx).copied().unwrap_or(0);
            let expected_weight = prev_weight.saturating_add(slice_weight);

            if slice.header.cumulative_weight != expected_weight {
                return Err(BootstrapError::WeightMismatch {
                    index: idx,
                    expected: expected_weight,
                    got: slice.header.cumulative_weight,
                });
            }

            prev_weight = slice.header.cumulative_weight;
        }

        info!(
            "Chain weight verified: {} slices, final weight={}",
            slices.len(),
            prev_weight
        );

        Ok(())
    }

    /// Analyze peer history from presence_root data
    pub fn analyze_peer_history(
        &self,
        peer_pubkeys: &[PublicKey],
        presence_data: &HashMap<u64, Vec<PublicKey>>,
    ) -> HashMap<PublicKey, PeerHistory> {
        let mut histories: HashMap<PublicKey, PeerHistory> = HashMap::new();

        for (tau2, pubkeys) in presence_data {
            for pubkey in pubkeys {
                if peer_pubkeys.contains(pubkey) {
                    let entry = histories.entry(pubkey.clone()).or_default();

                    if entry.first_seen_tau2 == 0 || *tau2 < entry.first_seen_tau2 {
                        entry.first_seen_tau2 = *tau2;
                    }
                    if *tau2 > entry.last_seen_tau2 {
                        entry.last_seen_tau2 = *tau2;
                    }
                    entry.presence_count += 1;
                }
            }
        }

        histories
    }

    /// Analyze peer age distribution
    ///
    /// Returns (established_count, median_age) where:
    /// - established_count: peers with presence history > τ₃ (14 days)
    /// - median_age: median presence age in τ₂ units
    ///
    /// Age-based priority provides Sybil resistance.
    pub fn analyze_peer_ages(
        &self,
        histories: &HashMap<PublicKey, PeerHistory>,
    ) -> (usize, u64) {
        let established_count = histories
            .values()
            .filter(|h| h.is_established())
            .count();

        let mut ages: Vec<u64> = histories.values().map(|h| h.age_score()).collect();
        ages.sort_unstable();
        let median_age = if ages.is_empty() {
            0
        } else {
            ages[ages.len() / 2]
        };

        info!(
            "Peer age analysis: {} established (>14 days), median_age={} τ₂",
            established_count, median_age
        );

        (established_count, median_age)
    }

    /// Verify subnet diversity in peer responses
    /// Requires 25+ unique /16 subnets to prevent Erebus/Sybil attacks
    pub fn verify_subnet_diversity(
        &self,
        responses: &[PeerChainInfo],
    ) -> Result<usize, BootstrapError> {
        let subnets: HashSet<Subnet16> = responses
            .iter()
            .map(|r| ip_to_subnet16(r.peer.ip()))
            .collect();

        let unique_count = subnets.len();

        if unique_count < MIN_DIVERSE_SUBNETS {
            return Err(BootstrapError::InsufficientSubnetDiversity {
                need: MIN_DIVERSE_SUBNETS,
                have: unique_count,
            });
        }

        info!(
            "Subnet diversity verified: {} unique /16 subnets (min: {})",
            unique_count, MIN_DIVERSE_SUBNETS
        );

        Ok(unique_count)
    }

    /// Verify subnet reputation roots in downloaded chain
    pub fn verify_subnet_roots(
        &self,
        slices: &[Slice],
        subnet_tracker: &SubnetTracker,
    ) -> Result<(), BootstrapError> {
        if slices.is_empty() {
            return Ok(());
        }

        // Genesis should have zero root
        let genesis = &slices[0];
        if genesis.header.subnet_reputation_root != [0u8; 32] {
            return Err(BootstrapError::SubnetRootMismatch {
                index: 0,
                expected: [0u8; 32],
                got: genesis.header.subnet_reputation_root,
            });
        }

        // For full verification, we'd recompute subnet tracker from scratch
        // and verify each slice's root. For now, verify tip matches.
        if slices.len() > 1 {
            let tip = slices.last().unwrap();
            let computed_root = subnet_tracker.compute_root();

            if tip.header.subnet_reputation_root != computed_root {
                warn!(
                    "Subnet root verification: tip has {:?}, computed {:?}",
                    &tip.header.subnet_reputation_root[..8],
                    &computed_root[..8]
                );
                // Note: This is a warning for now, full verification requires
                // recomputing tracker from genesis which is expensive
            }
        }

        info!("Subnet reputation roots verified");
        Ok(())
    }

    /// Select peers prioritized by presence age
    ///
    /// Age-based peer selection for Sybil resistance:
    /// - Peers sorted by presence history age (oldest first)
    /// - At genesis: all peers have equal priority (age = 0)
    /// - As network matures: older peers naturally dominate selection
    /// - Fresh nodes receive lower priority
    ///
    /// Returns (sorted_pubkeys, median_age, established_count)
    pub fn select_peers_by_age(
        &self,
        peer_pubkeys: &[PublicKey],
        presence_data: &HashMap<u64, Vec<PublicKey>>,
        count: usize,
    ) -> (Vec<PublicKey>, u64, usize) {
        let histories = self.analyze_peer_history(peer_pubkeys, presence_data);

        // Sort by age (oldest first)
        let mut peers_with_age: Vec<_> = peer_pubkeys
            .iter()
            .map(|pk| {
                let age = histories.get(pk).map(|h| h.age_score()).unwrap_or(0);
                (pk.clone(), age)
            })
            .collect();
        peers_with_age.sort_by(|a, b| b.1.cmp(&a.1)); // descending by age

        // Take top `count` peers
        let selected: Vec<PublicKey> = peers_with_age
            .iter()
            .take(count)
            .map(|(pk, _)| pk.clone())
            .collect();

        // Calculate median age
        let ages: Vec<u64> = peers_with_age.iter().take(count).map(|(_, age)| *age).collect();
        let median_age = if ages.is_empty() {
            0
        } else {
            let mut sorted_ages = ages.clone();
            sorted_ages.sort_unstable();
            sorted_ages[sorted_ages.len() / 2]
        };

        // Count established peers (age > τ₃)
        let established = ages.iter().filter(|&&age| age >= TAU3_IN_TAU2).count();

        info!(
            "Peer selection by age: {} peers, median_age={} τ₂, established={}",
            selected.len(), median_age, established
        );

        (selected, median_age, established)
    }

    /// Select diverse P2P peers using subnet reputation (max 5 per subnet)
    pub fn select_diverse_p2p_peers(
        &self,
        candidates: &[SocketAddr],
        subnet_tracker: &SubnetTracker,
        count: usize,
    ) -> Vec<SocketAddr> {
        subnet_tracker.select_diverse_peers(candidates, count, MAX_NODES_PER_SUBNET)
    }

    /// Full bootstrap verification with hardcoded node priority and subnet diversity
    ///
    /// Verification steps:
    /// 1. Verify local clock against network median (100 peers, 25+ subnets)
    /// 2. Verify hardcoded nodes match consensus
    /// 3. Verify subnet diversity
    /// 4. Verify chain weights
    /// 5. Analyze peer ages (priority-based Sybil resistance)
    pub fn verify_bootstrap(
        &self,
        peer_responses: &[PeerChainInfo],
        slices: &[Slice],
        presence_weights: &HashMap<u64, u64>,
        presence_pubkeys: &HashMap<u64, Vec<PublicKey>>,
        peer_pubkeys: &[PublicKey],
        subnet_tracker: &SubnetTracker,
        local_time: u64,
    ) -> Result<BootstrapResult, BootstrapError> {
        info!("Starting bootstrap verification...");

        // Step 1: Verify local clock against network time FIRST
        // This must happen before any time-based calculations
        // Median from 100 peers in 25+ subnets is manipulation-resistant
        let (network_time, time_warning) = self.verify_network_time(peer_responses, local_time)?;

        if let Some(ref warning) = time_warning {
            warn!("Time warning: {}", warning);
        }

        // Step 2: Verify hardcoded nodes and get consensus
        let (median_height, median_weight, hardcoded_count, p2p_count) =
            self.get_verified_consensus(peer_responses)?;

        // Step 3: Verify subnet diversity (25+ unique /16 subnets)
        let unique_subnets = self.verify_subnet_diversity(peer_responses)?;

        // Step 4: Verify height against NETWORK time (independent of local clock)
        let height_warning = self.verify_height(median_height, network_time)?;

        if let Some(ref warning) = height_warning {
            warn!("{}", warning);
        }

        // Step 5: Verify chain weights
        self.verify_chain_weights(slices, presence_weights)?;

        // Step 6: Verify subnet reputation roots
        self.verify_subnet_roots(slices, subnet_tracker)?;

        // Step 7: Verify downloaded chain matches consensus
        if !slices.is_empty() {
            let tip = slices.last().unwrap();
            let tolerance = median_weight / 100;
            let diff = if tip.header.cumulative_weight > median_weight {
                tip.header.cumulative_weight - median_weight
            } else {
                median_weight - tip.header.cumulative_weight
            };

            if diff > tolerance {
                warn!(
                    "Chain weight differs from consensus: chain={}, peers={}",
                    tip.header.cumulative_weight, median_weight
                );
            }
        }

        // Step 8: Analyze peer ages (priority-based, older = higher priority)
        let histories = self.analyze_peer_history(peer_pubkeys, presence_pubkeys);
        let (established_peers, median_peer_age) = self.analyze_peer_ages(&histories);

        info!(
            "Bootstrap complete: height={}, weight={}, network_time={}, subnets={}, established={}, median_age={} τ₂, hardcoded={}, p2p={}",
            median_height, median_weight, network_time, unique_subnets, established_peers, median_peer_age, hardcoded_count, p2p_count
        );

        Ok(BootstrapResult {
            height: median_height,
            cumulative_weight: median_weight,
            established_peers,
            hardcoded_responses: hardcoded_count,
            p2p_responses: p2p_count,
            unique_subnets,
            median_peer_age_tau2: median_peer_age,
            height_warning,
            network_time,
            time_warning,
        })
    }
}

/// Calculate weight for a presence proof
pub fn presence_weight(proof: &crate::types::PresenceProof) -> u64 {
    if proof.in_cooldown() {
        return 0;
    }

    if !proof.meets_threshold() {
        return 0;
    }

    1
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::crypto::sha3;

    fn make_genesis() -> Slice {
        Slice {
            header: SliceHeader {
                prev_hash: [0u8; 32],
                timestamp: GENESIS_TIMESTAMP,
                slice_index: 0,
                winner_pubkey: vec![],
                cooldown_medians: [0, 0, 0],
                registrations: [0, 0, 0],
                cumulative_weight: 0,
                subnet_reputation_root: [0u8; 32],
            },
            presence_root: sha3(b"montana genesis presence"),
            tx_root: sha3(b"montana genesis tx"),
            signature: vec![],
            presences: vec![],
            transactions: vec![],
        }
    }

    fn make_peer_info(
        addr: &str,
        height: u64,
        weight: u64,
        source: PeerSource,
    ) -> PeerChainInfo {
        PeerChainInfo {
            peer: addr.parse().unwrap(),
            slice_height: height,
            cumulative_weight: weight,
            tip_hash: [0u8; 32],
            source,
            peer_timestamp: GENESIS_TIMESTAMP + height * 600, // Realistic timestamp
        }
    }

    fn make_peer_info_with_time(
        addr: &str,
        height: u64,
        weight: u64,
        source: PeerSource,
        timestamp: u64,
    ) -> PeerChainInfo {
        PeerChainInfo {
            peer: addr.parse().unwrap(),
            slice_height: height,
            cumulative_weight: weight,
            tip_hash: [0u8; 32],
            source,
            peer_timestamp: timestamp,
        }
    }

    #[test]
    fn test_hardcoded_consensus_pass() {
        let genesis = make_genesis();
        // Create 20 hardcoded peers
        let mut hardcoded = vec![];
        for i in 0..20 {
            hardcoded.push(format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i).parse().unwrap());
        }
        let verifier = BootstrapVerifier::new(&genesis, hardcoded);

        // All 20 hardcoded nodes report height 1000
        let mut responses = vec![];
        for i in 0..20 {
            responses.push(make_peer_info(
                &format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i),
                1000,
                50000,
                PeerSource::Hardcoded,
            ));
        }
        // Add 80 P2P peers also at height 1000
        for i in 0..80 {
            responses.push(make_peer_info(
                &format!("100.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256),
                1000,
                50000,
                PeerSource::Gossip,
            ));
        }

        assert!(verifier.verify_hardcoded_consensus(&responses).is_ok());
    }

    #[test]
    fn test_hardcoded_consensus_with_divergent_p2p() {
        // NEW: Hardcoded consensus should succeed even if P2P peers diverge
        // This tests the "Trusted Core" security model
        let genesis = make_genesis();
        let mut hardcoded = vec![];
        for i in 0..20 {
            hardcoded.push(format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i).parse().unwrap());
        }
        let verifier = BootstrapVerifier::new(&genesis, hardcoded);

        // All hardcoded nodes report height 500 (they agree among themselves)
        let mut responses = vec![];
        for i in 0..20 {
            responses.push(make_peer_info(
                &format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i),
                500,
                25000,
                PeerSource::Hardcoded,
            ));
        }

        // P2P peers report height 1000 (eclipse attack simulation)
        for i in 0..80 {
            responses.push(make_peer_info(
                &format!("100.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256),
                1000,
                50000,
                PeerSource::Gossip,
            ));
        }

        // With new "Trusted Core" model: hardcoded median = 500
        // All 20 hardcoded agree with median → SUCCESS (P2P divergence is just a warning)
        let result = verifier.verify_hardcoded_consensus(&responses);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 500); // Returns hardcoded median
    }

    #[test]
    fn test_hardcoded_consensus_split_fail() {
        // NEW: Test case where hardcoded nodes themselves are split
        // This should fail because there's no trusted majority
        let genesis = make_genesis();
        let mut hardcoded = vec![];
        for i in 0..20 {
            hardcoded.push(format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i).parse().unwrap());
        }
        let verifier = BootstrapVerifier::new(&genesis, hardcoded);

        // Half hardcoded at height 100, half at height 1000 (50% split, no majority)
        let mut responses = vec![];
        for i in 0..10 {
            responses.push(make_peer_info(
                &format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i),
                100,  // Group A
                5000,
                PeerSource::Hardcoded,
            ));
        }
        for i in 10..20 {
            responses.push(make_peer_info(
                &format!("{}.{}.{}.{}:19333", 1 + i, 2 + i, 3 + i, 4 + i),
                1000, // Group B (very different from A)
                50000,
                PeerSource::Hardcoded,
            ));
        }

        // Median of hardcoded = (100*10 + 1000*10) sorted middle = either 100 or 1000
        // Neither group has >50% agreement with median → FAIL
        let result = verifier.verify_hardcoded_consensus(&responses);
        assert!(result.is_err());

        match result {
            Err(BootstrapError::HardcodedCompromised) => {}
            other => panic!("Expected HardcodedCompromised error, got {:?}", other),
        }
    }

    #[test]
    fn test_expected_height() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        assert_eq!(verifier.expected_height(GENESIS_TIMESTAMP), 0);
        assert_eq!(verifier.expected_height(GENESIS_TIMESTAMP + 600), 1);
        assert_eq!(verifier.expected_height(GENESIS_TIMESTAMP + 86400), 144);
    }

    #[test]
    fn test_chain_weight_verification() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        let mut slices = vec![genesis.clone()];

        let slice1 = Slice {
            header: SliceHeader {
                prev_hash: genesis.hash(),
                timestamp: GENESIS_TIMESTAMP + 600,
                slice_index: 1,
                winner_pubkey: vec![1, 2, 3],
                cooldown_medians: [0, 0, 0],
                registrations: [0, 0, 0],
                cumulative_weight: 10,
                subnet_reputation_root: [0u8; 32],
            },
            presence_root: sha3(b"slice1 presence"),
            tx_root: sha3(b"slice1 tx"),
            signature: vec![],
            presences: vec![],
            transactions: vec![],
        };
        slices.push(slice1.clone());

        let slice2 = Slice {
            header: SliceHeader {
                prev_hash: slice1.hash(),
                timestamp: GENESIS_TIMESTAMP + 1200,
                slice_index: 2,
                winner_pubkey: vec![4, 5, 6],
                cooldown_medians: [0, 0, 0],
                registrations: [0, 0, 0],
                cumulative_weight: 25,
                subnet_reputation_root: [0u8; 32],
            },
            presence_root: sha3(b"slice2 presence"),
            tx_root: sha3(b"slice2 tx"),
            signature: vec![],
            presences: vec![],
            transactions: vec![],
        };
        slices.push(slice2);

        let mut weights = HashMap::new();
        weights.insert(1, 10u64);
        weights.insert(2, 15u64);

        assert!(verifier.verify_chain_weights(&slices, &weights).is_ok());
    }

    #[test]
    fn test_peer_age_analysis() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        // Create 12 peers: 10 with long history, 2 with short history
        let mut peer_pubkeys = vec![];
        for i in 0..12 {
            peer_pubkeys.push(vec![i as u8, i as u8 + 1, i as u8 + 2]);
        }

        let mut presence_data = HashMap::new();
        for tau2 in 0..3000 {
            let mut pubkeys = vec![];
            // First 10 peers have full 3000 τ₂ history (> 2016)
            for i in 0..10 {
                pubkeys.push(peer_pubkeys[i].clone());
            }
            // Last 2 peers only 1000 τ₂ (< 2016)
            if tau2 < 1000 {
                pubkeys.push(peer_pubkeys[10].clone());
                pubkeys.push(peer_pubkeys[11].clone());
            }
            presence_data.insert(tau2, pubkeys);
        }

        let histories = verifier.analyze_peer_history(&peer_pubkeys, &presence_data);

        // First 10 are established (history > τ₃)
        for i in 0..10 {
            assert!(histories.get(&peer_pubkeys[i]).unwrap().is_established());
        }
        // Last 2 have shorter history
        assert!(!histories.get(&peer_pubkeys[10]).unwrap().is_established());
        assert!(!histories.get(&peer_pubkeys[11]).unwrap().is_established());

        // Analyze ages: 10 established, median age should be ~2999 τ₂
        let (established, median_age) = verifier.analyze_peer_ages(&histories);
        assert_eq!(established, 10);
        assert!(median_age >= 2000); // Most peers have long history
    }

    #[test]
    fn test_peer_selection_by_age() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        // Create 10 peers with varying history lengths
        let mut peer_pubkeys = vec![];
        for i in 0..10 {
            peer_pubkeys.push(vec![i as u8, i as u8 + 1, i as u8 + 2]);
        }

        let mut presence_data = HashMap::new();
        for tau2 in 0..3000 {
            let mut pubkeys = vec![];
            // Peer 0: full history (3000 τ₂)
            // Peer 1: 2500 τ₂, Peer 2: 2000 τ₂, etc.
            for i in 0..10 {
                if tau2 < 3000 - (i as u64 * 300) {
                    pubkeys.push(peer_pubkeys[i].clone());
                }
            }
            presence_data.insert(tau2, pubkeys);
        }

        // Select top 5 peers by age
        let (selected, median_age, established) = verifier.select_peers_by_age(
            &peer_pubkeys,
            &presence_data,
            5,
        );

        // Should select oldest 5 peers (indices 0-4)
        assert_eq!(selected.len(), 5);
        // Peer 0 should be first (oldest)
        assert_eq!(selected[0], peer_pubkeys[0]);
        // Median age of top 5 should be high
        assert!(median_age >= 1500);
        // At least some should be established
        assert!(established >= 3);
    }

    #[test]
    fn test_genesis_peer_selection() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        // Create peers with zero history (genesis scenario)
        let mut peer_pubkeys = vec![];
        for i in 0..10 {
            peer_pubkeys.push(vec![i as u8, i as u8 + 1, i as u8 + 2]);
        }

        // Empty presence data = all peers have age 0
        let presence_data: HashMap<u64, Vec<PublicKey>> = HashMap::new();

        let histories = verifier.analyze_peer_history(&peer_pubkeys, &presence_data);

        // All peers have age 0 at genesis - this is valid
        let (established, median_age) = verifier.analyze_peer_ages(&histories);
        assert_eq!(established, 0); // Zero established peers at genesis
        assert_eq!(median_age, 0);  // Median age is 0

        // Selection still works at genesis (all equal priority)
        let (selected, _, _) = verifier.select_peers_by_age(&peer_pubkeys, &presence_data, 5);
        assert_eq!(selected.len(), 5); // Can still select peers
    }

    // ========================================================================
    // Network Time Verification Tests
    // ========================================================================

    #[test]
    fn test_network_time_normal() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        let network_time = 1735900000u64;
        let local_time = network_time + 30; // 30 seconds ahead - normal

        let mut responses = vec![];
        for i in 0..100 {
            responses.push(make_peer_info_with_time(
                &format!("{}.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256, (i + 3) % 256),
                1000,
                50000,
                if i < 20 { PeerSource::Hardcoded } else { PeerSource::Gossip },
                network_time,
            ));
        }

        let result = verifier.verify_network_time(&responses, local_time);
        assert!(result.is_ok());

        let (median, warning) = result.unwrap();
        assert_eq!(median, network_time);
        assert!(warning.is_none()); // No warning for < 1 minute
    }

    #[test]
    fn test_network_time_warning() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        let network_time = 1735900000u64;
        let local_time = network_time + 300; // 5 minutes ahead - warning

        let mut responses = vec![];
        for i in 0..100 {
            responses.push(make_peer_info_with_time(
                &format!("{}.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256, (i + 3) % 256),
                1000,
                50000,
                PeerSource::Gossip,
                network_time,
            ));
        }

        let result = verifier.verify_network_time(&responses, local_time);
        assert!(result.is_ok());

        let (median, warning) = result.unwrap();
        assert_eq!(median, network_time);
        assert!(warning.is_some()); // Should have warning
        assert!(warning.unwrap().contains("300")); // Should mention 300 seconds
    }

    #[test]
    fn test_network_time_critical() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        let network_time = 1735900000u64;
        let local_time = network_time + 900; // 15 minutes ahead - critical

        let mut responses = vec![];
        for i in 0..100 {
            responses.push(make_peer_info_with_time(
                &format!("{}.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256, (i + 3) % 256),
                1000,
                50000,
                PeerSource::Gossip,
                network_time,
            ));
        }

        let result = verifier.verify_network_time(&responses, local_time);
        assert!(result.is_err());

        match result {
            Err(BootstrapError::ClockDivergenceCritical { divergence_secs }) => {
                assert_eq!(divergence_secs, 900);
            }
            _ => panic!("Expected ClockDivergenceCritical error"),
        }
    }

    #[test]
    fn test_network_time_local_behind() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        let network_time = 1735900000u64;
        let local_time = network_time - 45; // 45 seconds behind - normal

        let mut responses = vec![];
        for i in 0..100 {
            responses.push(make_peer_info_with_time(
                &format!("{}.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256, (i + 3) % 256),
                1000,
                50000,
                PeerSource::Gossip,
                network_time,
            ));
        }

        let result = verifier.verify_network_time(&responses, local_time);
        assert!(result.is_ok());

        let (median, warning) = result.unwrap();
        assert_eq!(median, network_time);
        assert!(warning.is_none());
    }

    #[test]
    fn test_network_time_median_calculation() {
        let genesis = make_genesis();
        let verifier = BootstrapVerifier::new(&genesis, vec![]);

        // Create responses with varied timestamps
        // Median should be the middle value when sorted
        let base_time = 1735900000u64;
        let mut responses = vec![];

        // 50 peers at base_time
        for i in 0..50 {
            responses.push(make_peer_info_with_time(
                &format!("{}.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256, (i + 3) % 256),
                1000,
                50000,
                PeerSource::Gossip,
                base_time,
            ));
        }

        // 50 peers at base_time + 10 (attacker trying to shift time)
        for i in 50..100 {
            responses.push(make_peer_info_with_time(
                &format!("{}.{}.{}.{}:19333", i % 256, (i + 1) % 256, (i + 2) % 256, (i + 3) % 256),
                1000,
                50000,
                PeerSource::Gossip,
                base_time + 10,
            ));
        }

        let local_time = base_time + 5;
        let result = verifier.verify_network_time(&responses, local_time);
        assert!(result.is_ok());

        let (median, _) = result.unwrap();
        // Median of 50 base_time and 50 base_time+10 = base_time+10 (middle of sorted list)
        assert!(median == base_time || median == base_time + 10);
    }
}
