"""
PoT Protocol v6 Test Fixtures
"""

import pytest
import asyncio
from typing import Generator

from pot.core.types import Hash, PublicKey, SecretKey, KeyPair
from pot.core.state import GlobalState, AccountState
from pot.core.bitcoin import BitcoinAnchor


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_keypair() -> KeyPair:
    """Create a mock keypair for testing."""
    # Use deterministic values for testing
    secret_data = bytes([i % 256 for i in range(64)])
    public_data = bytes([33] + [(i + 100) % 256 for i in range(32)])

    return KeyPair(
        public=PublicKey(public_data),
        secret=SecretKey(secret_data),
    )


@pytest.fixture
def mock_keypair_2() -> KeyPair:
    """Create a second mock keypair for testing."""
    secret_data = bytes([(i + 50) % 256 for i in range(64)])
    public_data = bytes([33] + [(i + 150) % 256 for i in range(32)])

    return KeyPair(
        public=PublicKey(public_data),
        secret=SecretKey(secret_data),
    )


@pytest.fixture
def mock_bitcoin_anchor() -> BitcoinAnchor:
    """Create a mock Bitcoin anchor for testing."""
    return BitcoinAnchor(
        height=800000,
        block_hash=Hash(bytes([i % 256 for i in range(32)])),
        merkle_root=Hash(bytes([(i + 50) % 256 for i in range(32)])),
        timestamp=1700000000,
        difficulty=50000000000000,
        epoch=3,  # Post third halving
    )


@pytest.fixture
def empty_state() -> GlobalState:
    """Create an empty global state for testing."""
    return GlobalState()


@pytest.fixture
def state_with_accounts(mock_keypair, mock_keypair_2) -> GlobalState:
    """Create a state with test accounts."""
    state = GlobalState()

    # Add first account with balance
    account1 = AccountState(
        pubkey=mock_keypair.public,
        balance=1000_00000000,  # 1000 tokens
        nonce=0,
        epoch_heartbeats=10,
        total_heartbeats=100,
    )
    state.set_account(mock_keypair.public, account1)

    # Add second account with smaller balance
    account2 = AccountState(
        pubkey=mock_keypair_2.public,
        balance=100_00000000,  # 100 tokens
        nonce=5,
        epoch_heartbeats=5,
        total_heartbeats=50,
    )
    state.set_account(mock_keypair_2.public, account2)

    state.active_accounts = 2
    state.total_supply = 1100_00000000
    state.total_heartbeats = 150

    return state


@pytest.fixture
def mock_hash() -> Hash:
    """Create a mock hash for testing."""
    return Hash(bytes([i % 256 for i in range(32)]))


@pytest.fixture
def zero_hash() -> Hash:
    """Create a zero hash."""
    return Hash.zero()


# Async fixtures helper
@pytest.fixture
def async_runner():
    """Helper for running async functions in tests."""
    def runner(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    return runner
