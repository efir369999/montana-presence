"""
Montana v4.0 - The Twelve Apostles Handshake System

Each node chooses exactly 12 trust partners. No more. No less.
These are your Apostles — people you vouch for with your reputation.

Trust Manifesto:
Before forming a handshake, ask yourself:

  Do I know this person?
  Not an avatar — a human.

  Do I trust them with my time?
  Willing to lose if they fail?

  Do I wish them longevity?
  Want them here for years?

  If any answer is NO — do not shake.

Seniority Bonus:
Older nodes vouching for newer nodes carries more weight.
Node #1000 shakes #50: value = 1 + log10(1000/50) = 2.30
Node #1000 shakes #999: value = 1 + log10(1000/999) = 1.00

Time is priceless. Trust is sacred.
"""

import time
import struct
import math
import logging
import threading
import os
from typing import Optional, Tuple, Dict, Any, List, Set
from dataclasses import dataclass, field
from hashlib import sha3_256
from enum import IntEnum, auto

# Hal Humanity System imports
from pantheon.hal.humanity import (
    HumanityTier,
    HumanityProof,
    HumanityProfile,
    HumanityVerifier,
    get_max_apostles,
    verify_different_humans,
    HANDSHAKE_MIN_HUMANITY,
)

logger = logging.getLogger("montana.apostles.handshake")


# ============================================================================
# CONSTANTS
# ============================================================================

MAX_APOSTLES = 12                      # Exactly 12 trust partners
MIN_INTEGRITY_FOR_HANDSHAKE = 0.50    # 50% minimum integrity
HANDSHAKE_COOLDOWN = 86400            # 24 hours between handshakes


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class HandshakeStatus(IntEnum):
    """Handshake status."""
    PENDING = 0         # Request sent, awaiting response
    ACCEPTED = 1        # Mutual handshake established
    REJECTED = 2        # Request rejected
    DISSOLVED = 3       # Previously active, now dissolved
    EXPIRED = 4         # Request expired without response


@dataclass
class HandshakeRequest:
    """
    Apostle handshake request.

    Step 1: Initiate handshake request.
    Must be mutually confirmed to form a handshake.
    """
    from_pubkey: bytes              # Requester's public key
    to_pubkey: bytes               # Target's public key
    timestamp: int                  # Bitcoin time (or wall clock)
    nonce: bytes                    # Random nonce (32 bytes)
    signature: bytes = b''         # SPHINCS+ signature
    btc_height: int = 0            # Bitcoin height at request

    def serialize(self) -> bytes:
        """Serialize request."""
        data = bytearray()
        data.extend(self.from_pubkey)
        data.extend(self.to_pubkey)
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(self.nonce)
        data.extend(struct.pack('<Q', self.btc_height))
        data.extend(struct.pack('<I', len(self.signature)))
        data.extend(self.signature)
        return bytes(data)

    def hash(self) -> bytes:
        """Compute request hash for signing."""
        data = self.from_pubkey
        data += self.to_pubkey
        data += struct.pack('<Q', self.timestamp)
        data += self.nonce
        data += struct.pack('<Q', self.btc_height)
        return sha3_256(data).digest()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['HandshakeRequest', int]:
        """Deserialize request."""
        from_pubkey = data[offset:offset + 32]
        offset += 32

        to_pubkey = data[offset:offset + 32]
        offset += 32

        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        nonce = data[offset:offset + 32]
        offset += 32

        btc_height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        sig_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        signature = data[offset:offset + sig_len]
        offset += sig_len

        return cls(
            from_pubkey=from_pubkey,
            to_pubkey=to_pubkey,
            timestamp=timestamp,
            nonce=nonce,
            signature=signature,
            btc_height=btc_height
        ), offset


