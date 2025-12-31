"""
PoT Protocol v6 Layer 0 Tests
Tests for Global Atomic Time with Edge Case Handling
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from pot.core.atomic import AtomicSource, AtomicTimeProof, region_to_bitmap, popcount
from pot.layers.layer0 import (
    # Edge case functions
    reject_outliers_mad,
    compensate_rtt,
    check_byzantine_agreement,
    filter_by_stratum,
    handle_kod,
    is_blacklisted,
    clear_blacklist,
    check_leap_indicator,
    # Query functions
    query_ntp_server,
    query_atomic_time,
    validate_atomic_time,
    # Mock oracle
    MockAtomicTimeOracle,
    # Info
    get_layer0_info,
    get_edge_case_info,
    # Constants
    NTPResponse,
    OUTLIER_MAD_THRESHOLD,
    MAX_RTT_FOR_COMPENSATION_MS,
    BYZANTINE_FAULT_TOLERANCE,
    MIN_ACCEPTABLE_STRATUM,
    MAX_ACCEPTABLE_STRATUM,
    KOD_BLACKLIST_CODES,
)
from pot.constants import (
    NTP_MIN_SOURCES_CONSENSUS,
    NTP_MIN_REGIONS_TOTAL,
    NTP_MAX_DRIFT_MS,
    AtomicTimeSource,
    REGION_NORTH_AMERICA,
    REGION_EUROPE,
    REGION_ASIA,
    REGION_OCEANIA,
    REGION_SOUTH_AMERICA,
)
from pot.errors import (
    InsufficientTimeSourcesError,
    InsufficientRegionsError,
    ExcessiveTimeDriftError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_sources():
    """Create sample atomic sources for testing."""
    base_time = 1704067200000  # 2024-01-01 00:00:00 UTC
    return [
        AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=base_time + 10, rtt_ms=50),
        AtomicSource(region=REGION_NORTH_AMERICA, server_id=1, timestamp_ms=base_time + 15, rtt_ms=60),
        AtomicSource(region=REGION_EUROPE, server_id=0, timestamp_ms=base_time + 5, rtt_ms=80),
        AtomicSource(region=REGION_EUROPE, server_id=1, timestamp_ms=base_time + 12, rtt_ms=70),
        AtomicSource(region=REGION_ASIA, server_id=0, timestamp_ms=base_time + 8, rtt_ms=100),
        AtomicSource(region=REGION_ASIA, server_id=1, timestamp_ms=base_time + 20, rtt_ms=90),
        AtomicSource(region=REGION_OCEANIA, server_id=0, timestamp_ms=base_time + 7, rtt_ms=120),
        AtomicSource(region=REGION_SOUTH_AMERICA, server_id=0, timestamp_ms=base_time + 11, rtt_ms=110),
    ]


@pytest.fixture
def sources_with_outlier(sample_sources):
    """Create sources with an outlier."""
    base_time = sample_sources[0].timestamp_ms
    # Add an outlier 10 seconds off
    outlier = AtomicSource(
        region=REGION_NORTH_AMERICA,
        server_id=99,
        timestamp_ms=base_time + 10000,  # 10 seconds off
        rtt_ms=50
    )
    return sample_sources + [outlier]


@pytest.fixture
def mock_server():
    """Create a mock NTP server config."""
    return AtomicTimeSource(
        host="time.example.com",
        region=REGION_NORTH_AMERICA,
        server_id=0
    )


@pytest.fixture
def mock_ntp_response(mock_server):
    """Create a mock NTP response."""
    return NTPResponse(
        server=mock_server,
        timestamp_ms=1704067200000,
        rtt_ms=50,
        stratum=1,
        leap_indicator=0,
        success=True
    )


@pytest.fixture(autouse=True)
def clear_blacklist_before_each():
    """Clear KoD blacklist before each test."""
    clear_blacklist()
    yield
    clear_blacklist()


# =============================================================================
# Test: Outlier Rejection (MAD)
# =============================================================================

class TestOutlierRejection:
    """Tests for MAD-based outlier rejection."""

    def test_no_outliers(self, sample_sources):
        """Test with no outliers - all sources should pass."""
        valid, rejected = reject_outliers_mad(sample_sources)
        assert len(rejected) == 0
        assert len(valid) == len(sample_sources)

    def test_single_outlier(self, sources_with_outlier):
        """Test detection of single outlier."""
        valid, rejected = reject_outliers_mad(sources_with_outlier)
        assert len(rejected) == 1
        assert rejected[0].timestamp_ms > valid[0].timestamp_ms + 5000

    def test_multiple_outliers(self, sample_sources):
        """Test detection of multiple outliers."""
        base_time = sample_sources[0].timestamp_ms
        # Add multiple outliers
        outliers = [
            AtomicSource(region=REGION_EUROPE, server_id=99, timestamp_ms=base_time + 50000, rtt_ms=50),
            AtomicSource(region=REGION_ASIA, server_id=99, timestamp_ms=base_time - 50000, rtt_ms=50),
        ]
        sources = sample_sources + outliers
        valid, rejected = reject_outliers_mad(sources)
        assert len(rejected) == 2

    def test_too_few_sources(self):
        """Test with fewer than 3 sources - no rejection possible."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=1000, rtt_ms=50),
            AtomicSource(region=REGION_EUROPE, server_id=0, timestamp_ms=2000, rtt_ms=50),
        ]
        valid, rejected = reject_outliers_mad(sources)
        assert len(valid) == 2
        assert len(rejected) == 0

    def test_all_identical_timestamps(self):
        """Test when all timestamps are identical (MAD = 0)."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=i, timestamp_ms=1000, rtt_ms=50)
            for i in range(5)
        ]
        valid, rejected = reject_outliers_mad(sources)
        assert len(valid) == 5
        assert len(rejected) == 0

    def test_custom_threshold(self, sources_with_outlier):
        """Test with custom MAD threshold."""
        # Very strict threshold
        valid_strict, rejected_strict = reject_outliers_mad(sources_with_outlier, threshold=1.0)
        # Very lenient threshold
        valid_lenient, rejected_lenient = reject_outliers_mad(sources_with_outlier, threshold=100.0)

        assert len(rejected_strict) >= len(rejected_lenient)


# =============================================================================
# Test: RTT Compensation
# =============================================================================

class TestRTTCompensation:
    """Tests for RTT compensation."""

    def test_normal_rtt_compensation(self):
        """Test RTT compensation for normal RTT values."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=1000, rtt_ms=100),
        ]
        compensated = compensate_rtt(sources)
        # Should add RTT/2 = 50ms
        assert compensated[0].timestamp_ms == 1050

    def test_high_rtt_no_compensation(self):
        """Test that high RTT sources are not compensated."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=1000, rtt_ms=600),
        ]
        compensated = compensate_rtt(sources)
        # Should NOT be compensated (RTT > 500ms)
        assert compensated[0].timestamp_ms == 1000

    def test_boundary_rtt(self):
        """Test RTT at exactly the boundary."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=1000, rtt_ms=500),
        ]
        compensated = compensate_rtt(sources)
        # Exactly at boundary - should be compensated
        assert compensated[0].timestamp_ms == 1250

    def test_mixed_rtt_values(self):
        """Test with mixed RTT values."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=1000, rtt_ms=100),  # Compensate
            AtomicSource(region=REGION_EUROPE, server_id=0, timestamp_ms=1000, rtt_ms=600),  # Skip
            AtomicSource(region=REGION_ASIA, server_id=0, timestamp_ms=1000, rtt_ms=200),  # Compensate
        ]
        compensated = compensate_rtt(sources)
        assert compensated[0].timestamp_ms == 1050  # +50
        assert compensated[1].timestamp_ms == 1000  # unchanged
        assert compensated[2].timestamp_ms == 1100  # +100

    def test_zero_rtt(self):
        """Test with zero RTT."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=0, timestamp_ms=1000, rtt_ms=0),
        ]
        compensated = compensate_rtt(sources)
        assert compensated[0].timestamp_ms == 1000


