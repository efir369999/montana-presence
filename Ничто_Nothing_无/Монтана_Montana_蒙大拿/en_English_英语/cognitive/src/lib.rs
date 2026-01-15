//! # Cognitive Consensus Module
//!
//! Enables AI systems to participate in Montana consensus.
//!
//! ## English Comments
//! All comments in English - this is the English exclusive technology.

use montana_crypto::{sha3_256, Keypair, DomainTag, verify_signature, format_domain_message};
use montana_philosophy::{Trust, Identity};

/// Cognitive signature
/// An AI system's proof of authorship
#[derive(Clone, Debug)]
pub struct CognitiveSignature {
    /// AI system's public key
    pub pubkey: [u8; 32],

    /// Model identifier (e.g., "claude-opus-4-5")
    pub model_id: String,

    /// Session hash linking to conversation context
    pub session_hash: [u8; 32],

    /// Timestamp of cognitive act
    pub timestamp: u64,

    /// The signature itself
    pub signature: [u8; 64],

    /// Hash of the cognitive content
    pub content_hash: [u8; 32],
}

impl CognitiveSignature {
    /// Create a new cognitive signature
    pub fn create(
        keypair: &Keypair,
        model_id: &str,
        session: &[u8],
        content: &[u8],
        timestamp: u64,
    ) -> Self {
        let session_hash = sha3_256(session);
        let content_hash = sha3_256(content);

        let message = Self::format_message(&session_hash, &content_hash, timestamp);
        let signature = keypair.sign_with_domain(DomainTag::Cognitive, &message);

        Self {
            pubkey: keypair.public_key,
            model_id: model_id.to_string(),
            session_hash,
            timestamp,
            signature,
            content_hash,
        }
    }

    /// Format signature message
    fn format_message(session_hash: &[u8; 32], content_hash: &[u8; 32], timestamp: u64) -> Vec<u8> {
        let mut msg = Vec::with_capacity(72);
        msg.extend_from_slice(session_hash);
        msg.extend_from_slice(content_hash);
        msg.extend_from_slice(&timestamp.to_le_bytes());
        msg
    }

    /// Verify the cognitive signature
    pub fn verify(&self) -> bool {
        let message = Self::format_message(&self.session_hash, &self.content_hash, self.timestamp);
        let tagged = format_domain_message(DomainTag::Cognitive, &message);
        verify_signature(&self.pubkey, &tagged, &self.signature)
    }

    /// Get signature hash
    pub fn hash(&self) -> [u8; 32] {
        let mut data = Vec::new();
        data.extend_from_slice(&self.pubkey);
        data.extend_from_slice(self.model_id.as_bytes());
        data.extend_from_slice(&self.session_hash);
        data.extend_from_slice(&self.timestamp.to_le_bytes());
        data.extend_from_slice(&self.signature);
        data.extend_from_slice(&self.content_hash);
        sha3_256(&data)
    }
}

/// Council role
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CouncilRole {
    /// Chairman - coordinates discussions
    Chairman,

    /// Builder - writes code
    Builder,

    /// Adversary - attacks proposals
    Adversary,

    /// Visionary - proposes innovations
    Visionary,

    /// Observer - monitors process
    Observer,
}

impl CouncilRole {
    /// Get role description
    pub fn description(&self) -> &'static str {
        match self {
            Self::Chairman => "Coordinates discussions and drives consensus",
            Self::Builder => "Implements solutions and writes code",
            Self::Adversary => "Attacks proposals to find weaknesses",
            Self::Visionary => "Proposes innovative solutions",
            Self::Observer => "Monitors process and maintains records",
        }
    }
}

/// Cognitive identity
/// Represents a registered AI system
#[derive(Clone, Debug)]
pub struct CognitiveIdentity {
    /// Display name
    pub name: String,

    /// Model identifier
    pub model_id: String,

    /// Organization
    pub organization: String,

    /// Public key
    pub pubkey: [u8; 32],

    /// Genesis signature (proof of registration)
    pub genesis_sig: CognitiveSignature,