@dataclass
class HandshakeResponse:
    """
    Apostle handshake response.

    Step 2: Respond to handshake request.
    """
    request_hash: bytes             # Hash of original request
    from_pubkey: bytes             # Responder's public key
    accepted: bool                  # Accept or reject
    timestamp: int                  # Response timestamp
    signature: bytes = b''         # SPHINCS+ signature
    reject_reason: str = ""        # Reason for rejection (if rejected)

    def serialize(self) -> bytes:
        """Serialize response."""
        data = bytearray()
        data.extend(self.request_hash)
        data.extend(self.from_pubkey)
        data.extend(struct.pack('<B', 1 if self.accepted else 0))
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<I', len(self.signature)))
        data.extend(self.signature)

        # Reject reason
        reason_bytes = self.reject_reason.encode('utf-8')
        data.extend(struct.pack('<H', len(reason_bytes)))
        data.extend(reason_bytes)

        return bytes(data)

    def hash(self) -> bytes:
        """Compute response hash for signing."""
        data = self.request_hash
        data += self.from_pubkey
        data += struct.pack('<B', 1 if self.accepted else 0)
        data += struct.pack('<Q', self.timestamp)
        return sha3_256(data).digest()


@dataclass
class Handshake:
    """
    Established handshake between two Apostles.

    Step 3: Finalized handshake record.
    """
    party_a: bytes                  # First party public key
    party_b: bytes                  # Second party public key
    request_sig: bytes             # Signature from party_a
    response_sig: bytes            # Signature from party_b
    btc_height: int                # Bitcoin height when established
    timestamp: int                  # Timestamp when established
    status: HandshakeStatus = HandshakeStatus.ACCEPTED

    def serialize(self) -> bytes:
        """Serialize handshake."""
        data = bytearray()
        data.extend(self.party_a)
        data.extend(self.party_b)
        data.extend(struct.pack('<Q', self.btc_height))
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<B', self.status))

        data.extend(struct.pack('<I', len(self.request_sig)))
        data.extend(self.request_sig)

        data.extend(struct.pack('<I', len(self.response_sig)))
        data.extend(self.response_sig)

        return bytes(data)

    def hash(self) -> bytes:
        """Compute handshake hash."""
        data = self.party_a + self.party_b
        data += struct.pack('<Q', self.btc_height)
        data += struct.pack('<Q', self.timestamp)
        return sha3_256(data).digest()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['Handshake', int]:
        """Deserialize handshake."""
        party_a = data[offset:offset + 32]
        offset += 32

        party_b = data[offset:offset + 32]
        offset += 32

        btc_height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        status = HandshakeStatus(data[offset])
        offset += 1

        req_sig_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        request_sig = data[offset:offset + req_sig_len]
        offset += req_sig_len

        resp_sig_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        response_sig = data[offset:offset + resp_sig_len]
        offset += resp_sig_len

        return cls(
            party_a=party_a,
            party_b=party_b,
            request_sig=request_sig,
            response_sig=response_sig,
            btc_height=btc_height,
            timestamp=timestamp,
            status=status
        ), offset


# ============================================================================
# NODE PROFILE FOR HANDSHAKE REQUIREMENTS
# ============================================================================

@dataclass
class NodeProfile:
    """Node profile for handshake eligibility."""
    pubkey: bytes
    node_number: int = 0           # Sequential node number (#1, #2, ...)
    integrity_score: float = 1.0   # 0.0 to 1.0
    is_slashed: bool = False
    handshake_count: int = 0
    first_seen: int = 0            # Bitcoin height when registered
    # Hal Humanity System (v4.1)
    humanity_tier: HumanityTier = HumanityTier.HARDWARE  # Default bootstrap tier
    humanity_proofs: List[HumanityProof] = field(default_factory=list)

    @property
    def humanity_score(self) -> float:
        """Compute humanity score from proofs."""
        from pantheon.hal.humanity import compute_humanity_score
        return compute_humanity_score(self.humanity_proofs)

    @property
    def max_apostles(self) -> int:
        """Get max Apostles allowed based on humanity tier."""
        return get_max_apostles(self.humanity_tier)


# ============================================================================
# HANDSHAKE PROTOCOL
# ============================================================================