# =============================================================================
# Test: Byzantine Fault Tolerance
# =============================================================================

class TestByzantineFaultTolerance:
    """Tests for Byzantine fault tolerance checking."""

    def test_sufficient_sources_agreement(self):
        """Test with sufficient agreeing sources."""
        base_time = 1000
        # 16 sources (3*5+1), all agreeing within drift
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=i, timestamp_ms=base_time + i * 10, rtt_ms=50)
            for i in range(16)
        ]
        agreement, count = check_byzantine_agreement(sources)
        assert agreement is True
        assert count >= 11  # 2*5+1

    def test_insufficient_total_sources(self):
        """Test with insufficient total sources."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=i, timestamp_ms=1000, rtt_ms=50)
            for i in range(10)  # Less than 3*5+1=16
        ]
        agreement, count = check_byzantine_agreement(sources)
        assert agreement is False

    def test_insufficient_agreeing_sources(self):
        """Test with sufficient total but insufficient agreeing sources."""
        base_time = 1000
        # 16 sources, but many disagree significantly
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=i, timestamp_ms=base_time, rtt_ms=50)
            for i in range(8)
        ] + [
            AtomicSource(region=REGION_EUROPE, server_id=i, timestamp_ms=base_time + 5000, rtt_ms=50)
            for i in range(8)
        ]
        agreement, count = check_byzantine_agreement(sources)
        # This should fail because sources are split
        assert count < 16

    def test_custom_fault_tolerance(self):
        """Test with custom fault tolerance level."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=i, timestamp_ms=1000, rtt_ms=50)
            for i in range(7)  # 3*2+1 = 7 for f=2
        ]
        agreement, count = check_byzantine_agreement(sources, max_faults=2)
        assert agreement is True

    def test_all_agreeing(self):
        """Test when all sources agree perfectly."""
        sources = [
            AtomicSource(region=REGION_NORTH_AMERICA, server_id=i, timestamp_ms=1000, rtt_ms=50)
            for i in range(20)
        ]
        agreement, count = check_byzantine_agreement(sources)
        assert agreement is True
        assert count == 20


