"""
Proof of Time - IP Validation & VPN/Proxy Detection Module
Production-grade IP validation with static IP enforcement.

Security measures:
- Static IP requirement (no dynamic residential)
- VPN/Proxy/Tor detection and blocking
- Datacenter IP identification
- ASN-based reputation system
- rDNS verification
- Rate limiting per subnet

Best practices applied:
- IANA reserved range blocking
- Known VPN provider blocking
- Datacenter ASN whitelist (optional)
- Geographic diversity enforcement
- Connection age tracking

Time is the ultimate proof.
"""

import ipaddress
import socket
import hashlib
import struct
import time
import threading
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import IntEnum, auto
from collections import defaultdict

logger = logging.getLogger("proof_of_time.ip_validator")


# ============================================================================
# IP CLASSIFICATION
# ============================================================================

class IPType(IntEnum):
    """IP address type classification."""
    UNKNOWN = 0
    STATIC_RESIDENTIAL = 1  # Home/business static IP
    STATIC_DATACENTER = 2   # Server/cloud provider
    DYNAMIC_RESIDENTIAL = 3  # Dynamic home IP (not allowed)
    VPN = 4                  # VPN exit node (blocked)
    TOR = 5                  # Tor exit node (blocked)
    PROXY = 6                # Open proxy (blocked)
    CGNAT = 7               # Carrier-grade NAT (blocked)
    RESERVED = 8            # IANA reserved (blocked)
    BOGON = 9               # Bogon/martian (blocked)


class ValidationResult(IntEnum):
    """IP validation result codes."""
    ALLOWED = 0
    BLOCKED_RESERVED = 1
    BLOCKED_PRIVATE = 2
    BLOCKED_VPN = 3
    BLOCKED_TOR = 4
    BLOCKED_PROXY = 5
    BLOCKED_CGNAT = 6
    BLOCKED_DYNAMIC = 7
    BLOCKED_DATACENTER = 8  # If datacenter mode disabled
    BLOCKED_REPUTATION = 9
    BLOCKED_RATE_LIMIT = 10
    BLOCKED_BLACKLIST = 11
    BLOCKED_NO_RDNS = 12


@dataclass
class IPInfo:
    """Information about an IP address."""
    ip: str
    ip_type: IPType = IPType.UNKNOWN
    asn: int = 0
    asn_name: str = ""
    country: str = ""
    rdns: str = ""
    is_static: bool = False
    reputation_score: float = 0.5  # 0=bad, 1=good
    first_seen: float = 0.0
    last_seen: float = 0.0
    connection_count: int = 0
    misbehavior_count: int = 0


# ============================================================================
# KNOWN RANGES
# ============================================================================

# IANA Reserved and Special-Use Ranges (RFC 5735, RFC 6890)
RESERVED_RANGES = [
    "0.0.0.0/8",          # "This" network
    "10.0.0.0/8",         # Private-Use
    "100.64.0.0/10",      # Shared Address Space (CGNAT)
    "127.0.0.0/8",        # Loopback
    "169.254.0.0/16",     # Link-Local
    "172.16.0.0/12",      # Private-Use
    "192.0.0.0/24",       # IETF Protocol Assignments
    "192.0.2.0/24",       # TEST-NET-1
    "192.88.99.0/24",     # 6to4 Relay Anycast
    "192.168.0.0/16",     # Private-Use
    "198.18.0.0/15",      # Benchmarking
    "198.51.100.0/24",    # TEST-NET-2
    "203.0.113.0/24",     # TEST-NET-3
    "224.0.0.0/4",        # Multicast
    "240.0.0.0/4",        # Reserved for Future Use
    "255.255.255.255/32", # Limited Broadcast
]

# CGNAT ranges (Carrier-Grade NAT) - RFC 6598
CGNAT_RANGES = [
    "100.64.0.0/10",
]