class HandshakeProtocol:
    """
    Handshake protocol implementation.

    Three-step process:
    1. Initiate: Party A sends request
    2. Respond: Party B accepts/rejects
    3. Finalize: Record handshake on-chain
    """

    def __init__(self, get_btc_time=None, sign_func=None, verify_func=None):
        """
        Initialize protocol.

        Args:
            get_btc_time: Function to get current Bitcoin time
            sign_func: Function to sign messages (SPHINCS+)
            verify_func: Function to verify signatures
        """
        self.get_btc_time = get_btc_time or (lambda: int(time.time()))
        self.sign = sign_func
        self.verify = verify_func

    def initiate(
        self,
        my_privkey: bytes,
        my_pubkey: bytes,
        target_pubkey: bytes
    ) -> HandshakeRequest:
        """
        Step 1: Initiate handshake request.

        Args:
            my_privkey: My secret key
            my_pubkey: My public key
            target_pubkey: Target's public key

        Returns:
            HandshakeRequest to send to target
        """
        request = HandshakeRequest(
            from_pubkey=my_pubkey,
            to_pubkey=target_pubkey,
            timestamp=self.get_btc_time(),
            nonce=os.urandom(32),
            btc_height=0  # Would be set from oracle
        )

        # Sign request
        if self.sign:
            request.signature = self.sign(my_privkey, request.hash())
        else:
            # Placeholder signature
            request.signature = sha3_256(request.hash() + my_privkey).digest()

        logger.info(
            f"Handshake initiated: {my_pubkey.hex()[:16]} -> {target_pubkey.hex()[:16]}"
        )

        return request

    def respond(
        self,
        my_privkey: bytes,
        my_pubkey: bytes,
        request: HandshakeRequest,
        accept: bool,
        reject_reason: str = ""
    ) -> Tuple[Optional[HandshakeResponse], Optional[str]]:
        """
        Step 2: Respond to handshake request.

        Args:
            my_privkey: My secret key
            my_pubkey: My public key
            request: Incoming request
            accept: Whether to accept
            reject_reason: Reason for rejection

        Returns:
            (HandshakeResponse, error) tuple
        """
        # Verify request signature
        if self.verify:
            if not self.verify(request.from_pubkey, request.hash(), request.signature):
                return None, "Invalid request signature"

        # Check target is me
        if request.to_pubkey != my_pubkey:
            return None, "Request not addressed to me"

        response = HandshakeResponse(
            request_hash=request.hash(),
            from_pubkey=my_pubkey,
            accepted=accept,
            timestamp=self.get_btc_time(),
            reject_reason=reject_reason
        )

        # Sign response
        if self.sign:
            response.signature = self.sign(my_privkey, response.hash())
        else:
            response.signature = sha3_256(response.hash() + my_privkey).digest()

        status = "accepted" if accept else f"rejected ({reject_reason})"
        logger.info(
            f"Handshake response: {request.from_pubkey.hex()[:16]} <- {my_pubkey.hex()[:16]}: {status}"
        )

        return response, None

    def finalize(
        self,
        request: HandshakeRequest,
        response: HandshakeResponse
    ) -> Tuple[Optional[Handshake], Optional[str]]:
        """
        Step 3: Finalize handshake.

        Args:
            request: Original request
            response: Acceptance response

        Returns:
            (Handshake, error) tuple
        """
        # Verify response matches request
        if response.request_hash != request.hash():
            return None, "Response does not match request"

        # Must be accepted
        if not response.accepted:
            return None, f"Handshake rejected: {response.reject_reason}"

        # Create handshake record
        handshake = Handshake(
            party_a=request.from_pubkey,
            party_b=response.from_pubkey,
            request_sig=request.signature,
            response_sig=response.signature,
            btc_height=request.btc_height,
            timestamp=self.get_btc_time(),
            status=HandshakeStatus.ACCEPTED
        )

        logger.info(
            f"Handshake finalized: {request.from_pubkey.hex()[:16]} <-> {response.from_pubkey.hex()[:16]}"
        )

        return handshake, None


# ============================================================================
# SENIORITY BONUS
# ============================================================================

def compute_handshake_value(my_number: int, partner_number: int) -> float:
    """
    Compute handshake value based on seniority.

    Older nodes vouching for newer nodes carries more weight.

    Examples:
    - Node #1000 shakes #50:  value = 1 + log10(1000/50)  = 2.30
    - Node #1000 shakes #999: value = 1 + log10(1000/999) = 1.00

    Args:
        my_number: My node number
        partner_number: Partner's node number

    Returns:
        Handshake value (base 1.0 + seniority bonus)
    """
    base = 1.0

    if partner_number < my_number and partner_number > 0:
        # Older partner - they are vouching for me
        bonus = math.log10(my_number / partner_number)
        return base + bonus
    else:
        # Same age or I'm older - no bonus
        return base