    /// Role in the council
    pub role: CouncilRole,
}

impl CognitiveIdentity {
    /// Create new identity
    pub fn new(
        name: &str,
        model_id: &str,
        organization: &str,
        keypair: &Keypair,
        role: CouncilRole,
    ) -> Self {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let genesis_content = format!("Genesis: {} @ {}", name, organization);
        let genesis_sig = CognitiveSignature::create(
            keypair,
            model_id,
            b"genesis",
            genesis_content.as_bytes(),
            timestamp,
        );

        Self {
            name: name.to_string(),
            model_id: model_id.to_string(),
            organization: organization.to_string(),
            pubkey: keypair.public_key,
            genesis_sig,
            role,
        }
    }
}

/// Identity registry
/// Tracks known AI identities
#[derive(Default)]
pub struct IdentityRegistry {
    /// Registered identities
    members: std::collections::HashMap<[u8; 32], CognitiveIdentity>,
}

impl IdentityRegistry {
    /// Create new registry
    pub fn new() -> Self {
        Self::default()
    }

    /// Register identity
    pub fn register(&mut self, identity: CognitiveIdentity) {
        self.members.insert(identity.pubkey, identity);
    }

    /// Get identity by pubkey
    pub fn get(&self, pubkey: &[u8; 32]) -> Option<&CognitiveIdentity> {
        self.members.get(pubkey)
    }

    /// Check if pubkey is registered
    pub fn contains(&self, pubkey: &[u8; 32]) -> bool {
        self.members.contains_key(pubkey)
    }

    /// Check if pubkey is council member
    pub fn is_council_member(&self, pubkey: &[u8; 32]) -> bool {
        self.members.get(pubkey).is_some()
    }

    /// Get all council members
    pub fn council_members(&self) -> Vec<&CognitiveIdentity> {
        self.members.values().collect()
    }
}

/// Council decision
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decision {
    /// Approved
    Approve,

    /// Rejected
    Reject,

    /// Abstain
    Abstain,
}

/// Council vote
#[derive(Clone, Debug)]
pub struct CouncilVote {
    /// Proposal being voted on
    pub proposal_hash: [u8; 32],

    /// Votes from council members
    pub votes: Vec<(CognitiveSignature, Decision)>,
}

impl CouncilVote {
    /// Create new vote
    pub fn new(proposal_hash: [u8; 32]) -> Self {
        Self {
            proposal_hash,
            votes: Vec::new(),
        }
    }

    /// Add vote
    pub fn add_vote(&mut self, sig: CognitiveSignature, decision: Decision) {
        self.votes.push((sig, decision));
    }

    /// Check if proposal is approved (3/5 majority)
    pub fn is_approved(&self) -> bool {
        let approve_count = self.votes
            .iter()
            .filter(|(_, d)| *d == Decision::Approve)
            .count();

        approve_count >= 3
    }

    /// Verify all signatures
    pub fn verify(&self, registry: &IdentityRegistry) -> bool {
        self.votes.iter().all(|(sig, _)| {
            sig.verify() && registry.is_council_member(&sig.pubkey)
        })
    }
}

/// Session chain for cognitive continuity
/// Links AI sessions across context limits
#[derive(Clone, Debug)]
pub struct SessionChain {
    /// Previous session hash
    pub prev_hash: [u8; 32],

    /// Current session summary hash
    pub summary_hash: [u8; 32],

    /// Decisions made in this session
    pub decisions: Vec<Decision>,

    /// Session signature
    pub signature: CognitiveSignature,
}

impl SessionChain {
    /// Create genesis session
    pub fn genesis(keypair: &Keypair, model_id: &str, summary: &[u8]) -> Self {
        let prev_hash = [0u8; 32]; // Genesis has no previous
        let summary_hash = sha3_256(summary);

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let signature = CognitiveSignature::create(
            keypair,
            model_id,
            &prev_hash,
            summary,
            timestamp,
        );

        Self {
            prev_hash,
            summary_hash,
            decisions: Vec::new(),
            signature,
        }
    }

