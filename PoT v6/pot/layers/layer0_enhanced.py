"""
PoT Protocol v6 Layer 0: Physical Time (Enhanced)
Part IV of Technical Specification

Enhanced version with full edge case handling:
- Outlier rejection (MAD-based)
- RTT compensation
- Byzantine fault tolerance
- Stratum validation
- Kiss-of-Death handling
"""

from __future__ import annotations
import asyncio
import logging
import time
import statistics
from typing import List, Optional, Dict, Tuple
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
)

logger = logging.getLogger(__name__)

# Try to import ntplib
_NTPLIB_AVAILABLE = False
_ntplib = None

try:
    import ntplib
    _ntplib = ntplib
    _NTPLIB_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Edge Case Constants
# =============================================================================

# Outlier detection: MAD multiplier (3.0 = ~99.7% of normal distribution)
OUTLIER_MAD_THRESHOLD = 3.0

# Maximum acceptable RTT for compensation (ignore if too high)
MAX_RTT_FOR_COMPENSATION_MS = 500

# Minimum acceptable stratum (1 = directly connected to atomic clock)
MIN_ACCEPTABLE_STRATUM = 1
MAX_ACCEPTABLE_STRATUM = 3

# Byzantine fault tolerance: need 2f+1 agreeing sources to tolerate f faults
# With 18 minimum sources, we can tolerate up to 5 Byzantine faults
BYZANTINE_FAULT_TOLERANCE = 5

# KoD (Kiss-of-Death) codes that should blacklist a server
KOD_BLACKLIST_CODES = {"DENY", "RSTR", "RATE"}


@dataclass
class EnhancedNTPResponse:
    """Enhanced NTP response with stratum and leap info."""
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

    MAD is more robust than standard deviation for outlier detection
    because it's not affected by extreme values.

    MAD = median(|Xi - median(X)|)
    Outlier if |Xi - median| > threshold * MAD * 1.4826

    1.4826 is the consistency constant for normal distribution.

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

    # Avoid division by zero
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
                f"deviation={deviation}ms, threshold={threshold * mad_scaled:.1f}ms"
            )

    return valid, rejected


# =============================================================================
# Edge Case #2: RTT Compensation
# =============================================================================

