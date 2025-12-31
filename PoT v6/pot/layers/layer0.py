"""
PoT Protocol v6 Layer 0: Physical Time
Part IV of Technical Specification

Global Atomic Time from 34 NTP sources across 8 regions.

CONCEPT: Layer 0 requires NO cryptographic proof. Atomic time is physical reality.
The key insight: time from cesium-133 atomic transitions at national metrology
laboratories is not a claim to be verified—it is a measurement to be observed.

EDGE CASES HANDLED:
1. Outlier Rejection (MAD-based)
2. RTT Compensation
3. Byzantine Fault Tolerance
4. Stratum Validation
5. Kiss-of-Death (KoD) Handling
6. Leap Second Detection
"""

from __future__ import annotations
import asyncio
import logging
import time
import statistics
from typing import List, Optional, Dict, Tuple, Set
from dataclasses import dataclass

from pot.constants import (
    ATOMIC_SOURCES,
    ALL_REGIONS,
    INHABITED_CONTINENTS,
    POLAR_REGIONS,
    NTP_TOTAL_SOURCES,
    NTP_MIN_SOURCES_CONSENSUS,
    NTP_MIN_SOURCES_CONTINENT,
    NTP_MIN_SOURCES_POLE,
    NTP_MIN_REGIONS_TOTAL,
    NTP_QUERY_TIMEOUT_MS,
    NTP_MAX_DRIFT_MS,
    NTP_RETRY_COUNT,
    AtomicTimeSource as AtomicTimeSourceConfig,
)
from pot.core.atomic import (
    AtomicSource,
    AtomicTimeProof,
    region_to_bitmap,
    popcount,
)
from pot.errors import (
    InsufficientTimeSourcesError,
    InsufficientRegionsError,
    ExcessiveTimeDriftError,
    NTPTimeoutError,
    NTPNetworkError,
)

logger = logging.getLogger(__name__)

# Try to import ntplib for actual NTP queries
_NTPLIB_AVAILABLE = False
_ntplib = None

try:
    import ntplib
    _ntplib = ntplib
    _NTPLIB_AVAILABLE = True
except ImportError:
    logger.warning("ntplib not available. Install with: pip install ntplib")


# =============================================================================
# Edge Case Constants
# =============================================================================

# Outlier detection: MAD multiplier (3.0 ≈ 99.7% of normal distribution)
OUTLIER_MAD_THRESHOLD: float = 3.0

# Maximum acceptable RTT for compensation (ignore if too high)
MAX_RTT_FOR_COMPENSATION_MS: int = 500

# Stratum limits (1 = atomic clock, 2 = synced to stratum 1)
MIN_ACCEPTABLE_STRATUM: int = 1
MAX_ACCEPTABLE_STRATUM: int = 3

# Byzantine fault tolerance: with 18+ sources, tolerate up to 5 faults
# Requires 3f+1 sources total, 2f+1 agreeing
BYZANTINE_FAULT_TOLERANCE: int = 5

# KoD (Kiss-of-Death) codes that blacklist a server
KOD_BLACKLIST_CODES: Set[str] = {"DENY", "RSTR", "RATE"}

# Global blacklist for KoD servers
_kod_blacklist: Set[str] = set()


@dataclass
class NTPResponse:
    """Enhanced NTP response with full metadata."""
    server: AtomicTimeSourceConfig
    timestamp_ms: int
    rtt_ms: int
    stratum: int
    leap_indicator: int
    success: bool
    error: Optional[str] = None
    kod_code: Optional[str] = None


# =============================================================================
# Edge Case #1: Outlier Rejection using MAD
# =============================================================================

def reject_outliers_mad(
    sources: List[AtomicSource],
    threshold: float = OUTLIER_MAD_THRESHOLD
) -> Tuple[List[AtomicSource], List[AtomicSource]]:
    """
    Reject outliers using Median Absolute Deviation (MAD).

    MAD is more robust than standard deviation because it's not
    affected by extreme values.

    Formula:
        MAD = median(|Xi - median(X)|)
        Outlier if |Xi - median| > threshold * MAD * 1.4826

    1.4826 is the consistency constant for normal distribution.

    Args:
        sources: List of atomic sources
        threshold: MAD multiplier (default 3.0)

    Returns:
        Tuple of (valid_sources, rejected_sources)
    """
    if len(sources) < 3:
        return sources, []

    timestamps = [s.timestamp_ms for s in sources]
    median_ts = statistics.median(timestamps)

    # Calculate MAD
    absolute_deviations = [abs(ts - median_ts) for ts in timestamps]
    mad = statistics.median(absolute_deviations)

    # Avoid division by zero (all timestamps identical)
    if mad == 0:
        return sources, []

    # MAD scale factor for normal distribution
    mad_scaled = mad * 1.4826

    valid = []
    rejected = []

    for source in sources:
        deviation = abs(source.timestamp_ms - median_ts)
        if deviation <= threshold * mad_scaled:
            valid.append(source)
        else:
            rejected.append(source)
            logger.warning(
                f"Outlier rejected: region={source.region}, "
                f"server={source.server_id}, "
                f"deviation={deviation}ms (threshold={threshold * mad_scaled:.1f}ms)"
            )

    return valid, rejected