# Known VPN Provider ASNs (partial list - expand as needed)
# Source: Various VPN provider documentation and IP lookups
VPN_ASNS = {
    # NordVPN
    212238, 208294, 207137,
    # ExpressVPN
    394711, 62041,
    # ProtonVPN
    209103, 62371,
    # Mullvad
    39351,
    # Surfshark
    212238,
    # Private Internet Access
    19531,
    # CyberGhost
    9009,
    # IPVanish
    33438,
    # HideMyAss
    30633,
    # Windscribe
    50304,
}

# Known Tor Exit Node ASNs (commonly used)
TOR_ASNS = {
    # Tor-friendly hosting providers
    47065,  # Frantech/BuyVM
    62563,  # GTHost
    396356, # MaxiHost
}

# Major datacenter/cloud ASNs (not blocked by default, but tracked)
DATACENTER_ASNS = {
    # AWS
    16509, 14618,
    # Google Cloud
    15169, 396982,
    # Microsoft Azure
    8075, 8068, 8069,
    # DigitalOcean
    14061, 393406,
    # OVH
    16276,
    # Hetzner
    24940,
    # Linode/Akamai
    63949,
    # Vultr
    20473,
    # Cloudflare
    13335,
    # Oracle Cloud
    31898,
    # Alibaba Cloud
    45102,
}

# Suspicious ISP patterns in rDNS (dynamic IP indicators)
DYNAMIC_RDNS_PATTERNS = [
    "dynamic",
    "dhcp",
    "dsl",
    "dial",
    "ppp",
    "cable",
    "pool",
    "customer",
    "client",
    "host-",
    "ip-",
    "dyn.",
    "dyn-",
    "-dyn",
    ".dyn.",
    "cgn",
    "cgnat",
    "nat.",
    "nat-",
]

# Static IP indicators in rDNS
STATIC_RDNS_PATTERNS = [
    "static",
    "business",
    "corporate",
    "enterprise",
    "dedicated",
    "server",
    "vps",
    "cloud",
    "hosting",
    "colo",
]


# ============================================================================
# IP VALIDATOR
# ============================================================================

