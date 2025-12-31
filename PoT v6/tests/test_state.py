"""
PoT Protocol v6 State Tests
"""

import pytest
from pot.core.state import GlobalState, AccountState
from pot.core.types import Hash


class TestAccountState:
    """Tests for AccountState."""

    def test_account_creation(self, mock_keypair):
        """Test account state creation."""
        account = AccountState(pubkey=mock_keypair.public)
        assert account.balance == 0
        assert account.nonce == 0
        assert account.epoch_heartbeats == 0

    def test_account_with_balance(self, mock_keypair):
        """Test account with balance."""
        account = AccountState(
            pubkey=mock_keypair.public,
            balance=1000_00000000,
        )
        assert account.balance == 1000_00000000

    def test_account_serialization(self, mock_keypair):
        """Test account serialization."""
        account = AccountState(
            pubkey=mock_keypair.public,
            balance=500,
            nonce=10,
        )
        data = account.serialize()
        restored, _ = AccountState.deserialize(data)

        assert restored.balance == account.balance
        assert restored.nonce == account.nonce


class TestGlobalState:
    """Tests for GlobalState."""

    def test_empty_state(self, empty_state):
        """Test empty state creation."""
        assert empty_state.chain_height == 0
        assert empty_state.total_supply == 0
        assert empty_state.active_accounts == 0

    def test_get_account(self, state_with_accounts, mock_keypair):
        """Test getting account from state."""
        account = state_with_accounts.get_account(mock_keypair.public)
        assert account is not None
        assert account.balance == 1000_00000000

    def test_get_nonexistent_account(self, empty_state, mock_keypair):
        """Test getting nonexistent account."""
        account = empty_state.get_account(mock_keypair.public)
        assert account is None

    def test_set_account(self, empty_state, mock_keypair):
        """Test setting account."""
        account = AccountState(
            pubkey=mock_keypair.public,
            balance=100,
        )
        empty_state.set_account(mock_keypair.public, account)

        retrieved = empty_state.get_account(mock_keypair.public)
        assert retrieved is not None
        assert retrieved.balance == 100

    def test_state_copy(self, state_with_accounts):
        """Test state copy."""
        copy = state_with_accounts.copy()

        assert copy.chain_height == state_with_accounts.chain_height
        assert copy.total_supply == state_with_accounts.total_supply

        # Modifying copy shouldn't affect original
        copy.chain_height = 999
        assert state_with_accounts.chain_height != 999

    def test_get_all_pubkeys(self, state_with_accounts):
        """Test getting all public keys."""
        pubkeys = state_with_accounts.get_all_pubkeys()
        assert len(pubkeys) == 2
