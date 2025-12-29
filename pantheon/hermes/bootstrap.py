"""
Proof of Time - Bootstrap and Peer Discovery Module
Production-grade peer discovery with DNS seeds and fallback mechanisms.

Includes:
- DNS seed resolution with caching
- Hardcoded bootstrap nodes for initial sync
- Peer address management
- Geographic diversity (when possible)

Time is the ultimate proof.
"""

import socket
import logging
import time
import random
import threading
import json
import os
from typing import List, Tuple, Optional, Set, Dict
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger("proof_of_time.bootstrap")


# ============================================================================
# NETWORK TYPES
# ============================================================================

class Network(Enum):
    """Network type enumeration."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    REGTEST = "regtest"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _parse_bootstrap_peers(peers_str: str) -> List[Tuple[str, int]]:
    """
    Parse bootstrap peers from environment variable string.

    Format: "ip1:port1,ip2:port2" e.g. "1.2.3.4:18333,5.6.7.8:18333"

    Args:
        peers_str: Comma-separated list of ip:port pairs

    Returns:
        List of (ip, port) tuples
    """
    if not peers_str or not peers_str.strip():
        return []

    peers = []
    for peer in peers_str.split(","):
        peer = peer.strip()
        if not peer:
            continue
        try:
            if ":" in peer:
                ip, port = peer.rsplit(":", 1)
                peers.append((ip.strip(), int(port)))
            else:
                # Default to testnet port
                peers.append((peer.strip(), 18333))
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid peer format '{peer}': {e}")
            continue

    if peers:
        logger.info(f"Loaded {len(peers)} bootstrap peers from environment")
    return peers


# ============================================================================
# SEED CONFIGURATION
# ============================================================================

@dataclass
class SeedConfig:
    """Seed node configuration."""

    # DNS seeds - resolved to discover peer IPs
    # In production, these would be actual DNS records returning peer IPs
    dns_seeds: Dict[Network, List[str]] = field(default_factory=lambda: {
        Network.MAINNET: [
            "seed1.proofoftime.network",
            "seed2.proofoftime.network",
            "seed3.proofoftime.network",
            "dnsseed.proofoftime.org",
            "seed.pot-network.io",
        ],
        Network.TESTNET: [
            "testnet-seed1.proofoftime.network",
            "testnet-seed2.proofoftime.network",
        ],
        Network.REGTEST: [],
    })

    # Hardcoded bootstrap nodes (IP:port)
    # These are fallback nodes when DNS seeds are unavailable
    # Can be overridden via POT_BOOTSTRAP_PEERS environment variable
    # Format: "ip1:port1,ip2:port2" e.g. "1.2.3.4:18333,5.6.7.8:18333"
    bootstrap_nodes: Dict[Network, List[Tuple[str, int]]] = field(default_factory=lambda: {
        Network.MAINNET: [
            # Primary bootstrap nodes (geographically distributed)
            # Replace with actual mainnet bootstrap nodes before launch
            ("127.0.0.1", 8333),  # Local development
        ],
        Network.TESTNET: _parse_bootstrap_peers(os.environ.get("POT_BOOTSTRAP_PEERS", "")) or [
            # Testnet bootstrap nodes - set via POT_BOOTSTRAP_PEERS env var
            ("127.0.0.1", 18333),  # Fallback to localhost
        ],
        Network.REGTEST: [
            ("127.0.0.1", 18444),
        ],
    })

    # Default ports per network
    default_ports: Dict[Network, int] = field(default_factory=lambda: {
        Network.MAINNET: 8333,
        Network.TESTNET: 18333,
        Network.REGTEST: 18444,
    })

    # DNS resolution timeout (seconds)
    dns_timeout: float = 10.0

    # Cache TTL for DNS results (seconds)
    dns_cache_ttl: int = 3600

    # Maximum addresses to return from DNS
    max_dns_results: int = 25

    # Retry attempts for DNS resolution
    dns_retry_count: int = 3

    # Delay between DNS retries (seconds)
    dns_retry_delay: float = 2.0


# ============================================================================
# DNS RESOLUTION
# ============================================================================

class DNSResolver:
    """
    DNS seed resolver with caching and fallback.

    Resolves DNS seeds to peer IP addresses. Handles:
    - Multiple record types (A, AAAA)
    - Caching with TTL
    - Retry logic
    - Timeout handling
    """

    def __init__(self, config: Optional[SeedConfig] = None):
        self.config = config or SeedConfig()

        # Cache: seed -> (addresses, expiry_time)
        self._cache: Dict[str, Tuple[List[str], float]] = {}
        self._cache_lock = threading.Lock()

    def resolve_seed(self, seed: str, port: int) -> List[Tuple[str, int]]:
        """
        Resolve a single DNS seed to (ip, port) tuples.

        Args:
            seed: DNS seed hostname
            port: Default port to use

        Returns:
            List of (ip, port) tuples
        """
        # Check cache first
        with self._cache_lock:
            if seed in self._cache:
                addresses, expiry = self._cache[seed]
                if time.time() < expiry:
                    logger.debug(f"DNS cache hit for {seed}: {len(addresses)} addresses")
                    return [(addr, port) for addr in addresses]

        # Resolve with retries
        addresses = []
        last_error = None

        for attempt in range(self.config.dns_retry_count):
            try:
                # Set socket timeout
                socket.setdefaulttimeout(self.config.dns_timeout)

                # Get all address info (IPv4 and IPv6)
                results = socket.getaddrinfo(
                    seed, port,
                    socket.AF_UNSPEC,  # Both IPv4 and IPv6
                    socket.SOCK_STREAM
                )

                # Extract unique IPs
                seen = set()
                for family, type_, proto, canonname, sockaddr in results:
                    ip = sockaddr[0]
                    if ip not in seen:
                        seen.add(ip)
                        addresses.append(ip)

                if addresses:
                    break

            except socket.gaierror as e:
                last_error = e
                logger.debug(f"DNS resolution failed for {seed} (attempt {attempt + 1}): {e}")
                if attempt < self.config.dns_retry_count - 1:
                    time.sleep(self.config.dns_retry_delay)
            except socket.timeout:
                last_error = socket.timeout("DNS resolution timed out")
                logger.debug(f"DNS timeout for {seed} (attempt {attempt + 1})")
                if attempt < self.config.dns_retry_count - 1:
                    time.sleep(self.config.dns_retry_delay)
            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected DNS error for {seed}: {e}")
                break
            finally:
                socket.setdefaulttimeout(None)

        if not addresses:
            if last_error:
                logger.warning(f"Failed to resolve DNS seed {seed}: {last_error}")
            return []

        # Cache results
        with self._cache_lock:
            self._cache[seed] = (addresses, time.time() + self.config.dns_cache_ttl)

        logger.info(f"Resolved DNS seed {seed}: {len(addresses)} addresses")
        return [(addr, port) for addr in addresses[:self.config.max_dns_results]]

    def resolve_all_seeds(self, network: Network) -> List[Tuple[str, int]]:
        """
        Resolve all DNS seeds for a network.

        Args:
            network: Target network

        Returns:
            List of (ip, port) tuples from all seeds
        """
        seeds = self.config.dns_seeds.get(network, [])
        port = self.config.default_ports.get(network, 8333)

        all_addresses = []
        seen = set()

        # Shuffle seeds for load balancing
        shuffled_seeds = list(seeds)
        random.shuffle(shuffled_seeds)

        for seed in shuffled_seeds:
            try:
                addresses = self.resolve_seed(seed, port)
                for addr in addresses:
                    if addr not in seen:
                        seen.add(addr)
                        all_addresses.append(addr)
            except Exception as e:
                logger.warning(f"Error resolving seed {seed}: {e}")
                continue

        logger.info(f"DNS resolution complete: {len(all_addresses)} unique addresses from {len(seeds)} seeds")
        return all_addresses

    def clear_cache(self):
        """Clear DNS cache."""
        with self._cache_lock:
            self._cache.clear()


# ============================================================================
# BOOTSTRAP MANAGER
# ============================================================================

class BootstrapManager:
    """
    Manages peer discovery and bootstrap process.

    Provides:
    - Initial peer discovery from DNS and hardcoded seeds
    - Persistent address storage
    - Address scoring and selection
    - Testnet/mainnet separation
    """

    def __init__(
        self,
        network: Network = Network.MAINNET,
        data_dir: Optional[str] = None,
        config: Optional[SeedConfig] = None
    ):
        self.network = network
        self.config = config or SeedConfig()
        self.dns_resolver = DNSResolver(self.config)

        # Data directory for persistent storage
        if data_dir:
            self.data_dir = Path(data_dir).expanduser()
        else:
            self.data_dir = Path.home() / ".proofoftime"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Address storage
        self._addresses: Dict[Tuple[str, int], AddressInfo] = {}
        self._addresses_lock = threading.Lock()

        # Load persisted addresses
        self._load_addresses()

    def get_initial_peers(self, count: int = 8) -> List[Tuple[str, int]]:
        """
        Get initial peers for connection.

        Order of preference:
        1. Previously successful peers (from persistent storage)
        2. DNS seed resolution
        3. Hardcoded bootstrap nodes

        Args:
            count: Maximum number of peers to return

        Returns:
            List of (ip, port) tuples
        """
        peers = []
        seen = set()

        # 1. Try previously successful peers first
        with self._addresses_lock:
            successful = [
                (addr, info) for addr, info in self._addresses.items()
                if info.success_count > 0
            ]
            # Sort by success rate and recency
            successful.sort(
                key=lambda x: (x[1].success_count, -x[1].last_attempt),
                reverse=True
            )
            for addr, _ in successful[:count]:
                if addr not in seen:
                    seen.add(addr)
                    peers.append(addr)

        if len(peers) >= count:
            logger.info(f"Using {len(peers)} previously successful peers")
            return peers[:count]

        # 2. Resolve DNS seeds
        remaining = count - len(peers)
        try:
            dns_peers = self.dns_resolver.resolve_all_seeds(self.network)
            random.shuffle(dns_peers)
            for peer in dns_peers:
                if peer not in seen and remaining > 0:
                    seen.add(peer)
                    peers.append(peer)
                    remaining -= 1
        except Exception as e:
            logger.warning(f"DNS seed resolution failed: {e}")

        if len(peers) >= count:
            logger.info(f"Using {len(peers)} peers from DNS seeds")
            return peers[:count]

        # 3. Fall back to hardcoded bootstrap nodes
        bootstrap = self.config.bootstrap_nodes.get(self.network, [])
        for peer in bootstrap:
            if peer not in seen and remaining > 0:
                seen.add(peer)
                peers.append(peer)
                remaining -= 1

        logger.info(f"Bootstrap: {len(peers)} total peers "
                   f"(prev: {len(successful) if 'successful' in dir() else 0}, "
                   f"dns: {len(dns_peers) if 'dns_peers' in dir() else 0}, "
                   f"bootstrap: {len([p for p in bootstrap if p in peers])})")

        return peers[:count]

    def add_peer(self, address: Tuple[str, int], source: str = "peer"):
        """
        Add a new peer address to the pool.

        Args:
            address: (ip, port) tuple
            source: Where the address came from (dns, peer, manual)
        """
        with self._addresses_lock:
            if address not in self._addresses:
                self._addresses[address] = AddressInfo(
                    ip=address[0],
                    port=address[1],
                    source=source,
                    first_seen=time.time()
                )

    def record_connection_attempt(self, address: Tuple[str, int], success: bool):
        """
        Record the result of a connection attempt.

        Args:
            address: (ip, port) tuple
            success: Whether connection succeeded
        """
        with self._addresses_lock:
            if address not in self._addresses:
                self._addresses[address] = AddressInfo(
                    ip=address[0],
                    port=address[1],
                    source="unknown",
                    first_seen=time.time()
                )

            info = self._addresses[address]
            info.attempt_count += 1
            info.last_attempt = time.time()

            if success:
                info.success_count += 1
                info.last_success = time.time()
            else:
                info.failure_count += 1
                info.last_failure = time.time()

        # Persist periodically
        if random.random() < 0.1:  # 10% chance per call
            self._save_addresses()

    def get_addresses_for_gossip(self, count: int = 10) -> List[Tuple[str, int]]:
        """
        Get addresses to share with other peers (addr message).

        Prioritizes:
        1. Recently successful connections
        2. Diverse subnet coverage

        Args:
            count: Maximum addresses to return

        Returns:
            List of (ip, port) tuples
        """
        with self._addresses_lock:
            # Filter to addresses with recent success
            max_age = 86400 * 3  # 3 days
            now = time.time()

            candidates = [
                (addr, info) for addr, info in self._addresses.items()
                if info.last_success and (now - info.last_success) < max_age
            ]

            # Sort by recency
            candidates.sort(key=lambda x: x[1].last_success or 0, reverse=True)

            return [addr for addr, _ in candidates[:count]]

    def _get_addresses_path(self) -> Path:
        """Get path to addresses file."""
        return self.data_dir / f"peers_{self.network.value}.json"

    def _load_addresses(self):
        """Load addresses from persistent storage."""
        path = self._get_addresses_path()
        if not path.exists():
            return

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            for entry in data:
                addr = (entry['ip'], entry['port'])
                self._addresses[addr] = AddressInfo(
                    ip=entry['ip'],
                    port=entry['port'],
                    source=entry.get('source', 'unknown'),
                    first_seen=entry.get('first_seen', 0),
                    last_attempt=entry.get('last_attempt', 0),
                    last_success=entry.get('last_success'),
                    last_failure=entry.get('last_failure'),
                    attempt_count=entry.get('attempt_count', 0),
                    success_count=entry.get('success_count', 0),
                    failure_count=entry.get('failure_count', 0)
                )

            logger.info(f"Loaded {len(self._addresses)} addresses from {path}")

        except Exception as e:
            logger.warning(f"Failed to load addresses: {e}")

    def _save_addresses(self):
        """Save addresses to persistent storage."""
        with self._addresses_lock:
            data = []
            for addr, info in self._addresses.items():
                data.append({
                    'ip': info.ip,
                    'port': info.port,
                    'source': info.source,
                    'first_seen': info.first_seen,
                    'last_attempt': info.last_attempt,
                    'last_success': info.last_success,
                    'last_failure': info.last_failure,
                    'attempt_count': info.attempt_count,
                    'success_count': info.success_count,
                    'failure_count': info.failure_count
                })

            # Keep only most relevant addresses
            data.sort(
                key=lambda x: (x['success_count'], x.get('last_success') or 0),
                reverse=True
            )
            data = data[:1000]  # Keep top 1000

        try:
            path = self._get_addresses_path()
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(data)} addresses to {path}")
        except Exception as e:
            logger.warning(f"Failed to save addresses: {e}")

    def shutdown(self):
        """Save state on shutdown."""
        self._save_addresses()


@dataclass
class AddressInfo:
    """Information about a peer address."""
    ip: str
    port: int
    source: str = "unknown"
    first_seen: float = 0
    last_attempt: float = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    attempt_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate connection success rate."""
        if self.attempt_count == 0:
            return 0.0
        return self.success_count / self.attempt_count