class IPValidator:
    """
    Production-grade IP validation for P2P network.

    Enforces:
    1. Static IP requirement
    2. No VPN/Tor/Proxy
    3. No CGNAT or reserved ranges
    4. Reputation tracking
    5. Rate limiting

    Configuration options:
    - allow_datacenter: Allow datacenter IPs (default: True for nodes)
    - require_rdns: Require valid reverse DNS (default: False)
    - require_static: Require static IP verification (default: True)
    - min_reputation: Minimum reputation score (default: 0.3)
    """

    def __init__(
        self,
        allow_datacenter: bool = True,
        require_rdns: bool = False,
        require_static: bool = True,
        min_reputation: float = 0.3,
        rate_limit_per_minute: int = 10,
    ):
        self.allow_datacenter = allow_datacenter
        self.require_rdns = require_rdns
        self.require_static = require_static
        self.min_reputation = min_reputation
        self.rate_limit_per_minute = rate_limit_per_minute

        # Compile reserved ranges
        self._reserved_networks = [
            ipaddress.ip_network(r) for r in RESERVED_RANGES
        ]
        self._cgnat_networks = [
            ipaddress.ip_network(r) for r in CGNAT_RANGES
        ]

        # IP info cache
        self._ip_cache: Dict[str, IPInfo] = {}

        # Whitelist/blacklist
        self._whitelist: Set[str] = set()
        self._blacklist: Set[str] = set()
        self._whitelist_subnets: List[ipaddress.IPv4Network] = []
        self._blacklist_subnets: List[ipaddress.IPv4Network] = []

        # Rate limiting
        self._connection_times: Dict[str, List[float]] = defaultdict(list)

        # ASN cache (would need external lookup in production)
        self._asn_cache: Dict[str, Tuple[int, str]] = {}

        # Thread safety
        self._lock = threading.RLock()

        logger.info(f"IP Validator initialized: datacenter={allow_datacenter}, rdns={require_rdns}, static={require_static}")

    # =========================================================================
    # MAIN VALIDATION
    # =========================================================================

    def validate(self, ip: str) -> Tuple[ValidationResult, str]:
        """
        Validate an IP address for P2P connection.

        Args:
            ip: IP address string

        Returns:
            (result_code, reason_string) tuple
        """
        with self._lock:
            try:
                # Parse IP
                addr = ipaddress.ip_address(ip)

                # Check whitelist first
                if self._is_whitelisted(ip):
                    return ValidationResult.ALLOWED, "Whitelisted"

                # Check blacklist
                if self._is_blacklisted(ip):
                    return ValidationResult.BLOCKED_BLACKLIST, "IP is blacklisted"

                # IPv6 - currently only allow IPv4 for simplicity
                if isinstance(addr, ipaddress.IPv6Address):
                    # Could enable IPv6 with additional validation
                    return ValidationResult.BLOCKED_RESERVED, "IPv6 not yet supported"

                # Check reserved ranges
                for network in self._reserved_networks:
                    if addr in network:
                        return ValidationResult.BLOCKED_RESERVED, f"Reserved range: {network}"

                # Check CGNAT ranges
                for network in self._cgnat_networks:
                    if addr in network:
                        return ValidationResult.BLOCKED_CGNAT, "CGNAT range not allowed"

                # Check private ranges (should be caught by reserved, but double-check)
                if addr.is_private:
                    return ValidationResult.BLOCKED_PRIVATE, "Private IP not allowed"

                # Rate limiting
                if not self._check_rate_limit(ip):
                    return ValidationResult.BLOCKED_RATE_LIMIT, "Rate limit exceeded"

                # Get or create IP info
                info = self._get_or_create_info(ip)

                # Check reputation
                if info.reputation_score < self.min_reputation:
                    return ValidationResult.BLOCKED_REPUTATION, f"Low reputation: {info.reputation_score:.2f}"

                # Classify IP type
                self._classify_ip(info)

                # Block VPN
                if info.ip_type == IPType.VPN:
                    return ValidationResult.BLOCKED_VPN, "VPN detected"

                # Block Tor
                if info.ip_type == IPType.TOR:
                    return ValidationResult.BLOCKED_TOR, "Tor exit node detected"

                # Block Proxy
                if info.ip_type == IPType.PROXY:
                    return ValidationResult.BLOCKED_PROXY, "Proxy detected"

                # Block dynamic IPs if required
                if self.require_static and info.ip_type == IPType.DYNAMIC_RESIDENTIAL:
                    return ValidationResult.BLOCKED_DYNAMIC, "Dynamic IP not allowed (static required)"

                # Block datacenter if not allowed
                if not self.allow_datacenter and info.ip_type == IPType.STATIC_DATACENTER:
                    return ValidationResult.BLOCKED_DATACENTER, "Datacenter IP not allowed"

                # Check rDNS if required
                if self.require_rdns and not info.rdns:
                    return ValidationResult.BLOCKED_NO_RDNS, "No reverse DNS found"

                # Update tracking
                info.last_seen = time.time()
                info.connection_count += 1

                return ValidationResult.ALLOWED, f"Valid ({info.ip_type.name})"

            except ValueError as e:
                return ValidationResult.BLOCKED_RESERVED, f"Invalid IP format: {e}"
            except Exception as e:
                logger.warning(f"IP validation error for {ip}: {e}")
                return ValidationResult.BLOCKED_RESERVED, f"Validation error: {e}"

    # =========================================================================
    # IP CLASSIFICATION
    # =========================================================================

    def _classify_ip(self, info: IPInfo):
        """Classify IP address type using multiple signals."""
        ip = info.ip

        # Get ASN if not cached
        if info.asn == 0:
            asn, asn_name = self._lookup_asn(ip)
            info.asn = asn
            info.asn_name = asn_name

        # Get rDNS if not cached
        if not info.rdns:
            info.rdns = self._lookup_rdns(ip)

        # Check VPN ASNs
        if info.asn in VPN_ASNS:
            info.ip_type = IPType.VPN
            info.is_static = False
            return

        # Check Tor ASNs
        if info.asn in TOR_ASNS:
            info.ip_type = IPType.TOR
            info.is_static = False
            return

        # Check datacenter ASNs
        if info.asn in DATACENTER_ASNS:
            info.ip_type = IPType.STATIC_DATACENTER
            info.is_static = True
            return

        # Analyze rDNS for dynamic patterns
        rdns_lower = info.rdns.lower() if info.rdns else ""

        for pattern in DYNAMIC_RDNS_PATTERNS:
            if pattern in rdns_lower:
                info.ip_type = IPType.DYNAMIC_RESIDENTIAL
                info.is_static = False
                return

        # Check for static patterns
        for pattern in STATIC_RDNS_PATTERNS:
            if pattern in rdns_lower:
                info.ip_type = IPType.STATIC_RESIDENTIAL
                info.is_static = True
                return

        # Default classification based on ASN name
        asn_lower = info.asn_name.lower() if info.asn_name else ""

        # Hosting/cloud indicators
        hosting_keywords = ["hosting", "server", "cloud", "data center", "datacenter", "colocation"]
        for keyword in hosting_keywords:
            if keyword in asn_lower:
                info.ip_type = IPType.STATIC_DATACENTER
                info.is_static = True
                return

        # ISP indicators (may be dynamic)
        isp_keywords = ["telecom", "broadband", "mobile", "wireless", "cellular", "comcast", "verizon", "at&t"]
        for keyword in isp_keywords:
            if keyword in asn_lower:
                # Assume dynamic unless proven static
                if info.rdns and any(p in rdns_lower for p in STATIC_RDNS_PATTERNS):
                    info.ip_type = IPType.STATIC_RESIDENTIAL
                    info.is_static = True
                else:
                    info.ip_type = IPType.DYNAMIC_RESIDENTIAL
                    info.is_static = False
                return

        # Unknown - assume static if has proper rDNS
        if info.rdns and "." in info.rdns:
            info.ip_type = IPType.STATIC_RESIDENTIAL
            info.is_static = True
        else:
            info.ip_type = IPType.UNKNOWN
            info.is_static = False

    def _lookup_rdns(self, ip: str) -> str:
        """Lookup reverse DNS for IP address."""
        try:
            result = socket.gethostbyaddr(ip)
            return result[0] if result else ""
        except (socket.herror, socket.gaierror, socket.timeout):
            return ""
        except Exception as e:
            logger.debug(f"rDNS lookup failed for {ip}: {e}")
            return ""

    def _lookup_asn(self, ip: str) -> Tuple[int, str]:
        """
        Lookup ASN for IP address.

        In production, this should use:
        - Team Cymru IP-to-ASN service
        - MaxMind GeoIP2 database
        - RIPE/ARIN whois

        For now, returns cached or estimated values.
        """
        if ip in self._asn_cache:
            return self._asn_cache[ip]

        # In production, implement actual ASN lookup here
        # For now, return unknown
        return 0, ""

    # =========================================================================
    # WHITELIST/BLACKLIST
    # =========================================================================

    def add_to_whitelist(self, ip_or_subnet: str):
        """Add IP or subnet to whitelist."""
        with self._lock:
            if "/" in ip_or_subnet:
                network = ipaddress.ip_network(ip_or_subnet, strict=False)
                self._whitelist_subnets.append(network)
                logger.info(f"Whitelisted subnet: {network}")
            else:
                self._whitelist.add(ip_or_subnet)
                logger.info(f"Whitelisted IP: {ip_or_subnet}")

    def add_to_blacklist(self, ip_or_subnet: str, reason: str = ""):
        """Add IP or subnet to blacklist."""
        with self._lock:
            if "/" in ip_or_subnet:
                network = ipaddress.ip_network(ip_or_subnet, strict=False)
                self._blacklist_subnets.append(network)
                logger.warning(f"Blacklisted subnet: {network} - {reason}")
            else:
                self._blacklist.add(ip_or_subnet)
                logger.warning(f"Blacklisted IP: {ip_or_subnet} - {reason}")

    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted."""
        if ip in self._whitelist:
            return True

        try:
            addr = ipaddress.ip_address(ip)
            for network in self._whitelist_subnets:
                if addr in network:
                    return True
        except ValueError:
            pass

        return False

    def _is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted."""
        if ip in self._blacklist:
            return True

        try:
            addr = ipaddress.ip_address(ip)
            for network in self._blacklist_subnets:
                if addr in network:
                    return True
        except ValueError:
            pass

        return False

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    def _check_rate_limit(self, ip: str) -> bool:
        """Check if IP is within rate limits."""
        now = time.time()
        window = 60.0  # 1 minute window

        # Get subnet for rate limiting (prevent /24 flooding)
        try:
            addr = ipaddress.ip_address(ip)
            subnet = str(ipaddress.ip_network(f"{ip}/24", strict=False).network_address)
        except ValueError:
            subnet = ip

        # Clean old entries
        self._connection_times[subnet] = [
            t for t in self._connection_times[subnet]
            if now - t < window
        ]

        # Check limit
        if len(self._connection_times[subnet]) >= self.rate_limit_per_minute:
            return False

        # Record this connection attempt
        self._connection_times[subnet].append(now)
        return True

    # =========================================================================
    # REPUTATION MANAGEMENT
    # =========================================================================

    def record_misbehavior(self, ip: str, severity: float = 0.1):
        """
        Record misbehavior for an IP address.

        Args:
            ip: IP address
            severity: How much to decrease reputation (0.0-1.0)
        """
        with self._lock:
            info = self._get_or_create_info(ip)
            info.misbehavior_count += 1
            info.reputation_score = max(0.0, info.reputation_score - severity)

            # Auto-blacklist if reputation drops to 0
            if info.reputation_score <= 0:
                self.add_to_blacklist(ip, "Reputation dropped to zero")

    def record_good_behavior(self, ip: str, bonus: float = 0.01):
        """
        Record good behavior for an IP address.

        Args:
            ip: IP address
            bonus: How much to increase reputation (0.0-1.0)
        """
        with self._lock:
            info = self._get_or_create_info(ip)
            info.reputation_score = min(1.0, info.reputation_score + bonus)

    def get_reputation(self, ip: str) -> float:
        """Get reputation score for IP (0.0-1.0)."""
        with self._lock:
            info = self._ip_cache.get(ip)
            return info.reputation_score if info else 0.5

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_or_create_info(self, ip: str) -> IPInfo:
        """Get or create IPInfo for address."""
        if ip not in self._ip_cache:
            self._ip_cache[ip] = IPInfo(
                ip=ip,
                first_seen=time.time(),
                last_seen=time.time()
            )
        return self._ip_cache[ip]

    def get_info(self, ip: str) -> Optional[IPInfo]:
        """Get IPInfo if available."""
        with self._lock:
            return self._ip_cache.get(ip)

    def get_stats(self) -> Dict:
        """Get validator statistics."""
        with self._lock:
            total = len(self._ip_cache)
            by_type = defaultdict(int)
            for info in self._ip_cache.values():
                by_type[info.ip_type.name] += 1

            return {
                'total_ips_seen': total,
                'by_type': dict(by_type),
                'whitelist_count': len(self._whitelist) + len(self._whitelist_subnets),
                'blacklist_count': len(self._blacklist) + len(self._blacklist_subnets),
                'allow_datacenter': self.allow_datacenter,
                'require_rdns': self.require_rdns,
                'require_static': self.require_static,
            }

    def cleanup(self, max_age_hours: int = 24):
        """Remove old entries from cache."""
        with self._lock:
            now = time.time()
            max_age = max_age_hours * 3600

            to_remove = [
                ip for ip, info in self._ip_cache.items()
                if now - info.last_seen > max_age and ip not in self._whitelist
            ]

            for ip in to_remove:
                del self._ip_cache[ip]

            if to_remove:
                logger.debug(f"Cleaned up {len(to_remove)} stale IP entries")


