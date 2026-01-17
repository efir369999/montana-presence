# Montana Network Layer Security Audit

**Auditor:** Claude Opus 4.5 (Anthropic)
**Date:** 2026-01-08
**Scope:** `montana/src/net/` (P2P network layer)
**Role:** Adversarial attacker with unlimited resources

---

## Executive Summary

The Montana network layer demonstrates **robust security architecture** with multiple layers of defense. The implementation follows Bitcoin Core patterns while adding modern protections against sophisticated attacks like Erebus.

**Overall Assessment: SECURE with minor improvements recommended**

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 3 |
| INFO | 2 |

---

## Attack Surface

### Entry Points

| Component | File | Description |
|-----------|------|-------------|
| TCP Listener | protocol.rs:281 | Port 19333, accepts inbound connections |
| Noise Handshake | encrypted.rs | Authenticated encryption for all P2P traffic |
| Message Processing | protocol.rs:845 | Handles all P2P message types |
| Bootstrap | bootstrap.rs | Initial peer discovery |
| AddrMan | addrman.rs | Address storage with cryptographic bucketing |

### Defense Mechanisms

| Defense | Constant | Purpose |
|---------|----------|---------|
| MAX_PEERS | 125 | Total connection limit |
| MAX_OUTBOUND | 8 | Outbound connection limit |
| MAX_INBOUND | 117 | Inbound connection limit |
| MAX_CONNECTIONS_PER_IP | 2 | Per-IP slot limit |
| MAX_PEERS_PER_NETGROUP | 2 | Per-/16 subnet limit |
| MIN_IP_VOTES | 4 | External IP consensus threshold |
| Eviction Protection | 28 slots | Multi-category peer protection |
| GlobalSubnetLimiter | Two-tier | Adaptive DoS/Erebus protection |
| BoundedInvSet | 100k items | Memory exhaustion prevention |
| ML-DSA-65 | Post-quantum | Bootstrap node authentication |

---

## Attack Simulations

### 1. Eclipse Attack

**Goal:** Isolate victim node by controlling all its connections.

**Attack Plan:**
1. Control IPs in many /16 subnets
2. Poison victim's AddrMan with attacker IPs
3. Wait for victim to select attacker IPs for outbound
4. Fill all inbound slots with attacker nodes
5. Spoof victim's external IP perception

**Analysis:**

```
Outbound Eclipse:
- Need victim to select attacker IPs from AddrMan
- AddrMan uses SipHash with secret 32-byte key
- Bucket assignment: unpredictable without key
- Selection: 50/50 NEW vs TRIED, random within table
- Conclusion: DIFFICULT - requires sustained AddrMan poisoning

Inbound Eclipse:
- MAX_INBOUND = 117 slots available
- MAX_PEERS_PER_NETGROUP = 2 per /16 subnet
- Need at least 59 different /16 subnets to fill 117 slots
- GlobalSubnetLimiter adds time-based rate limiting
- Eviction protection saves 28 slots from eviction
- Conclusion: DIFFICULT - requires massive IP diversity

External IP Spoofing:
- MIN_IP_VOTES = 4 (50% of 8 outbound)
- Only outbound votes count (inbound ignored as potential Sybil)
- Need to control 4+ outbound connections
- Conclusion: DIFFICULT - requires successful outbound eclipse first
```

**Result:** `PROTECTED` - Multiple defense layers make eclipse impractical.

---

### 2. Erebus Attack (AS-level, Long-term)

**Goal:** Gradually take over connections using BGP-level network control over days/weeks.

**Attack Plan:**
1. Control AS with many /16 subnets
2. Gradually increase connection attempts from controlled subnets
3. Build "legitimate" history in slow tier
4. Replace departing honest peers with attacker nodes

**Analysis:**