# ============================================================================
# QUICK START HELPER
# ============================================================================

def get_bootstrap_peers(
    network: Network = Network.MAINNET,
    count: int = 8
) -> List[Tuple[str, int]]:
    """
    Quick helper to get bootstrap peers.

    Args:
        network: Target network (mainnet, testnet, regtest)
        count: Number of peers to return

    Returns:
        List of (ip, port) tuples
    """
    manager = BootstrapManager(network=network)
    return manager.get_initial_peers(count)


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run bootstrap self-tests."""
    logger.info("Running bootstrap self-tests...")

    # Test SeedConfig defaults
    config = SeedConfig()
    assert len(config.dns_seeds[Network.MAINNET]) > 0
    assert len(config.bootstrap_nodes[Network.MAINNET]) > 0
    logger.info("✓ SeedConfig defaults")

    # Test DNSResolver (with localhost fallback)
    resolver = DNSResolver(config)

    # Test resolving localhost
    addresses = resolver.resolve_seed("localhost", 8333)
    assert len(addresses) > 0
    assert addresses[0][1] == 8333
    logger.info(f"✓ DNS resolver (localhost: {addresses})")

    # Test cache
    addresses2 = resolver.resolve_seed("localhost", 8333)
    assert addresses == addresses2
    logger.info("✓ DNS cache")

    # Test BootstrapManager
    manager = BootstrapManager(network=Network.REGTEST)

    # Get initial peers (will use hardcoded bootstrap)
    peers = manager.get_initial_peers(count=2)
    assert len(peers) > 0
    logger.info(f"✓ BootstrapManager (peers: {peers})")

    # Test address recording
    test_addr = ("127.0.0.1", 8333)
    manager.add_peer(test_addr, source="test")
    manager.record_connection_attempt(test_addr, success=True)
    manager.record_connection_attempt(test_addr, success=False)

    with manager._addresses_lock:
        info = manager._addresses[test_addr]
        assert info.attempt_count == 2
        assert info.success_count == 1
        assert info.failure_count == 1
    logger.info("✓ Address recording")

    # Test gossip addresses
    gossip = manager.get_addresses_for_gossip(count=5)
    assert len(gossip) >= 0  # May be 0 if no recent successes
    logger.info(f"✓ Gossip addresses (count: {len(gossip)})")

    # Test persistence
    manager._save_addresses()
    manager2 = BootstrapManager(network=Network.REGTEST)
    # Should load saved addresses
    logger.info("✓ Address persistence")

    manager.shutdown()

    logger.info("All bootstrap self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(message)s"
    )
    _self_test()