# =============================================================================
# Test: Stratum Validation
# =============================================================================

class TestStratumValidation:
    """Tests for stratum validation."""

    def test_valid_stratum_1(self, mock_server):
        """Test stratum 1 (atomic clock) is accepted."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=0, success=True)
        ]
        filtered = filter_by_stratum(responses)
        assert len(filtered) == 1

    def test_valid_stratum_2(self, mock_server):
        """Test stratum 2 is accepted."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=2, leap_indicator=0, success=True)
        ]
        filtered = filter_by_stratum(responses)
        assert len(filtered) == 1

    def test_valid_stratum_3(self, mock_server):
        """Test stratum 3 is accepted."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=3, leap_indicator=0, success=True)
        ]
        filtered = filter_by_stratum(responses)
        assert len(filtered) == 1

    def test_invalid_stratum_0(self, mock_server):
        """Test stratum 0 (KoD/unspecified) is rejected."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=0, leap_indicator=0, success=True)
        ]
        filtered = filter_by_stratum(responses)
        assert len(filtered) == 0

    def test_invalid_stratum_4_plus(self, mock_server):
        """Test stratum 4+ is rejected."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=4, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=10, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=16, leap_indicator=0, success=True),
        ]
        filtered = filter_by_stratum(responses)
        assert len(filtered) == 0

    def test_mixed_stratums(self, mock_server):
        """Test filtering mixed stratum levels."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=4, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=2, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=0, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=3, leap_indicator=0, success=True),
        ]
        filtered = filter_by_stratum(responses)
        assert len(filtered) == 3  # Only stratum 1, 2, 3


# =============================================================================
# Test: Kiss-of-Death Handling
# =============================================================================

class TestKoDHandling:
    """Tests for Kiss-of-Death handling."""

    def test_no_kod(self, mock_ntp_response):
        """Test response without KoD is accepted."""
        assert handle_kod(mock_ntp_response) is True
        assert not is_blacklisted(mock_ntp_response.server.host)

    def test_kod_deny(self, mock_server):
        """Test DENY KoD code blacklists server."""
        response = NTPResponse(
            server=mock_server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=0,
            leap_indicator=0,
            success=True,
            kod_code="DENY"
        )
        assert handle_kod(response) is False
        assert is_blacklisted(mock_server.host)

    def test_kod_rstr(self, mock_server):
        """Test RSTR KoD code blacklists server."""
        response = NTPResponse(
            server=mock_server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=0,
            leap_indicator=0,
            success=True,
            kod_code="RSTR"
        )
        assert handle_kod(response) is False
        assert is_blacklisted(mock_server.host)

    def test_kod_rate(self, mock_server):
        """Test RATE KoD code blacklists server."""
        response = NTPResponse(
            server=mock_server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=0,
            leap_indicator=0,
            success=True,
            kod_code="RATE"
        )
        assert handle_kod(response) is False
        assert is_blacklisted(mock_server.host)

    def test_kod_unknown_code(self, mock_server):
        """Test unknown KoD code does not blacklist."""
        response = NTPResponse(
            server=mock_server,
            timestamp_ms=1000,
            rtt_ms=50,
            stratum=1,
            leap_indicator=0,
            success=True,
            kod_code="UNKNOWN"
        )
        assert handle_kod(response) is True
        assert not is_blacklisted(mock_server.host)

    def test_clear_blacklist(self, mock_server):
        """Test clearing the blacklist."""
        response = NTPResponse(
            server=mock_server,
            timestamp_ms=0,
            rtt_ms=0,
            stratum=0,
            leap_indicator=0,
            success=True,
            kod_code="DENY"
        )
        handle_kod(response)
        assert is_blacklisted(mock_server.host)

        clear_blacklist()
        assert not is_blacklisted(mock_server.host)


# =============================================================================
# Test: Leap Second Detection
# =============================================================================