```
Slow Tier Configuration:
- SLOW_SLOT_SECS = 600 (10 minutes)
- SLOW_PERIOD_SLOTS = 144 (24 hours)
- SLOW_MAX_CHANGE_PERCENT = 20% per period
- SLOW_DEFAULT_REQUESTS = 500

Attack Timeline:
- Day 0: New subnet gets 500 default connections allowed
- Day 1-7: Establish "normal" baseline
- Day 8+: Gradually increase connections
- Limit increases capped at 20%/day

Issue Found:
- SLOW_DEFAULT_REQUESTS = 500 is generous
- Normal subnet may have 0-10 connections/day
- Fresh attacker subnet gets 500 before any history
```

**Result:** `PARTIALLY PROTECTED` - Two-tier system good, but default too generous.

**Finding [MEDIUM]:** See F-001 below.

---

### 3. Memory Exhaustion (DoS)

**Goal:** Crash node by exhausting memory.

**Analysis:**

```
Collection                  | Bound                    | Max Memory
----------------------------|--------------------------|------------
peers HashMap               | MAX_PEERS (125)          | ~1 MB
BoundedInvSet               | MAX_KNOWN_INV (100k)     | ~3.2 MB/peer
AddrMan tables              | 1024*64 + 256*64 = 81k   | ~16 MB
ip_votes                    | MAX_OUTBOUND (8)         | 128 bytes
sent_nonces                 | MAX_PEERS (125)          | 1 KB
subnet_limiter v4           | 65536 /16 subnets max    | ~10 MB
subnet_limiter v6           | 50k /32 subnets (LRU)    | ~200 MB
Flow control recv_queue     | 5 MB per peer            | 625 MB worst case
Flow control send_queue     | 1 MB per peer            | 125 MB worst case
```

**Total worst case:** ~1 GB (acceptable for modern systems)

**Result:** `PROTECTED` - All collections bounded with explicit limits.

---

### 4. CPU Exhaustion (DoS)

**Goal:** Slow node with expensive operations.

**Analysis:**

```
Operation                   | Protection
----------------------------|---------------------------
Noise handshake             | Connection rate limiting
Message deserialization     | Size check before allocation
Inv processing              | 5000 burst, 10/sec
Headers validation          | 5000 burst, 10/sec
GetSlices response          | 5 burst, 1/sec (strict!)
BoundedInvSet eviction      | Batch of 10k (amortized O(1))
AddrMan selection           | Max 1000 iterations
```

**Result:** `PROTECTED` - Rate limiting prevents CPU exhaustion.

---

### 5. Eviction Gaming

**Goal:** Protect attacker nodes from eviction while evicting honest nodes.

**Attack Plan:**
1. Connect from many different /16 subnets
2. Relay recent transactions (get TX protection)
3. Relay recent slices (get Slice protection)
4. Maintain low latency (get Ping protection)
5. Stay connected long (get Longevity protection)

**Analysis:**

```
Protection layers (eviction.rs):
1. NoBan permission    - 0 slots (admin-set)
2. Netgroup diversity  - 4 slots
3. Low ping latency    - 8 slots
4. Recent TX relay     - 4 slots
5. Recent slice relay  - 4 slots
6. Longevity           - 8 slots
Total protected:       28 slots

Eviction target selection:
- Find netgroup with most candidates (highest risk)
- Evict youngest peer from that netgroup
```

**Result:** `PARTIALLY PROTECTED` - Attacker can game protection categories, but netgroup diversity limits effectiveness.

**Finding [LOW]:** See F-002 below.

---

### 6. AddrMan Poisoning

**Goal:** Fill address database with attacker IPs to increase eclipse probability.

**Attack Plan:**
1. Connect from many IPs
2. Send Addr messages with attacker-controlled addresses
3. Fill NEW table with attacker addresses
4. Wait for victim to select attacker IPs for outbound

**Analysis:**