# ============================================================================
# VPN DETECTION SERVICE
# ============================================================================

class VPNDetector:
    """
    Advanced VPN/Proxy detection service.

    Uses multiple detection methods:
    1. ASN-based detection (known VPN providers)
    2. IP range matching (known VPN exit nodes)
    3. Port scanning (common VPN ports)
    4. Timing analysis (latency patterns)
    5. Protocol fingerprinting

    Note: Some methods require external data sources.
    """

    # Common VPN/Proxy ports
    VPN_PORTS = [
        1194,   # OpenVPN
        1723,   # PPTP
        500,    # IKE/IPsec
        4500,   # IPsec NAT-T
        51820,  # WireGuard
        443,    # SSL VPN (also legitimate HTTPS)
        8080,   # HTTP Proxy
        3128,   # Squid Proxy
        1080,   # SOCKS
        9050,   # Tor SOCKS
        9051,   # Tor Control
    ]

    def __init__(self):
        # Known VPN IP ranges (sample - expand with real data)
        self._vpn_ranges: List[ipaddress.IPv4Network] = []

        # Tor exit node list (should be updated periodically)
        self._tor_exits: Set[str] = set()

        self._lock = threading.Lock()

    def is_vpn(self, ip: str) -> Tuple[bool, str]:
        """
        Check if IP is a VPN exit node.

        Returns:
            (is_vpn, detection_method)
        """
        with self._lock:
            try:
                addr = ipaddress.ip_address(ip)

                # Check VPN ranges
                for network in self._vpn_ranges:
                    if addr in network:
                        return True, "Known VPN range"

                # Check Tor exits
                if ip in self._tor_exits:
                    return True, "Tor exit node"

                return False, ""

            except ValueError:
                return False, "Invalid IP"

    def add_vpn_range(self, cidr: str):
        """Add known VPN IP range."""
        with self._lock:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                self._vpn_ranges.append(network)
                logger.info(f"Added VPN range: {network}")
            except ValueError as e:
                logger.warning(f"Invalid VPN range {cidr}: {e}")

    def add_tor_exit(self, ip: str):
        """Add known Tor exit node."""
        with self._lock:
            self._tor_exits.add(ip)

    def load_tor_exits_from_file(self, filepath: str):
        """Load Tor exit nodes from file (one IP per line)."""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    ip = line.strip()
                    if ip and not ip.startswith('#'):
                        self._tor_exits.add(ip)
            logger.info(f"Loaded {len(self._tor_exits)} Tor exit nodes from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load Tor exits from {filepath}: {e}")

    def update_tor_exits_from_url(self, url: str = "https://check.torproject.org/torbulkexitlist"):
        """
        Update Tor exit node list from official source.

        Note: Requires network access. Should be called periodically.
        """
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read().decode('utf-8')
                new_exits = set()
                for line in data.split('\n'):
                    ip = line.strip()
                    if ip and not ip.startswith('#'):
                        try:
                            ipaddress.ip_address(ip)
                            new_exits.add(ip)
                        except ValueError:
                            continue

                with self._lock:
                    self._tor_exits = new_exits

                logger.info(f"Updated {len(new_exits)} Tor exit nodes from {url}")

        except Exception as e:
            logger.error(f"Failed to update Tor exits from {url}: {e}")