class TestLeapSecondDetection:
    """Tests for leap second detection."""

    def test_no_leap_second(self, mock_server):
        """Test no leap second indicated."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=0, success=True)
            for _ in range(10)
        ]
        leap, alarm = check_leap_indicator(responses)
        assert leap == 0
        assert alarm is False

    def test_positive_leap_second(self, mock_server):
        """Test positive leap second (+1s) detection."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=1, success=True)
            for _ in range(10)
        ]
        leap, alarm = check_leap_indicator(responses)
        assert leap == 1
        assert alarm is False

    def test_negative_leap_second(self, mock_server):
        """Test negative leap second (-1s) detection."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=2, success=True)
            for _ in range(10)
        ]
        leap, alarm = check_leap_indicator(responses)
        assert leap == 2
        assert alarm is False

    def test_alarm_condition(self, mock_server):
        """Test alarm when many sources unsynchronized."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=3, success=True)
            for _ in range(10)
        ]
        leap, alarm = check_leap_indicator(responses)
        assert alarm is True

    def test_mixed_leap_indicators(self, mock_server):
        """Test consensus with mixed indicators."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=0, success=True)
            for _ in range(6)
        ] + [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=1, success=True)
            for _ in range(4)
        ]
        leap, alarm = check_leap_indicator(responses)
        assert leap == 0  # 6/10 > 50%
        assert alarm is False

    def test_no_consensus(self, mock_server):
        """Test no consensus when split evenly."""
        responses = [
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=0, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=1, success=True),
            NTPResponse(server=mock_server, timestamp_ms=1000, rtt_ms=50, stratum=1, leap_indicator=2, success=True),
        ]
        leap, alarm = check_leap_indicator(responses)
        assert leap is None  # No majority

    def test_empty_responses(self):
        """Test with empty response list."""
        leap, alarm = check_leap_indicator([])
        assert leap is None
        assert alarm is False


# =============================================================================
# Test: Mock Oracle
# =============================================================================

class TestMockAtomicTimeOracle:
    """Tests for MockAtomicTimeOracle."""

    def test_create_oracle(self):
        """Test oracle creation."""
        oracle = MockAtomicTimeOracle(base_time_ms=1000)
        assert oracle.get_time_ms() == 1000

    def test_advance_time(self):
        """Test time advancement."""
        oracle = MockAtomicTimeOracle(base_time_ms=1000)
        oracle.advance(500)
        assert oracle.get_time_ms() == 1500

    def test_create_proof(self):
        """Test proof creation."""
        oracle = MockAtomicTimeOracle(base_time_ms=1704067200000)
        proof = oracle.create_proof(source_count=20)

        assert proof.source_count == 20
        assert len(proof.sources) == 20
        assert proof.timestamp_ms == 1704067200000

    def test_proof_has_multiple_regions(self):
        """Test proof contains multiple regions."""
        oracle = MockAtomicTimeOracle()
        proof = oracle.create_proof(source_count=20)

        regions = set(s.region for s in proof.sources)
        assert len(regions) >= 3


# =============================================================================
# Test: Validation
# =============================================================================

class TestValidation:
    """Tests for atomic time proof validation."""

    def test_valid_proof(self):
        """Test validation of valid proof."""
        oracle = MockAtomicTimeOracle()
        proof = oracle.create_proof(source_count=20)
        assert validate_atomic_time(proof) is True

    def test_insufficient_sources(self):
        """Test rejection of proof with insufficient sources."""
        oracle = MockAtomicTimeOracle()
        proof = oracle.create_proof(source_count=5)
        # Manually set low count
        proof = AtomicTimeProof(
            timestamp_ms=proof.timestamp_ms,
            source_count=5,
            sources=proof.sources[:5],
            median_drift_ms=0,
            region_bitmap=proof.region_bitmap
        )
        assert validate_atomic_time(proof) is False

    def test_excessive_drift(self):
        """Test rejection of proof with excessive drift."""
        oracle = MockAtomicTimeOracle()
        proof = oracle.create_proof(source_count=20)
        # Create proof with excessive drift
        proof = AtomicTimeProof(
            timestamp_ms=proof.timestamp_ms,
            source_count=proof.source_count,
            sources=proof.sources,
            median_drift_ms=2000,  # > 1000ms
            region_bitmap=proof.region_bitmap
        )
        assert validate_atomic_time(proof) is False


# =============================================================================
# Test: Info Functions
# =============================================================================

class TestInfoFunctions:
    """Tests for information functions."""

    def test_get_layer0_info(self):
        """Test layer info retrieval."""
        info = get_layer0_info()
        assert info["layer"] == 0
        assert info["name"] == "Physical Time"
        assert "sources_total" in info
        assert "edge_cases_handled" in info
        assert len(info["edge_cases_handled"]) == 6

    def test_get_edge_case_info(self):
        """Test edge case info retrieval."""
        info = get_edge_case_info()
        assert "outlier_rejection" in info
        assert "rtt_compensation" in info
        assert "byzantine_tolerance" in info
        assert "stratum_validation" in info
        assert "kod_handling" in info
        assert "leap_second" in info