```
Defenses:
- Addr rate limit: 1000 burst, 0.1/sec per peer
- Cryptographic bucketing (SipHash with secret key)
- Source netgroup affects bucket selection
- is_routable() check filters non-routable IPs
- 50/50 selection between NEW and TRIED tables
- TRIED table only contains successfully connected peers

Bucket calculation:
- NEW bucket = SipHash(key || netgroup || source_netgroup) % 1024
- TRIED bucket = SipHash(key || addr || netgroup) % 256
- Position = SipHash(key' || addr || bucket) % 64

Attacker cannot predict bucket without key (32 random bytes).
```

**Result:** `PROTECTED` - Cryptographic bucketing prevents targeted poisoning.

---

### 7. Self-Connection Detection Bypass

**Goal:** Waste connection slots by making node connect to itself.

**Analysis:**

```
Detection mechanism (protocol.rs):
1. Node generates random u64 nonce in Version message
2. Nonce stored in sent_nonces HashSet
3. On receiving Version, check if nonce in sent_nonces
4. If match: self-connection, disconnect

Nonce space: 2^64 possibilities
Collision probability: negligible
```

**Result:** `PROTECTED` - Cryptographic nonce prevents bypass.

---

### 8. Bootstrap Node Impersonation

**Goal:** Impersonate hardcoded bootstrap node to poison new nodes.

**Analysis:**

```
Authentication flow:
1. Client connects to hardcoded IP
2. Client sends AuthChallenge (random bytes)
3. Server signs challenge with ML-DSA-65 private key
4. Client verifies signature against hardcoded public key

ML-DSA-65:
- Post-quantum secure signature scheme
- 4000-byte private key (never transmitted)
- 1952-byte public key (hardcoded in client)
- 3309-byte signature
```

**Result:** `PROTECTED` - Cryptographic authentication prevents impersonation.

---

## Findings

### F-001: Slow Tier Default Too Generous [MEDIUM]

**Location:** rate_limit.rs:315

**Description:**
`SLOW_DEFAULT_REQUESTS = 500` allows new subnets 500 connections per day before any history is established. Legitimate subnets typically have 0-10 connections per day. An attacker with fresh IPs from many /16 subnets could make 500 × N connections before adaptive limits kick in.

**Impact:**
- Initial flood attack possible with fresh IPs
- Undermines Erebus protection for first 24 hours per subnet
- Attacker with 100 fresh /16s could make 50,000 connections/day

**Recommendation:**
```rust
// Current
const SLOW_DEFAULT_REQUESTS: u64 = 500;

// Recommended
const SLOW_DEFAULT_REQUESTS: u64 = 50;
```

Lower default forces subnets to build history before high limits.

---

### F-002: Eviction Protection Categories Gameable [LOW]

**Location:** eviction.rs:54-59

**Description:**
Attacker nodes can achieve multiple protection categories simultaneously:
- Send one transaction to get TX protection (4 slots)
- Relay one slice to get Slice protection (4 slots)
- Have good latency to get Ping protection (8 slots)
- Stay connected to get Longevity protection (8 slots)

**Impact:**
- Attacker can protect up to 24 nodes from eviction
- But limited by netgroup diversity (only 2 per /16)
- Net effect: minor, as diversity limits dominate

**Recommendation:**
Consider adding "useful work" metric that tracks cumulative contribution, not just most recent activity.

---

### F-003: No Rate Limit on Ping/Pong [LOW]

**Location:** protocol.rs:1155-1161

**Description:**
Ping and Pong messages are processed without rate limiting. An attacker could send many Ping messages to cause CPU usage (though minimal per-message).

**Impact:**
- Low - Ping/Pong processing is O(1) and trivial
- Each peer can spam pings, but processing is cheap

**Recommendation:**
Add rate limit: 10 ping/min per peer is sufficient.

```rust
pub struct PingRateLimiter {
    bucket: TokenBucket,
}

impl PingRateLimiter {
    pub fn new() -> Self {
        Self { bucket: TokenBucket::new(10.0, 0.17) } // 10/min
    }
}
```

---

### F-004: Ban by SocketAddr Instead of IP [LOW]

**Location:** connection.rs:17-39