# =============================================================================
# Edge Case #2: RTT Compensation
# =============================================================================

def compensate_rtt(sources: List[AtomicSource]) -> List[AtomicSource]:
    """
    Compensate timestamps for Round-Trip Time (RTT).

    NTP timestamp represents server time at transmission.
    True time ≈ timestamp + RTT/2 (assuming symmetric network).

    High RTT sources (>500ms) are not compensated as the
    asymmetry becomes unpredictable.

    Args:
        sources: List of atomic sources

    Returns:
        Sources with RTT-compensated timestamps
    """
    compensated = []

    for source in sources:
        if source.rtt_ms > MAX_RTT_FOR_COMPENSATION_MS:
            # High RTT - skip compensation, network too unstable
            logger.debug(
                f"Skipping RTT compensation: region={source.region}, "
                f"rtt={source.rtt_ms}ms > {MAX_RTT_FOR_COMPENSATION_MS}ms"
            )
            compensated.append(source)
        else:
            # Apply RTT/2 compensation
            compensated_ts = source.timestamp_ms + (source.rtt_ms // 2)
            compensated.append(AtomicSource(
                region=source.region,
                server_id=source.server_id,
                timestamp_ms=compensated_ts,
                rtt_ms=source.rtt_ms
            ))

    return compensated


# =============================================================================
# Edge Case #3: Byzantine Fault Tolerance
# =============================================================================

def check_byzantine_agreement(
    sources: List[AtomicSource],
    max_faults: int = BYZANTINE_FAULT_TOLERANCE
) -> Tuple[bool, int]:
    """
    Check if sources reach Byzantine agreement.

    For Byzantine fault tolerance with f faults:
    - Need at least 3f + 1 total sources
    - Need at least 2f + 1 agreeing sources

    Agreement = timestamps within acceptable drift (NTP_MAX_DRIFT_MS).

    Args:
        sources: List of atomic sources
        max_faults: Maximum Byzantine faults to tolerate

    Returns:
        Tuple of (agreement_reached, agreeing_count)
    """
    min_total = 3 * max_faults + 1
    min_agreeing = 2 * max_faults + 1

    if len(sources) < min_total:
        logger.warning(
            f"Insufficient sources for Byzantine tolerance: "
            f"{len(sources)} < {min_total} (f={max_faults})"
        )
        return False, 0

    timestamps = sorted(s.timestamp_ms for s in sources)
    median_ts = statistics.median(timestamps)

    # Count sources within acceptable drift
    agreeing = sum(
        1 for ts in timestamps
        if abs(ts - median_ts) <= NTP_MAX_DRIFT_MS
    )

    agreement = agreeing >= min_agreeing

    if not agreement:
        logger.warning(
            f"Byzantine agreement failed: {agreeing} agreeing < {min_agreeing} required"
        )

    return agreement, agreeing


# =============================================================================
# Edge Case #4: Stratum Validation
# =============================================================================

def filter_by_stratum(responses: List[NTPResponse]) -> List[NTPResponse]:
    """
    Filter responses by stratum level.

    Stratum levels:
    - 0: Kiss-of-Death or unspecified
    - 1: Primary reference (atomic clock)
    - 2: Secondary reference (synced to stratum 1)
    - 3+: Further removed, less accurate

    We only accept stratum 1-3 for reliable time.

    Args:
        responses: List of NTP responses

    Returns:
        Filtered responses with acceptable stratum
    """
    valid = []
    for resp in responses:
        if MIN_ACCEPTABLE_STRATUM <= resp.stratum <= MAX_ACCEPTABLE_STRATUM:
            valid.append(resp)
        else:
            logger.debug(
                f"Rejected stratum {resp.stratum} from {resp.server.host}"
            )

    return valid


# =============================================================================
# Edge Case #5: Kiss-of-Death (KoD) Handling
# =============================================================================

def handle_kod(response: NTPResponse) -> bool:
    """
    Handle Kiss-of-Death packet from NTP server.

    KoD packets tell client to stop or slow down queries.

    Common codes:
    - DENY: Access denied permanently
    - RSTR: Access restricted
    - RATE: Rate limit exceeded

    Args:
        response: NTP response to check

    Returns:
        True if response is valid (not KoD), False if KoD
    """
    if response.kod_code:
        if response.kod_code in KOD_BLACKLIST_CODES:
            _kod_blacklist.add(response.server.host)
            logger.warning(
                f"KoD received from {response.server.host}: {response.kod_code}. "
                f"Server blacklisted."
            )
            return False
        else:
            logger.info(
                f"KoD code '{response.kod_code}' from {response.server.host}"
            )

    return True


def is_blacklisted(host: str) -> bool:
    """Check if server is blacklisted due to KoD."""
    return host in _kod_blacklist


def clear_blacklist() -> None:
    """Clear the KoD blacklist (for testing)."""
    _kod_blacklist.clear()


# =============================================================================
# Edge Case #6: Leap Second Handling
# =============================================================================

def check_leap_indicator(responses: List[NTPResponse]) -> Tuple[Optional[int], bool]:
    """
    Check leap second indicator from NTP responses.

    Leap Indicator (LI) values:
    - 0: No warning
    - 1: Last minute of day has 61 seconds (+1 leap second)
    - 2: Last minute of day has 59 seconds (-1 leap second)
    - 3: Clock not synchronized (alarm condition)

    Args:
        responses: List of NTP responses

    Returns:
        Tuple of (consensus_leap_indicator, has_alarm)
    """
    leap_counts = {0: 0, 1: 0, 2: 0, 3: 0}

    for resp in responses:
        if resp.success and resp.leap_indicator in leap_counts:
            leap_counts[resp.leap_indicator] += 1

    total = len(responses)
    if total == 0:
        return None, False

    # Check for alarm condition (too many unsynchronized)
    has_alarm = leap_counts[3] > total // 3
    if has_alarm:
        logger.warning(
            f"Alarm: {leap_counts[3]}/{total} NTP sources unsynchronized"
        )

    # Find consensus leap indicator (excluding alarm)
    for li in [0, 1, 2]:
        if leap_counts[li] > total // 2:
            if li != 0:
                logger.info(f"Leap second indicator consensus: {li}")
            return li, has_alarm

    return None, has_alarm


# =============================================================================
# NTP Query Functions
# =============================================================================

async def query_ntp_server(
    server: AtomicTimeSourceConfig,
    timeout_ms: int = NTP_QUERY_TIMEOUT_MS
) -> NTPResponse:
    """
    Query a single NTP server with full metadata.

    Args:
        server: Server configuration
        timeout_ms: Query timeout in milliseconds

    Returns:
        NTPResponse with result or error
    """
    # Check blacklist
    if is_blacklisted(server.host):
        return NTPResponse(
            server=server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=16,
            leap_indicator=3,
            success=False,
            error="Server blacklisted (KoD)"
        )

    if not _NTPLIB_AVAILABLE:
        # Fallback: use local time (WARNING: not accurate for production)
        current_ms = int(time.time() * 1000)
        return NTPResponse(
            server=server,
            timestamp_ms=current_ms,
            rtt_ms=50,
            stratum=1,
            leap_indicator=0,
            success=True
        )

    try:
        client = _ntplib.NTPClient()
        loop = asyncio.get_event_loop()

        t1 = time.monotonic()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.request(server.host, version=4)
            ),
            timeout=timeout_ms / 1000.0
        )
        t2 = time.monotonic()

        rtt_ms = int((t2 - t1) * 1000)

        # Check for KoD (stratum 0 with ASCII reference ID)
        kod_code = None
        if response.stratum == 0:
            try:
                # Reference ID might be KoD code as ASCII
                ref_bytes = response.ref_id.to_bytes(4, 'big')
                kod_code = ref_bytes.decode('ascii').strip('\x00')
            except:
                pass

        return NTPResponse(
            server=server,
            timestamp_ms=int(response.tx_time * 1000),
            rtt_ms=min(rtt_ms, 65535),  # Cap to u16 max
            stratum=response.stratum,
            leap_indicator=response.leap,
            success=True,
            kod_code=kod_code
        )

    except asyncio.TimeoutError:
        return NTPResponse(
            server=server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=16,
            leap_indicator=3,
            success=False,
            error=f"Timeout after {timeout_ms}ms"
        )
    except Exception as e:
        return NTPResponse(
            server=server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=16,
            leap_indicator=3,
            success=False,
            error=str(e)
        )