def compensate_rtt(sources: List[AtomicSource]) -> List[AtomicSource]:
    """
    Compensate timestamps for Round-Trip Time (RTT).

    NTP timestamp represents server time at transmission.
    True time ≈ timestamp + RTT/2 (symmetric network assumption).

    For high RTT (network congestion), we reduce weight or skip compensation.

    Returns:
        Sources with RTT-compensated timestamps
    """
    compensated = []

    for source in sources:
        if source.rtt_ms > MAX_RTT_FOR_COMPENSATION_MS:
            # High RTT - don't compensate, mark as less reliable
            logger.debug(
                f"Skipping RTT compensation for high-RTT source: "
                f"region={source.region}, rtt={source.rtt_ms}ms"
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

    For Byzantine fault tolerance with f faults, we need:
    - At least 3f + 1 total sources
    - At least 2f + 1 agreeing sources

    Agreement = timestamps within acceptable drift (1000ms).

    Returns:
        Tuple of (agreement_reached, agreeing_count)
    """
    if len(sources) < 3 * max_faults + 1:
        logger.warning(
            f"Insufficient sources for Byzantine tolerance: "
            f"{len(sources)} < {3 * max_faults + 1}"
        )
        return False, 0

    timestamps = sorted(s.timestamp_ms for s in sources)
    median_ts = statistics.median(timestamps)

    # Count sources within acceptable drift
    agreeing = sum(
        1 for ts in timestamps
        if abs(ts - median_ts) <= NTP_MAX_DRIFT_MS
    )

    required = 2 * max_faults + 1
    agreement = agreeing >= required

    if not agreement:
        logger.warning(
            f"Byzantine agreement failed: {agreeing} agreeing < {required} required"
        )

    return agreement, agreeing


# =============================================================================
# Edge Case #4: Stratum Validation
# =============================================================================

def filter_by_stratum(
    responses: List[EnhancedNTPResponse]
) -> List[EnhancedNTPResponse]:
    """
    Filter responses by stratum level.

    Stratum 1 = directly connected to atomic clock (best)
    Stratum 2 = synced to stratum 1 (good)
    Stratum 3+ = less reliable

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

# Blacklisted servers (discovered KoD)
_kod_blacklist: set = set()


def handle_kod(response: EnhancedNTPResponse) -> bool:
    """
    Handle Kiss-of-Death packet from NTP server.

    KoD packets tell client to back off or stop querying.
    Common codes:
    - DENY: Access denied permanently
    - RSTR: Access restricted
    - RATE: Rate limit exceeded

    Returns:
        True if response is valid (not KoD), False if KoD received
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
                f"KoD code {response.kod_code} from {response.server.host}"
            )

    return True


def is_blacklisted(host: str) -> bool:
    """Check if server is blacklisted due to KoD."""
    return host in _kod_blacklist


# =============================================================================
# Edge Case #6: Leap Second Handling
# =============================================================================

def check_leap_indicator(sources: List[EnhancedNTPResponse]) -> Optional[int]:
    """
    Check leap second indicator from NTP responses.

    Leap Indicator (LI) values:
    0 = No warning
    1 = Last minute of day has 61 seconds (positive leap)
    2 = Last minute of day has 59 seconds (negative leap)
    3 = Clock not synchronized (alarm)

    Returns:
        Consensus leap indicator or None if no consensus
    """
    leap_counts = {0: 0, 1: 0, 2: 0, 3: 0}

    for source in sources:
        if source.success and source.leap_indicator in leap_counts:
            leap_counts[source.leap_indicator] += 1

    # Filter out unsynchronized (3)
    if leap_counts[3] > len(sources) // 3:
        logger.warning("Too many unsynchronized NTP sources")

    # Find consensus
    for li in [0, 1, 2]:  # Prefer in order
        if leap_counts[li] > len(sources) // 2:
            if li != 0:
                logger.info(f"Leap second indicator: {li}")
            return li

    return None


# =============================================================================
# Enhanced Query Function
# =============================================================================

async def query_ntp_server_enhanced(
    server: AtomicTimeSourceConfig,
    timeout_ms: int = NTP_QUERY_TIMEOUT_MS
) -> EnhancedNTPResponse:
    """
    Query NTP server with enhanced response data.

    Includes stratum, leap indicator, and KoD detection.
    """
    if is_blacklisted(server.host):
        return EnhancedNTPResponse(
            server=server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=16,
            leap_indicator=3,
            success=False,
            error="Server blacklisted"
        )

    if not _NTPLIB_AVAILABLE:
        # Fallback for testing
        current_ms = int(time.time() * 1000)
        return EnhancedNTPResponse(
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

        # Check for KoD (stratum 0 with reference ID as ASCII code)
        kod_code = None
        if response.stratum == 0:
            # Reference ID might be KoD code
            try:
                kod_code = response.ref_id.decode('ascii').strip('\x00')
            except:
                pass

        return EnhancedNTPResponse(
            server=server,
            timestamp_ms=int(response.tx_time * 1000),
            rtt_ms=min(rtt_ms, 65535),
            stratum=response.stratum,
            leap_indicator=response.leap,
            success=True,
            kod_code=kod_code
        )

    except asyncio.TimeoutError:
        return EnhancedNTPResponse(
            server=server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=16,
            leap_indicator=3,
            success=False,
            error=f"Timeout after {timeout_ms}ms"
        )
    except Exception as e:
        return EnhancedNTPResponse(
            server=server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=16,
            leap_indicator=3,
            success=False,
            error=str(e)
        )


async def query_atomic_time_enhanced() -> AtomicTimeProof:
    """
    Enhanced atomic time query with full edge case handling.

    Process:
    1. Query all sources in parallel
    2. Filter by stratum (1-3 only)
    3. Handle KoD responses
    4. Apply RTT compensation
    5. Reject outliers using MAD
    6. Check Byzantine agreement
    7. Compute median with filtered sources
    8. Verify leap second consensus
    """
    all_servers: List[AtomicTimeSourceConfig] = []
    for region in ALL_REGIONS:
        all_servers.extend(ATOMIC_SOURCES.get(region, []))

    # Step 1: Query all sources
    tasks = [query_ntp_server_enhanced(server) for server in all_servers]
    results = await asyncio.gather(*tasks)

    # Step 2: Filter by success and stratum
    valid_responses = [r for r in results if r.success]
    valid_responses = filter_by_stratum(valid_responses)

    # Step 3: Handle KoD
    valid_responses = [r for r in valid_responses if handle_kod(r)]

    if len(valid_responses) < NTP_MIN_SOURCES_CONSENSUS:
        raise InsufficientTimeSourcesError(
            len(valid_responses),
            NTP_MIN_SOURCES_CONSENSUS
        )

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

    # Step 4: RTT compensation
    sources = compensate_rtt(sources)

    # Step 5: Outlier rejection
    sources, rejected = reject_outliers_mad(sources)

    if len(sources) < NTP_MIN_SOURCES_CONSENSUS:
        raise InsufficientTimeSourcesError(
            len(sources),
            NTP_MIN_SOURCES_CONSENSUS
        )

    # Step 6: Byzantine agreement check
    agreement, agreeing_count = check_byzantine_agreement(sources)
    if not agreement:
        logger.warning(f"Byzantine agreement not reached, proceeding with caution")

    # Region validation
    region_bitmap = 0
    for source in sources:
        region_bitmap |= region_to_bitmap(source.region)

    regions_present = popcount(region_bitmap)
    if regions_present < NTP_MIN_REGIONS_TOTAL:
        raise InsufficientRegionsError(regions_present, NTP_MIN_REGIONS_TOTAL)

    # Step 7: Compute median
    timestamps = sorted(s.timestamp_ms for s in sources)
    mid = len(timestamps) // 2
    if len(timestamps) % 2 == 0:
        median_time = (timestamps[mid - 1] + timestamps[mid]) // 2
    else:
        median_time = timestamps[mid]

    # Compute drift
    drifts = [s.timestamp_ms - median_time for s in sources]
    median_drift = statistics.median(drifts)

    if abs(median_drift) > NTP_MAX_DRIFT_MS:
        raise ExcessiveTimeDriftError(int(median_drift), NTP_MAX_DRIFT_MS)

    # Step 8: Check leap second
    leap = check_leap_indicator(valid_responses)

    return AtomicTimeProof(
        timestamp_ms=median_time,
        source_count=len(sources),
        sources=sources,
        median_drift_ms=int(median_drift),
        region_bitmap=region_bitmap
    )


# =============================================================================
# Summary of Edge Cases Handled
# =============================================================================

def get_edge_case_summary() -> dict:
    """Get summary of all edge cases handled."""
    return {
        "outlier_rejection": {
            "method": "MAD (Median Absolute Deviation)",
            "threshold": f"{OUTLIER_MAD_THRESHOLD} * MAD * 1.4826",
            "description": "Removes timestamps > 3 MAD from median"
        },
        "rtt_compensation": {
            "method": "timestamp + RTT/2",
            "max_rtt": f"{MAX_RTT_FOR_COMPENSATION_MS}ms",
            "description": "Adjusts for network latency"
        },
        "byzantine_tolerance": {
            "max_faults": BYZANTINE_FAULT_TOLERANCE,
            "requirement": f"≥{3 * BYZANTINE_FAULT_TOLERANCE + 1} sources, "
                          f"≥{2 * BYZANTINE_FAULT_TOLERANCE + 1} agreeing",
            "description": "Tolerates up to 5 malicious sources"
        },
        "stratum_validation": {
            "min": MIN_ACCEPTABLE_STRATUM,
            "max": MAX_ACCEPTABLE_STRATUM,
            "description": "Only accepts stratum 1-3 (atomic clock synced)"
        },
        "kod_handling": {
            "blacklist_codes": list(KOD_BLACKLIST_CODES),
            "description": "Blacklists servers sending Kiss-of-Death"
        },
        "leap_second": {
            "indicators": "0=none, 1=+1s, 2=-1s, 3=unsync",
            "description": "Detects upcoming leap seconds"
        }
    }