**Description:**
`BanEntry` stores `SocketAddr` (IP + port). Attacker can change port to bypass ban.

**Impact:**
- Banned attacker can reconnect from same IP on different port
- Must accumulate new ban score from scratch

**Recommendation:**
Ban by IP address, not SocketAddr:

```rust
pub struct BanEntry {
    pub ip: IpAddr,        // Changed from SocketAddr
    pub banned_at: u64,
    pub ban_until: u64,
    pub reason: String,
}
```

---

### F-005: Flow Control Pause Could Delay Honest Peers [INFO]

**Location:** protocol.rs:759-780

**Description:**
`MAX_FLOW_CONTROL_PAUSES = 50` allows 50 × 100ms = 5 second delay before disconnecting a slow consumer. During high load, honest slow peers may experience delays.

**Impact:**
- Minor inconvenience for slow peers
- Security tradeoff is correct (disconnect slow consumers)

**Recommendation:**
Current behavior is acceptable. Document as expected behavior.

---

### F-006: IPv6 /32 Granularity May Be Too Coarse [INFO]

**Location:** rate_limit.rs:317-319

**Description:**
IPv6 subnets are tracked at /32 granularity. A single AS typically has a /32 allocation. This is appropriate for Erebus-style attacks but may allow more granular attacks from within a /32.

**Impact:**
- Attacker within a /32 has 2^96 addresses available
- But realistic attack would still be limited by connection rate

**Recommendation:**
Consider /48 or /64 tracking for finer granularity. However, this increases memory usage significantly. Current tradeoff is acceptable.

---

## Defense Matrix

| Attack | Primary Defense | Secondary Defense | Tertiary Defense |
|--------|-----------------|-------------------|------------------|
| Eclipse | Netgroup diversity | AddrMan bucketing | MIN_IP_VOTES |
| Erebus | Two-tier limiter | Netgroup limits | Eviction protection |
| Memory DoS | Bounded collections | Flow control | Per-peer limits |
| CPU DoS | Rate limiting | Message size limits | Flow control |
| Amplification | Per-IP limits | Rate limiting | - |
| Bootstrap impersonation | ML-DSA-65 | Hardcoded pubkeys | - |
| Self-connection | Nonce detection | - | - |

---

## Positive Findings

### P-001: Excellent Memory Safety
All unbounded collections have explicit limits with documented memory calculations.

### P-002: Two-Tier Adaptive Rate Limiting
The GlobalSubnetLimiter with fast (minute) and slow (day) tiers provides excellent defense against both burst DoS and long-term Erebus attacks.

### P-003: Cryptographic Address Management
SipHash-based bucket assignment with secret key prevents targeted AddrMan manipulation.

### P-004: Post-Quantum Bootstrap Authentication
ML-DSA-65 protects against future quantum attacks on bootstrap infrastructure.

### P-005: Multi-Layer Eviction Protection
28 protected slots across 6 categories ensure diverse honest peer retention.

### P-006: Noise Protocol Encryption
All P2P traffic is encrypted and authenticated, preventing MITM attacks.

---

## Conclusion

Montana's network layer demonstrates **production-ready security** with comprehensive defenses against known P2P attack vectors. The implementation shows clear influence from Bitcoin Core's battle-tested patterns while adding modern protections.

**No critical or high severity issues found.**

The medium severity finding (F-001: generous slow tier default) should be addressed before mainnet launch. Low severity findings are minor improvements that can be addressed over time.

**Verdict: SAFE for continued development**

---

## Appendix: Attack Resources Assumed

| Resource | Capability |
|----------|------------|
| Budget | $1B+ |
| Botnet | 10M+ nodes |
| AS Control | Multiple autonomous systems |
| BGP Hijacking | Capable |
| Time | Years of preparation |
| Insider Access | None assumed |

Even with these resources, no practical attack path to full node compromise was identified.

---

*Report generated by Claude Opus 4.5*
*Anthropic Council Security Audit Program*