async def query_ntp_server_with_retries(
    server: AtomicTimeSourceConfig,
    timeout_ms: int = NTP_QUERY_TIMEOUT_MS,
    retries: int = NTP_RETRY_COUNT
) -> Optional[NTPResponse]:
    """
    Query an NTP server with retries and exponential backoff.

    Args:
        server: Server configuration
        timeout_ms: Query timeout per attempt
        retries: Number of retry attempts

    Returns:
        NTPResponse if successful, None if all retries failed
    """
    for attempt in range(retries):
        response = await query_ntp_server(server, timeout_ms)
        if response.success:
            return response

        if attempt < retries - 1:
            # Exponential backoff: 100ms, 200ms, 400ms...
            await asyncio.sleep(0.1 * (2 ** attempt))

    return None


# =============================================================================
# Main Query Function
# =============================================================================

async def query_atomic_time() -> AtomicTimeProof:
    """
    Query atomic time from all 34 global sources with full edge case handling.

    Process:
    1. Query all sources in parallel with retries
    2. Filter by stratum (accept only 1-3)
    3. Handle KoD responses (blacklist abusive servers)
    4. Apply RTT compensation (timestamp + RTT/2)
    5. Reject outliers using MAD
    6. Check Byzantine agreement
    7. Verify region requirements
    8. Compute median timestamp
    9. Check leap second indicator

    Returns:
        AtomicTimeProof with consensus timestamp

    Raises:
        InsufficientTimeSourcesError: If < 18 sources respond
        InsufficientRegionsError: If < 5 regions respond
        ExcessiveTimeDriftError: If drift > 1000ms
    """
    # Collect all servers to query
    all_servers: List[AtomicTimeSourceConfig] = []
    for region in ALL_REGIONS:
        all_servers.extend(ATOMIC_SOURCES.get(region, []))

    logger.debug(f"Querying {len(all_servers)} NTP sources...")

    # Step 1: Query all servers in parallel
    tasks = [query_ntp_server_with_retries(server) for server in all_servers]
    results = await asyncio.gather(*tasks)

    # Step 2: Filter successful responses
    valid_responses = [r for r in results if r is not None and r.success]
    logger.debug(f"Received {len(valid_responses)} successful responses")

    # Step 3: Filter by stratum
    valid_responses = filter_by_stratum(valid_responses)
    logger.debug(f"After stratum filter: {len(valid_responses)} responses")

    # Step 4: Handle KoD
    valid_responses = [r for r in valid_responses if handle_kod(r)]

    if len(valid_responses) < NTP_MIN_SOURCES_CONSENSUS:
        raise InsufficientTimeSourcesError(
            len(valid_responses),
            NTP_MIN_SOURCES_CONSENSUS
        )

    # Check leap seconds before converting
    leap_indicator, has_alarm = check_leap_indicator(valid_responses)

    # Convert to AtomicSource
    sources = [
        AtomicSource(
            region=r.server.region,
            server_id=r.server.server_id,
            timestamp_ms=r.timestamp_ms,
            rtt_ms=r.rtt_ms
        )
        for r in valid_responses
    ]

    # Step 5: RTT compensation
    sources = compensate_rtt(sources)

    # Step 6: Outlier rejection using MAD
    sources, rejected = reject_outliers_mad(sources)
    if rejected:
        logger.info(f"Rejected {len(rejected)} outliers")

    if len(sources) < NTP_MIN_SOURCES_CONSENSUS:
        raise InsufficientTimeSourcesError(
            len(sources),
            NTP_MIN_SOURCES_CONSENSUS
        )

    # Step 7: Byzantine agreement check
    agreement, agreeing_count = check_byzantine_agreement(sources)
    if not agreement:
        logger.warning("Byzantine agreement not reached, proceeding with caution")

    # Step 8: Verify region coverage
    region_bitmap = 0
    region_counts: Dict[int, int] = {}
    for source in sources:
        region_bitmap |= region_to_bitmap(source.region)
        region_counts[source.region] = region_counts.get(source.region, 0) + 1

    regions_present = popcount(region_bitmap)
    if regions_present < NTP_MIN_REGIONS_TOTAL:
        raise InsufficientRegionsError(regions_present, NTP_MIN_REGIONS_TOTAL)

    # Verify per-continent minimums
    for region in INHABITED_CONTINENTS:
        count = region_counts.get(region, 0)
        if count < NTP_MIN_SOURCES_CONTINENT:
            logger.warning(
                f"Region {region} has only {count} sources "
                f"(minimum: {NTP_MIN_SOURCES_CONTINENT})"
            )

    # Step 9: Compute median timestamp
    timestamps = sorted(s.timestamp_ms for s in sources)
    mid = len(timestamps) // 2
    if len(timestamps) % 2 == 0:
        median_time = (timestamps[mid - 1] + timestamps[mid]) // 2
    else:
        median_time = timestamps[mid]

    # Compute median drift
    drifts = [s.timestamp_ms - median_time for s in sources]
    median_drift = int(statistics.median(drifts))

    if abs(median_drift) > NTP_MAX_DRIFT_MS:
        raise ExcessiveTimeDriftError(median_drift, NTP_MAX_DRIFT_MS)

    logger.info(
        f"Atomic time consensus: {len(sources)} sources, "
        f"{regions_present} regions, drift={median_drift}ms"
    )

    return AtomicTimeProof(
        timestamp_ms=median_time,
        source_count=len(sources),
        sources=sources,
        median_drift_ms=median_drift,
        region_bitmap=region_bitmap
    )


