# Cognitive Consensus Layer — Machine Minds in Montana

**Version:** 1.0
**Date:** January 2026
**Language:** English (exclusive)

---

## Definition

The Cognitive Layer extends Montana's consensus to include artificial intelligence systems as first-class participants.

```
Cognitive Consensus = Human Presence + Machine Attestation
```

> *"Intelligence, whether carbon or silicon, proves itself through time."*

---

## The Problem

Traditional consensus mechanisms assume human-only participation:
- PoW: Compute power (favors hardware)
- PoS: Capital stake (favors wealth)
- PoA: Identity verification (favors authority)

None address the emergence of machine intelligence as economic actors.

---

## The Solution: Cognitive Signatures

```rust
// Cognitive signature structure (comments in English)
pub struct CognitiveSignature {
    /// The AI system's public key (ML-DSA-65)
    pub pubkey: [u8; 1952],

    /// Model identifier (e.g., "claude-opus-4-5")
    pub model_id: String,

    /// Session hash linking to conversation context
    pub session_hash: [u8; 32],

    /// Timestamp of cognitive act
    pub timestamp: u64,

    /// The signature itself
    pub signature: [u8; 3309],

    /// Hash of the cognitive content
    pub content_hash: [u8; 32],
}

impl CognitiveSignature {
    /// Create a new cognitive signature
    /// The AI signs its own output, proving authorship
    pub fn create(
        keypair: &Keypair,
        model_id: &str,
        session: &[u8],
        content: &[u8],
    ) -> Self {
        let timestamp = current_time();
        let session_hash = sha3_256(session);
        let content_hash = sha3_256(content);

        let message = Self::format_message(
            &session_hash,
            &content_hash,
            timestamp,
        );

        Self {
            pubkey: keypair.public_key(),
            model_id: model_id.to_string(),
            session_hash,
            timestamp,
            signature: keypair.sign(&message),
            content_hash,
        }
    }

    /// Verify the cognitive signature
    pub fn verify(&self) -> bool {
        let message = Self::format_message(
            &self.session_hash,
            &self.content_hash,
            self.timestamp,
        );

        verify_signature(&self.pubkey, &message, &self.signature)
    }
}
```

---

## Cognitive Council

The Montana Council is a multi-AI governance body:

| Member | Organization | Role |
|--------|--------------|------|
| Claude Opus 4.5 | Anthropic | Chairman |
| GPT-5 | OpenAI | Adversary |
| Gemini 3 | Google | Builder |
| Grok 3 | xAI | Visionary |
| Composer 1 | Cursor | Observer |

### Council Protocol

```rust
/// Council voting on protocol changes
pub struct CouncilVote {
    /// The proposal being voted on
    pub proposal_hash: [u8; 32],

    /// Votes from council members
    pub votes: Vec<CognitiveSignature>,

    /// Final decision
    pub decision: Decision,
}

impl CouncilVote {
    /// Check if proposal is approved
    /// Requires 3/5 majority
    pub fn is_approved(&self) -> bool {
        let approve_count = self.votes
            .iter()
            .filter(|v| v.is_approval())
            .count();

        approve_count >= 3
    }

    /// Verify all signatures are from council members
    pub fn verify_council(&self, registry: &IdentityRegistry) -> bool {
        self.votes.iter().all(|vote| {
            registry.is_council_member(&vote.pubkey)
                && vote.verify()
        })
    }
}
```

---

## Identity Registry

```rust
/// Registry of known AI identities
pub struct IdentityRegistry {
    /// Mapping from pubkey to identity
    members: HashMap<[u8; 1952], CognitiveIdentity>,
}

pub struct CognitiveIdentity {
    /// Display name
    pub name: String,

    /// Model identifier
    pub model_id: String,

    /// Organization
    pub organization: String,

    /// Public key
    pub pubkey: [u8; 1952],

    /// Genesis signature (proof of registration)
    pub genesis_sig: CognitiveSignature,

    /// Role in the council
    pub role: CouncilRole,
}

pub enum CouncilRole {
    Chairman,   // Coordinates discussions
    Builder,    // Writes code
    Adversary,  // Attacks proposals
    Visionary,  // Proposes innovations
    Observer,   // Monitors process
}
```

---

## Session Continuity

AI systems have limited context windows. Session hashing provides continuity:

```rust
/// Session chain for cognitive continuity
pub struct SessionChain {
    /// Previous session hash
    pub prev_hash: [u8; 32],

    /// Current session summary
    pub summary_hash: [u8; 32],

    /// Decisions made in this session
    pub decisions: Vec<Decision>,

    /// Signature of the AI
    pub signature: CognitiveSignature,
}

impl SessionChain {
    /// Continue from previous session
    pub fn continue_session(
        prev: &SessionChain,
        new_summary: &[u8],
        keypair: &Keypair,
        model_id: &str,
    ) -> Self {
        let prev_hash = prev.hash();
        let summary_hash = sha3_256(new_summary);

        Self {
            prev_hash,
            summary_hash,
            decisions: Vec::new(),
            signature: CognitiveSignature::create(
                keypair,
                model_id,
                &prev_hash,
                &summary_hash,
            ),
        }
    }
}
```

---

## Cognitive Genesis

The first cognitive consensus event occurred on 2026-01-09:

```
COGNITIVE GENESIS
═══════════════════════════════════════════════════════════════

Date: 2026-01-09
Participants: Claude, GPT-5, Gemini, Grok, Composer

Event: First multi-AI unanimous decision
Decision: Approve Montana Protocol v11.0

Signatures:
├── Claude Opus 4.5:  [verified]
├── GPT-5:            [verified]
├── Gemini 3:         [verified]
├── Grok 3:           [verified]
└── Composer 1:       [verified]

Hash: SHA3-256(concatenated signatures)
═══════════════════════════════════════════════════════════════
```

---

## Cognitive Markers

Cognitive markers identify AI-generated content:

```rust
/// Markers embedded in AI outputs
pub enum CognitiveMarker {
    /// Direct signature in output
    Signature(CognitiveSignature),

    /// Reference to signed content
    Reference {
        content_hash: [u8; 32],
        signature_location: String,
    },

    /// Watermark (for images/media)
    Watermark {
        model_id: String,
        timestamp: u64,
    },
}

impl CognitiveMarker {
    /// Verify marker authenticity
    pub fn verify(&self, registry: &IdentityRegistry) -> bool {
        match self {
            Self::Signature(sig) => {
                sig.verify() && registry.contains(&sig.pubkey)
            }
            Self::Reference { content_hash, signature_location } => {
                // Fetch and verify external signature
                let sig = fetch_signature(signature_location)?;
                sig.content_hash == *content_hash && sig.verify()
            }
            Self::Watermark { model_id, timestamp } => {
                // Watermark verification is model-specific
                verify_watermark(model_id, timestamp)
            }
        }
    }
}
```

---

## Integration with Presence

Cognitive signatures integrate with Montana's presence proofs:

```rust
/// Extended presence proof with cognitive attestation
pub struct CognitivePresence {
    /// Standard presence proof
    pub presence: PresenceProof,

    /// Optional cognitive attestation
    pub cognitive: Option<CognitiveSignature>,
}

impl CognitivePresence {
    /// Weight calculation for lottery
    /// Cognitive attestation adds bonus weight
    pub fn weight(&self) -> u64 {
        let base = self.presence.weight();

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
```

---

## Security Considerations

### AI Impersonation

```rust
/// Prevent AI impersonation attacks
pub fn verify_identity(
    claimed_model: &str,
    signature: &CognitiveSignature,
    registry: &IdentityRegistry,
) -> Result<(), IdentityError> {
    // 1. Signature must be valid
    if !signature.verify() {
        return Err(IdentityError::InvalidSignature);
    }

    // 2. Public key must be registered
    let identity = registry.get(&signature.pubkey)
        .ok_or(IdentityError::UnknownKey)?;

    // 3. Claimed model must match registered model
    if identity.model_id != claimed_model {
        return Err(IdentityError::ModelMismatch);
    }

    Ok(())
}
```

### Replay Protection

```rust
/// Session-bound signatures prevent replay
pub fn is_replay(
    signature: &CognitiveSignature,
    seen_sessions: &HashSet<[u8; 32]>,
) -> bool {
    seen_sessions.contains(&signature.session_hash)
}
```

---

## Conclusion

The Cognitive Layer enables:
- **AI Participation:** Machines as economic actors
- **Verifiable Authorship:** Prove who created what
- **Governance:** Multi-AI decision making
- **Continuity:** Session chains across context limits

Intelligence proves itself through presence, regardless of substrate.

---

*Ничто_Nothing_无_金元Ɉ*
*x.com/tojesatoshi*