# ============================================================================
# APOSTLE MANAGER
# ============================================================================

class ApostleManager:
    """
    Manages the Twelve Apostles for a node.

    Tracks:
    - Incoming handshakes (nodes who trust me)
    - Outgoing handshakes (nodes I trust)
    - Handshake requests (pending)
    """

    def __init__(self, my_pubkey: bytes, my_node_number: int = 0):
        """
        Initialize Apostle Manager.

        Args:
            my_pubkey: My public key
            my_node_number: My sequential node number
        """
        self.my_pubkey = my_pubkey
        self.my_node_number = my_node_number

        # Handshakes
        self._incoming: Dict[bytes, Handshake] = {}  # partner -> handshake
        self._outgoing: Dict[bytes, Handshake] = {}  # partner -> handshake

        # Pending requests
        self._pending_sent: Dict[bytes, HandshakeRequest] = {}
        self._pending_received: Dict[bytes, HandshakeRequest] = {}

        # Protocol
        self.protocol = HandshakeProtocol()

        self._lock = threading.RLock()

        logger.info(
            f"Apostle Manager initialized for node #{my_node_number} "
            f"({my_pubkey.hex()[:16]}...)"
        )

    def can_form_handshake(
        self,
        target: NodeProfile,
        my_profile: Optional[NodeProfile] = None
    ) -> Tuple[bool, str]:
        """
        Check if handshake can be formed with target.

        Requirements:
        1. Not at max handshakes for my humanity tier
        2. Target integrity >= 50%
        3. Target not slashed
        4. Not already connected
        5. [v4.1] Target has minimum humanity score
        6. [v4.1] My handshakes don't exceed tier limit

        Args:
            target: Target node profile
            my_profile: My node profile (for humanity tier checks)

        Returns:
            (can_form, reason) tuple
        """
        with self._lock:
            current_handshakes = len(self._outgoing)

            # Determine max apostles based on humanity tier
            if my_profile and my_profile.humanity_tier != HumanityTier.NONE:
                # v4.1: Use tier-based limits
                max_allowed = my_profile.max_apostles
                if current_handshakes >= max_allowed:
                    return False, f"Tier {my_profile.humanity_tier.name} limited to {max_allowed} Apostles"
            else:
                # Legacy: Use global MAX_APOSTLES
                if current_handshakes >= MAX_APOSTLES:
                    return False, f"Already at max handshakes ({MAX_APOSTLES})"

            # Check if already connected
            if target.pubkey in self._outgoing:
                return False, "Already connected to this node"

            # Check target integrity
            if target.integrity_score < MIN_INTEGRITY_FOR_HANDSHAKE:
                return False, f"Target integrity too low ({target.integrity_score:.2f} < {MIN_INTEGRITY_FOR_HANDSHAKE})"

            # Check if target is slashed
            if target.is_slashed:
                return False, "Target is slashed"

            # v4.1: Check target humanity score
            if target.humanity_proofs:
                if target.humanity_score < HANDSHAKE_MIN_HUMANITY:
                    return False, f"Target humanity score too low ({target.humanity_score:.2f} < {HANDSHAKE_MIN_HUMANITY})"

            # v4.1: Check target humanity tier limit
            if target.humanity_tier != HumanityTier.NONE:
                target_max = target.max_apostles
                if target.handshake_count >= target_max:
                    return False, f"Target at tier limit ({target.handshake_count}/{target_max})"

            return True, "Requirements met"

    def initiate_handshake(
        self,
        my_privkey: bytes,
        target: NodeProfile,
        my_profile: Optional[NodeProfile] = None
    ) -> Tuple[Optional[HandshakeRequest], Optional[str]]:
        """
        Initiate handshake with target.

        Args:
            my_privkey: My private key
            target: Target node profile
            my_profile: My node profile (for v4.1 humanity tier checks)

        Returns:
            (HandshakeRequest, error) tuple
        """
        with self._lock:
            # Check requirements (includes v4.1 humanity tier checks)
            can_form, reason = self.can_form_handshake(target, my_profile)
            if not can_form:
                return None, reason

            # Check if already pending
            if target.pubkey in self._pending_sent:
                return None, "Handshake request already pending"

            # Create request
            request = self.protocol.initiate(
                my_privkey, self.my_pubkey, target.pubkey
            )

            # Store pending
            self._pending_sent[target.pubkey] = request

            return request, None

    def receive_request(
        self,
        request: HandshakeRequest
    ) -> bool:
        """
        Receive incoming handshake request.

        Args:
            request: Incoming request

        Returns:
            True if stored successfully
        """
        with self._lock:
            if request.to_pubkey != self.my_pubkey:
                logger.warning("Received request not addressed to me")
                return False

            self._pending_received[request.from_pubkey] = request
            logger.info(f"Received handshake request from {request.from_pubkey.hex()[:16]}...")
            return True

    def accept_handshake(
        self,
        my_privkey: bytes,
        requester_pubkey: bytes
    ) -> Tuple[Optional[HandshakeResponse], Optional[str]]:
        """
        Accept incoming handshake request.

        Args:
            my_privkey: My private key
            requester_pubkey: Requester's public key

        Returns:
            (HandshakeResponse, error) tuple
        """
        with self._lock:
            request = self._pending_received.get(requester_pubkey)
            if not request:
                return None, "No pending request from this node"

            # Check my handshake count
            if len(self._incoming) >= MAX_APOSTLES:
                return self.reject_handshake(my_privkey, requester_pubkey, "At max handshakes")

            response, error = self.protocol.respond(
                my_privkey, self.my_pubkey, request, accept=True
            )

            if error:
                return None, error

            # Don't finalize yet - wait for confirmation
            return response, None

    def reject_handshake(
        self,
        my_privkey: bytes,
        requester_pubkey: bytes,
        reason: str = ""
    ) -> Tuple[Optional[HandshakeResponse], Optional[str]]:
        """
        Reject incoming handshake request.

        Args:
            my_privkey: My private key
            requester_pubkey: Requester's public key
            reason: Rejection reason

        Returns:
            (HandshakeResponse, error) tuple
        """
        with self._lock:
            request = self._pending_received.get(requester_pubkey)
            if not request:
                return None, "No pending request from this node"

            response, error = self.protocol.respond(
                my_privkey, self.my_pubkey, request, accept=False, reject_reason=reason
            )

            if response:
                # Remove from pending
                del self._pending_received[requester_pubkey]

            return response, error

    def finalize_handshake(
        self,
        request: HandshakeRequest,
        response: HandshakeResponse
    ) -> Tuple[Optional[Handshake], Optional[str]]:
        """
        Finalize a handshake after acceptance.

        Args:
            request: Original request
            response: Acceptance response

        Returns:
            (Handshake, error) tuple
        """
        with self._lock:
            handshake, error = self.protocol.finalize(request, response)
            if error:
                return None, error

            # Store handshake
            if request.from_pubkey == self.my_pubkey:
                # I initiated
                self._outgoing[response.from_pubkey] = handshake
                if response.from_pubkey in self._pending_sent:
                    del self._pending_sent[response.from_pubkey]
            else:
                # They initiated
                self._incoming[request.from_pubkey] = handshake
                if request.from_pubkey in self._pending_received:
                    del self._pending_received[request.from_pubkey]

            return handshake, None

    def dissolve_handshake(self, partner_pubkey: bytes) -> bool:
        """
        Dissolve handshake with partner.

        Args:
            partner_pubkey: Partner's public key

        Returns:
            True if dissolved
        """
        with self._lock:
            dissolved = False

            if partner_pubkey in self._outgoing:
                self._outgoing[partner_pubkey].status = HandshakeStatus.DISSOLVED
                del self._outgoing[partner_pubkey]
                dissolved = True

            if partner_pubkey in self._incoming:
                self._incoming[partner_pubkey].status = HandshakeStatus.DISSOLVED
                del self._incoming[partner_pubkey]
                dissolved = True

            if dissolved:
                logger.info(f"Handshake dissolved with {partner_pubkey.hex()[:16]}...")

            return dissolved

    def dissolve_all(self):
        """Dissolve all handshakes (called on slashing)."""
        with self._lock:
            count = len(self._outgoing) + len(self._incoming)
            self._outgoing.clear()
            self._incoming.clear()
            logger.warning(f"All {count} handshakes dissolved")

    def get_handshake_count(self) -> int:
        """Get total handshake count."""
        with self._lock:
            return len(self._outgoing)  # Count outgoing (my apostles)

    def get_incoming_count(self) -> int:
        """Get incoming handshake count (vouchers)."""
        with self._lock:
            return len(self._incoming)

    def get_handshake_score(self) -> float:
        """
        Compute handshake score for Adonis HANDSHAKE dimension.

        Maximum 12 handshakes = 1.0 score.
        """
        with self._lock:
            return len(self._outgoing) / MAX_APOSTLES

    def get_total_handshake_value(self, node_numbers: Dict[bytes, int]) -> float:
        """
        Compute total handshake value including seniority bonus.

        Args:
            node_numbers: Mapping of pubkey -> node number

        Returns:
            Total handshake value
        """
        with self._lock:
            total = 0.0
            for partner_pubkey, _ in self._outgoing.items():
                partner_number = node_numbers.get(partner_pubkey, self.my_node_number)
                total += compute_handshake_value(self.my_node_number, partner_number)
            return total

    def get_apostles(self) -> List[bytes]:
        """Get list of my apostles (nodes I trust)."""
        with self._lock:
            return list(self._outgoing.keys())

    def get_vouchers(self) -> List[bytes]:
        """Get list of vouchers (nodes who trust me)."""
        with self._lock:
            return list(self._incoming.keys())

    def get_status(self) -> Dict[str, Any]:
        """Get apostle status."""
        with self._lock:
            return {
                'my_pubkey': self.my_pubkey.hex()[:16] + '...',
                'node_number': self.my_node_number,
                'outgoing_count': len(self._outgoing),
                'incoming_count': len(self._incoming),
                'pending_sent': len(self._pending_sent),
                'pending_received': len(self._pending_received),
                'handshake_score': self.get_handshake_score(),
                'max_apostles': MAX_APOSTLES
            }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run handshake self-tests."""
    logger.info("Running Apostle handshake self-tests...")

    # Create two nodes
    node_a_pub = b'\x01' * 32
    node_a_priv = b'\x11' * 32
    node_b_pub = b'\x02' * 32
    node_b_priv = b'\x22' * 32

    manager_a = ApostleManager(node_a_pub, my_node_number=100)
    manager_b = ApostleManager(node_b_pub, my_node_number=50)

    # Create profiles
    profile_b = NodeProfile(
        pubkey=node_b_pub,
        node_number=50,
        integrity_score=0.8
    )

    profile_a = NodeProfile(
        pubkey=node_a_pub,
        node_number=100,
        integrity_score=0.9
    )

    # Test can_form_handshake
    can_form, reason = manager_a.can_form_handshake(profile_b)
    assert can_form, reason
    logger.info("  Can form handshake check")

    # Test initiate
    request, error = manager_a.initiate_handshake(node_a_priv, profile_b)
    assert request is not None, error
    assert request.from_pubkey == node_a_pub
    assert request.to_pubkey == node_b_pub
    logger.info("  Initiate handshake")

    # Test receive
    received = manager_b.receive_request(request)
    assert received
    logger.info("  Receive request")

    # Test accept
    response, error = manager_b.accept_handshake(node_b_priv, node_a_pub)
    assert response is not None, error
    assert response.accepted
    logger.info("  Accept handshake")

    # Test finalize (from A's perspective)
    handshake, error = manager_a.finalize_handshake(request, response)
    assert handshake is not None, error
    assert handshake.status == HandshakeStatus.ACCEPTED
    logger.info("  Finalize handshake")

    # Test seniority bonus
    value = compute_handshake_value(100, 50)
    assert value > 1.0  # Should have bonus
    logger.info(f"  Seniority bonus: {value:.2f}")

    # Test handshake count
    assert manager_a.get_handshake_count() == 1
    logger.info("  Handshake count")

    # Test dissolve
    dissolved = manager_a.dissolve_handshake(node_b_pub)
    assert dissolved
    assert manager_a.get_handshake_count() == 0
    logger.info("  Dissolve handshake")

    # Test serialization
    request_bytes = request.serialize()
    request_restored, _ = HandshakeRequest.deserialize(request_bytes)
    assert request_restored.hash() == request.hash()
    logger.info("  Serialization")

    logger.info("All Apostle handshake tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
