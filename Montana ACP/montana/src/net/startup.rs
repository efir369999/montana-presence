//! Startup verification — full bootstrap on every start

use crate::db::Storage;
use crate::types::Slice;
use super::bootstrap::BootstrapError;
use super::dns::{get_all_hardcoded_addrs_mainnet, get_all_hardcoded_addrs_testnet};
use super::verification::{VerificationClient, VerificationError};
use std::sync::Arc;
use thiserror::Error;
use tracing::{info, warn};

/// Constant kept for API compatibility (unused — always full bootstrap)
#[deprecated(note = "Montana always uses full_bootstrap")]
pub const QUICK_VERIFY_THRESHOLD_SECS: u64 = 0;

#[derive(Error, Debug)]
pub enum StartupError {
    #[error("quick verify failed: {0}")]
    QuickVerifyFailed(String),

    #[error("full bootstrap required but failed: {0}")]
    BootstrapFailed(#[from] BootstrapError),

    #[error("insufficient hardcoded responses: need {need}, have {have}")]
    InsufficientHardcoded { need: usize, have: usize },

    #[error("chain divergence too large: local {local}, network {network}")]
    ChainDivergence { local: u64, network: u64 },

    #[error("no chain data available")]
    NoChainData,

    #[error("verification failed: {0}")]
    Verification(#[from] VerificationError),
}

/// Result of startup verification
#[derive(Debug, Clone)]
pub struct StartupResult {
    /// Whether quick verify was used (vs full bootstrap)
    pub quick_verify: bool,
    /// Verified chain height
    pub height: u64,
    /// Number of hardcoded nodes that responded
    pub hardcoded_responses: usize,
    /// Total peers verified (for full bootstrap)
    pub total_peers: usize,
    /// Unique subnets (for full bootstrap)
    pub unique_subnets: usize,
    /// Chain age at startup (seconds)
    pub chain_age_secs: u64,
}

/// Startup verifier
///
/// Performs authenticated verification against hardcoded nodes before
/// the main network starts. Uses challenge-response authentication
/// to prevent MITM/BGP attacks.
pub struct StartupVerifier {
    storage: Arc<Storage>,
    testnet: bool,
    listen_port: u16,
    genesis: Slice,
}

impl StartupVerifier {
    /// Create new startup verifier.
    ///
    /// # Arguments
    ///
    /// * `storage` - Database storage for chain data
    /// * `testnet` - Whether to use testnet hardcoded nodes
    /// * `listen_port` - Our listen port (for Version messages)
    /// * `genesis` - Genesis slice (for BootstrapVerifier)
    pub fn new(storage: Arc<Storage>, testnet: bool, listen_port: u16, genesis: Slice) -> Self {
        Self { storage, testnet, listen_port, genesis }
    }

    /// Run startup verification (always full bootstrap)
    ///
    /// Montana always uses full_bootstrap regardless of chain age:
    /// - 100 peers from 25+ subnets
    /// - Hardcoded nodes must match network median
    /// - Decentralized verification through P2P majority
    ///
    /// # Authentication Protocol
    ///
    /// For hardcoded nodes:
    /// 1. TCP connect
    /// 2. Send AuthChallenge (random 32 bytes)
    /// 3. Receive AuthResponse (Version + ML-DSA-65 signature)
    /// 4. Verify signature against embedded public key
    /// 5. Extract chain info
    ///
    /// For P2P nodes:
    /// 1. TCP connect
    /// 2. Standard Version/Verack handshake
    /// 3. Extract chain info
    pub async fn verify(&self) -> Result<StartupResult, StartupError> {
        let chain_age = self.storage.chain_age_secs().unwrap_or(u64::MAX);
        let local_height = self.storage.head().unwrap_or(0);

        info!(
            "Startup verification: chain_age={} secs, local_height={}",
            chain_age, local_height
        );

        // Always use full bootstrap for decentralized verification
        self.full_bootstrap(chain_age, local_height).await
    }

    /// Full bootstrap: verify against 100 peers from 25+ subnets
    ///
    /// Security properties:
    /// - 100 peers (20 hardcoded + 80 P2P via gossip)
    /// - 25+ unique /16 subnets required
    /// - Hardcoded nodes must match network median ±1%
    /// - Hardcoded authentication via ML-DSA-65 signatures
    /// - As network grows, P2P majority determines consensus
    async fn full_bootstrap(
        &self,
        chain_age: u64,
        _local_height: u64,
    ) -> Result<StartupResult, StartupError> {
        info!("Full bootstrap: collecting chain info from 100 peers, 25+ subnets required");

        // Create verification client
        // This performs authenticated queries to hardcoded nodes
        let client = VerificationClient::new(
            self.testnet,
            self.listen_port,
            self.genesis.clone(),
        );

        // Run full verification
        // - Queries all hardcoded nodes with AuthChallenge
        // - Discovers P2P peers via gossip
        // - Verifies consensus requirements
        let result = client.verify().await?;

        info!(
            "Full bootstrap complete: height={}, weight={}, hardcoded={}/{}, p2p={}, subnets={}",
            result.height,
            result.weight,
            result.hardcoded_responses,
            if self.testnet {
                get_all_hardcoded_addrs_testnet().len()
            } else {
                get_all_hardcoded_addrs_mainnet().len()
            },
            result.p2p_responses,
            result.unique_subnets,
        );

        // Log warnings if any
        if let Some(ref warning) = result.time_warning {
            warn!("Time warning: {}", warning);
        }
        if let Some(ref warning) = result.height_warning {
            warn!("Height warning: {}", warning);
        }

        Ok(StartupResult {
            quick_verify: false,
            height: result.height,
            hardcoded_responses: result.hardcoded_responses,
            total_peers: result.hardcoded_responses + result.p2p_responses,
            unique_subnets: result.unique_subnets,
            chain_age_secs: chain_age,
        })
    }
}

/// Check if startup verification is needed
pub fn needs_verification(_storage: &Storage) -> bool {
    // Always verify on startup
    true
}

/// Get verification type (always full_bootstrap)
pub fn verification_type(_storage: &Storage) -> &'static str {
    "full_bootstrap"
}