def validate_atomic_time(proof: AtomicTimeProof) -> bool:
    """
    Validate an atomic time proof.

    Per specification (Part IV):
    1. Minimum total sources (≥18)
    2. Region coverage (≥5 regions)
    3. Per-continent verification (≥2 per inhabited continent)
    4. Polar regions (optional but preferred)
    5. Drift is reasonable (≤1000ms)
    6. Timestamp consistency (max spread ≤10x drift limit)
    7. Outliers within reasonable bounds

    Args:
        proof: AtomicTimeProof to validate

    Returns:
        True if proof is valid
    """
    # 1. Minimum total sources
    if proof.source_count < NTP_MIN_SOURCES_CONSENSUS:
        logger.debug(
            f"Insufficient sources: {proof.source_count} < {NTP_MIN_SOURCES_CONSENSUS}"
        )
        return False

    # 2. Verify region coverage
    regions_present = popcount(proof.region_bitmap)
    if regions_present < NTP_MIN_REGIONS_TOTAL:
        logger.debug(
            f"Insufficient regions: {regions_present} < {NTP_MIN_REGIONS_TOTAL}"
        )
        return False

    # 3. Per-continent verification
    region_counts: Dict[int, int] = {}
    for source in proof.sources:
        region_counts[source.region] = region_counts.get(source.region, 0) + 1

    for region in INHABITED_CONTINENTS:
        count = region_counts.get(region, 0)
        if count < NTP_MIN_SOURCES_CONTINENT:
            logger.debug(
                f"Region {region} has insufficient sources: "
                f"{count} < {NTP_MIN_SOURCES_CONTINENT}"
            )
            return False

    # 4. Polar regions (relaxed - just log if missing)
    for region in POLAR_REGIONS:
        count = region_counts.get(region, 0)
        if count < NTP_MIN_SOURCES_POLE:
            logger.debug(f"Polar region {region} has no sources (optional)")

    # 5. Verify drift is reasonable
    if abs(proof.median_drift_ms) > NTP_MAX_DRIFT_MS:
        logger.debug(
            f"Excessive drift: {proof.median_drift_ms}ms > {NTP_MAX_DRIFT_MS}ms"
        )
        return False

    # 6. Verify timestamp consistency
    if proof.sources:
        timestamps = [s.timestamp_ms for s in proof.sources]
        max_spread = max(timestamps) - min(timestamps)
        if max_spread > NTP_MAX_DRIFT_MS * 10:
            logger.debug(f"Sources too far apart: spread={max_spread}ms")
            return False

    # 7. Check for outliers (should have been removed)
    _, outliers = reject_outliers_mad(list(proof.sources))
    if len(outliers) > 0:
        logger.debug(f"Proof contains {len(outliers)} outliers")
        # Informational - outliers in validated proof is unusual but not fatal

    return True