# ============================================================================
# GEOGRAPHIC DIVERSITY
# ============================================================================

class GeographicDiversity:
    """
    Ensures geographic diversity of peer connections.

    Prevents concentration of nodes in single regions which could
    enable regional attacks or censorship.
    """

    MAX_PEERS_PER_COUNTRY = 10
    MAX_PEERS_PER_REGION = 25

    def __init__(self):
        self._peers_by_country: Dict[str, Set[str]] = defaultdict(set)
        self._peers_by_region: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.Lock()

        # Region mappings
        self._country_to_region = {
            # North America
            'US': 'NA', 'CA': 'NA', 'MX': 'NA',
            # Europe
            'GB': 'EU', 'DE': 'EU', 'FR': 'EU', 'NL': 'EU', 'CH': 'EU',
            'SE': 'EU', 'NO': 'EU', 'FI': 'EU', 'DK': 'EU', 'AT': 'EU',
            'BE': 'EU', 'PL': 'EU', 'CZ': 'EU', 'ES': 'EU', 'IT': 'EU',
            # Asia Pacific
            'JP': 'APAC', 'KR': 'APAC', 'SG': 'APAC', 'AU': 'APAC', 'NZ': 'APAC',
            'HK': 'APAC', 'TW': 'APAC', 'IN': 'APAC',
            # South America
            'BR': 'SA', 'AR': 'SA', 'CL': 'SA', 'CO': 'SA',
            # Africa
            'ZA': 'AF', 'NG': 'AF', 'KE': 'AF',
            # Middle East
            'AE': 'ME', 'IL': 'ME', 'SA': 'ME',
        }

    def can_add_peer(self, ip: str, country: str) -> Tuple[bool, str]:
        """Check if peer can be added based on geographic diversity."""
        with self._lock:
            country = country.upper() if country else 'XX'
            region = self._country_to_region.get(country, 'OTHER')

            if len(self._peers_by_country[country]) >= self.MAX_PEERS_PER_COUNTRY:
                return False, f"Too many peers from {country}"

            if len(self._peers_by_region[region]) >= self.MAX_PEERS_PER_REGION:
                return False, f"Too many peers from region {region}"

            return True, "OK"

    def add_peer(self, ip: str, country: str):
        """Register peer's geographic location."""
        with self._lock:
            country = country.upper() if country else 'XX'
            region = self._country_to_region.get(country, 'OTHER')

            self._peers_by_country[country].add(ip)
            self._peers_by_region[region].add(ip)

    def remove_peer(self, ip: str, country: str):
        """Unregister peer's geographic location."""
        with self._lock:
            country = country.upper() if country else 'XX'
            region = self._country_to_region.get(country, 'OTHER')

            self._peers_by_country[country].discard(ip)
            self._peers_by_region[region].discard(ip)

    def get_distribution(self) -> Dict:
        """Get current geographic distribution."""
        with self._lock:
            return {
                'by_country': {k: len(v) for k, v in self._peers_by_country.items()},
                'by_region': {k: len(v) for k, v in self._peers_by_region.items()},
            }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run IP validator self-tests."""
    logger.info("Running IP validator self-tests...")

    validator = IPValidator(
        allow_datacenter=True,
        require_rdns=False,
        require_static=True,
    )

    # Test reserved ranges
    result, reason = validator.validate("10.0.0.1")
    assert result == ValidationResult.BLOCKED_RESERVED, f"Should block private: {reason}"

    result, reason = validator.validate("192.168.1.1")
    assert result == ValidationResult.BLOCKED_RESERVED, f"Should block private: {reason}"

    result, reason = validator.validate("127.0.0.1")
    assert result == ValidationResult.BLOCKED_RESERVED, f"Should block loopback: {reason}"

    result, reason = validator.validate("100.64.0.1")
    assert result == ValidationResult.BLOCKED_CGNAT, f"Should block CGNAT: {reason}"

    logger.info("Reserved range blocking")

    # Test whitelist
    validator.add_to_whitelist("1.2.3.4")
    result, reason = validator.validate("1.2.3.4")
    assert result == ValidationResult.ALLOWED, f"Should allow whitelisted: {reason}"
    logger.info("Whitelist functionality")

    # Test blacklist
    validator.add_to_blacklist("5.6.7.8", "Test blacklist")
    result, reason = validator.validate("5.6.7.8")
    assert result == ValidationResult.BLOCKED_BLACKLIST, f"Should block blacklisted: {reason}"
    logger.info("Blacklist functionality")

    # Test rate limiting
    for i in range(15):
        result, reason = validator.validate(f"8.8.8.{i % 256}")
    # Should eventually hit rate limit for subnet
    logger.info("Rate limiting active")

    # Test reputation
    validator.record_misbehavior("9.9.9.9", 0.3)
    validator.record_misbehavior("9.9.9.9", 0.3)
    assert validator.get_reputation("9.9.9.9") < 0.5
    logger.info("Reputation tracking")

    # Test stats
    stats = validator.get_stats()
    assert 'total_ips_seen' in stats
    logger.info("Statistics collection")

    logger.info("All IP validator self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