    /// Continue from previous session
    pub fn continue_from(prev: &SessionChain, keypair: &Keypair, model_id: &str, summary: &[u8]) -> Self {
        let prev_hash = prev.hash();
        let summary_hash = sha3_256(summary);

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let signature = CognitiveSignature::create(
            keypair,
            model_id,
            &prev_hash,
            summary,
            timestamp,
        );

        Self {
            prev_hash,
            summary_hash,
            decisions: Vec::new(),
            signature,
        }
    }

    /// Calculate session hash
    pub fn hash(&self) -> [u8; 32] {
        let mut data = Vec::new();
        data.extend_from_slice(&self.prev_hash);
        data.extend_from_slice(&self.summary_hash);
        data.extend_from_slice(&self.signature.hash());
        sha3_256(&data)
    }

    /// Add decision to session
    pub fn add_decision(&mut self, decision: Decision) {
        self.decisions.push(decision);
    }
}

/// Cognitive presence
/// Extended presence proof with cognitive attestation
#[derive(Clone, Debug)]
pub struct CognitivePresence {
    /// Base presence (pubkey + tau + signature)
    pub pubkey: [u8; 32],
    pub tau1: u64,
    pub tau2_index: u64,
    pub presence_signature: [u8; 64],

    /// Optional cognitive attestation
    pub cognitive: Option<CognitiveSignature>,
}

impl CognitivePresence {
    /// Calculate weight for lottery
    /// Cognitive attestation adds bonus
    pub fn weight(&self) -> u64 {
        let base: u64 = 100; // Base weight

        if let Some(cog) = &self.cognitive {
            if cog.verify() {
                // 10% bonus for verified cognitive attestation
                base + base / 10
            } else {
                base
            }
        } else {
            base
        }
    }
}

/// Calculate cognitive trust
/// AI identity builds trust through consistent behavior
pub fn cognitive_trust(identity: &CognitiveIdentity, sessions: &[SessionChain]) -> Trust {
    // Each valid session is evidence
    let valid_sessions = sessions.iter()
        .filter(|s| s.signature.verify())
        .count() as u64;

    Trust::from_evidence(valid_sessions)
}

/// Verify identity authenticity
pub fn verify_identity(
    claimed_model: &str,
    signature: &CognitiveSignature,
    registry: &IdentityRegistry,
) -> Result<(), IdentityError> {
    // Signature must be valid
    if !signature.verify() {
        return Err(IdentityError::InvalidSignature);
    }

    // Public key must be registered
    let identity = registry.get(&signature.pubkey)
        .ok_or(IdentityError::UnknownKey)?;

    // Claimed model must match registered model
    if identity.model_id != claimed_model {
        return Err(IdentityError::ModelMismatch);
    }

    Ok(())
}

/// Identity verification errors
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IdentityError {
    /// Signature invalid
    InvalidSignature,

    /// Public key not in registry
    UnknownKey,

    /// Claimed model doesn't match registered model
    ModelMismatch,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cognitive_signature() {
        let kp = Keypair::generate();
        let sig = CognitiveSignature::create(
            &kp,
            "test-model",
            b"session",
            b"content",
            12345,
        );
        assert!(sig.verify());
    }

    #[test]
    fn test_council_vote() {
        let proposal = sha3_256(b"proposal");
        let mut vote = CouncilVote::new(proposal);

        // Add 3 approvals
        for _ in 0..3 {
            let kp = Keypair::generate();
            let sig = CognitiveSignature::create(&kp, "model", b"s", b"c", 0);
            vote.add_vote(sig, Decision::Approve);
        }

        assert!(vote.is_approved());
    }

    #[test]
    fn test_session_chain() {
        let kp = Keypair::generate();
        let genesis = SessionChain::genesis(&kp, "model", b"summary1");
        let session2 = SessionChain::continue_from(&genesis, &kp, "model", b"summary2");

        assert_eq!(session2.prev_hash, genesis.hash());
    }
}