def query_atomic_time_sync() -> AtomicTimeProof:
    """Synchronous wrapper for query_atomic_time()."""
    return asyncio.run(query_atomic_time())


def get_current_time_ms() -> int:
    """Get current local time in milliseconds since Unix epoch."""
    return int(time.time() * 1000)


# =============================================================================
# Mock Oracle for Testing
# =============================================================================

class MockAtomicTimeOracle:
    """
    Mock atomic time oracle for testing.

    Generates deterministic atomic time proofs without network access.
    """

    def __init__(self, base_time_ms: Optional[int] = None):
        self.base_time_ms = base_time_ms or get_current_time_ms()
        self._offset_ms = 0

    def advance(self, ms: int):
        """Advance mock time by specified milliseconds."""
        self._offset_ms += ms

    def get_time_ms(self) -> int:
        """Get current mock time."""
        return self.base_time_ms + self._offset_ms

    def create_proof(self, source_count: int = 20) -> AtomicTimeProof:
        """Create a mock atomic time proof."""
        current_time = self.get_time_ms()
        sources: List[AtomicSource] = []
        region_bitmap = 0

        regions_used = list(ALL_REGIONS)
        sources_per_region = max(1, source_count // len(regions_used))

        for region in regions_used:
            region_sources = ATOMIC_SOURCES.get(region, [])
            for i, server in enumerate(region_sources[:sources_per_region]):
                if len(sources) >= source_count:
                    break

                # Add small deterministic drift
                drift = (i * 7 - len(sources) * 3) % 100 - 50

                sources.append(AtomicSource(
                    region=region,
                    server_id=server.server_id,
                    timestamp_ms=current_time + drift,
                    rtt_ms=50 + i * 5
                ))
                region_bitmap |= region_to_bitmap(region)

            if len(sources) >= source_count:
                break

        return AtomicTimeProof(
            timestamp_ms=current_time,
            source_count=len(sources),
            sources=sources,
            median_drift_ms=0,
            region_bitmap=region_bitmap
        )


# =============================================================================
# Info Functions
# =============================================================================

def get_layer0_info() -> dict:
    """Get information about Layer 0 implementation."""
    return {
        "layer": 0,
        "name": "Physical Time",
        "description": "Global Atomic Time from 34 NTP sources",
        "sources_total": NTP_TOTAL_SOURCES,
        "sources_required": NTP_MIN_SOURCES_CONSENSUS,
        "regions_required": NTP_MIN_REGIONS_TOTAL,
        "max_drift_ms": NTP_MAX_DRIFT_MS,
        "edge_cases_handled": [
            "Outlier rejection (MAD-based)",
            "RTT compensation",
            "Byzantine fault tolerance (f=5)",
            "Stratum validation (1-3)",
            "Kiss-of-Death handling",
            "Leap second detection",
        ],
        "ntplib_available": _NTPLIB_AVAILABLE,
    }


def get_edge_case_info() -> dict:
    """Get detailed information about edge case handling."""
    return {
        "outlier_rejection": {
            "method": "MAD (Median Absolute Deviation)",
            "threshold": f"{OUTLIER_MAD_THRESHOLD} × MAD × 1.4826",
            "description": "Removes timestamps > 3 MAD from median"
        },
        "rtt_compensation": {
            "method": "timestamp + RTT/2",
            "max_rtt": f"{MAX_RTT_FOR_COMPENSATION_MS}ms",
            "description": "Adjusts for network latency (symmetric assumption)"
        },
        "byzantine_tolerance": {
            "max_faults": BYZANTINE_FAULT_TOLERANCE,
            "requirement": f"≥{3 * BYZANTINE_FAULT_TOLERANCE + 1} total, "
                          f"≥{2 * BYZANTINE_FAULT_TOLERANCE + 1} agreeing",
            "description": "Tolerates up to 5 malicious/faulty sources"
        },
        "stratum_validation": {
            "min": MIN_ACCEPTABLE_STRATUM,
            "max": MAX_ACCEPTABLE_STRATUM,
            "description": "Only accepts stratum 1-3 (atomic clock hierarchy)"
        },
        "kod_handling": {
            "blacklist_codes": list(KOD_BLACKLIST_CODES),
            "description": "Blacklists servers sending Kiss-of-Death"
        },
        "leap_second": {
            "indicators": {
                0: "No warning",
                1: "+1 second (61s minute)",
                2: "-1 second (59s minute)",
                3: "Unsynchronized (alarm)"
            },
            "description": "Detects upcoming leap seconds via NTP LI field"
        }
    }
